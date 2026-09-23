#!/usr/bin/env bash

# ==============================================================================
# Генератор временных меток с поддержкой дробных шагов и стартов.
# Режимы: --step или --count (взаимоисключающие)
# Вывод: всегда в формате MM:SS.ss (два знака после точки, даже если .00).
#
# Примеры:
#   ./time_replay_counter.sh --time=2          --step=0.5
#   ./time_replay_counter.sh --time=1:30.5     --step=10.25 --start=5.75
#   ./time_replay_counter.sh --time=1:00       --count=12
#   ./time_replay_counter.sh -t 1:30 -c 10 -s 5
#
# Требования:
#   - GNU getopt (из util-linux)
#   - bc (для парсинга дробных чисел)
# ==============================================================================

set -euo pipefail

if ! getopt --version | grep -q "util-linux"; then
    echo "ОШИБКА: требуется GNU getopt (пакет util-linux). BSD-версия не поддерживается." >&2
    exit 1
fi

if ! command -v bc >/dev/null; then
    echo "ОШИБКА: требуется утилита 'bc' для парсинга дробных чисел." >&2
    exit 1
fi

# Парсим аргументы.
# Под set -e нельзя писать PARSED=$(getopt ...) + проверка $?: упадёт раньше,
# поэтому используем конструкцию if ! ... — она set -e-безопасна.
if ! PARSED=$(getopt -o t:p:s:c: -l time:,step:,start:,count: -n "$0" -- "$@"); then
    echo "ОШИБКА: сбой при разборе аргументов." >&2
    exit 2
fi
eval set -- "$PARSED" || exit 2

time_arg=""
step_arg=""
start_arg=""
count_arg=""

while true; do
    case "${1:-}" in
    -t | --time)
        time_arg="$2"
        shift 2
        ;;
    -p | --step)
        step_arg="$2"
        shift 2
        ;;
    -s | --start)
        start_arg="$2"
        shift 2
        ;;
    -c | --count)
        count_arg="$2"
        shift 2
        ;;
    --)
        shift
        break
        ;;
    *)
        echo "ВНУТРЕННЯЯ ОШИБКА"
        exit 3
        ;;
    esac
done

# Проверка взаимоисключающих параметров
if [[ -n "$step_arg" && -n "$count_arg" ]]; then
    echo "ОШИБКА: параметры --step и --count не могут быть указаны одновременно." >&2
    exit 3
fi

# Проверка обязательных параметров
if [[ -z "$time_arg" ]] || [[ -z "$step_arg" && -z "$count_arg" ]]; then
    cat >&2 <<EOF
ОШИБКА: необходимо указать --time (-t) и один из --step (-p) или --count (-c).

Использование:
  $0 --time=<время> --step=<шаг> [--start=<старт>]
  $0 --time=<время> --count=<число> [--start=<старт>]
  $0 -t <время> -p <шаг> [-s <старт>]
  $0 -t <время> -c <число> [-s <старт>]

Форматы времени:
  - Минуты:          "5"        → 5 минут
  - Мин:Сек:         "1:30"     → 1 минута 30 секунд
  - Мин:Сек.сс:      "1:30.25"  → 1:30 и 25 сотых секунды

Примеры:
  $0 -t 2 -p 0.5
  $0 --time=1:45.5 --step=10.25 --start=5.75
  $0 -t 1:00 -c 12
  $0 -t 1:30 -c 10 -s 5
EOF
    exit 3
fi

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================

# Преобразует строку времени в целое число — сотые доли секунды
parse_time_to_centiseconds() {
    local input="$1"
    local total_sec

    if [[ "$input" =~ ^[0-9]+$ ]]; then
        total_sec=$(echo "$input * 60" | bc -l)
    elif [[ "$input" =~ ^([0-9]+):([0-5]?[0-9])(\.[0-9]+)?$ ]]; then
        local min="${BASH_REMATCH[1]}"
        local sec="${BASH_REMATCH[2]}"
        local frac="${BASH_REMATCH[3]:-.0}"
        total_sec=$(echo "$min * 60 + $sec$frac" | bc -l)
    else
        echo "ОШИБКА: неверный формат времени '$input'. Ожидалось: Ч или Ч:С или Ч:С.дд" >&2
        exit 3
    fi

    # Округляем до ближайшей сотой и возвращаем целое (без точки!)
    local cs
    cs=$(echo "scale=0; ($total_sec * 100 + 0.5)/1" | bc -l)
    echo "${cs%.*}"
}

# Преобразует целое число сотых секунд → строка MM:SS.ss
centiseconds_to_mmss() {
    local cs="$1"
    # Убедимся, что это число
    if ! [[ "$cs" =~ ^[0-9]+$ ]]; then
        echo "ОШИБКА: centiseconds_to_mmss получил не число: '$cs'" >&2
        exit 3
    fi

    local total_sec=$((cs / 100))
    local frac_part=$((cs % 100))
    local minutes=$((total_sec / 60))
    local seconds=$((total_sec % 60))

    printf "%02d:%02d.%02d" "$minutes" "$seconds" "$frac_part"
}

# Проверка: неотрицательное число (для step/start/count)
is_nonnegative_number() {
    [[ "$1" =~ ^[0-9]*\.?[0-9]+$ ]] || [[ "$1" =~ ^[0-9]+$ ]]
}

# Проверка: целое положительное число (для count)
is_positive_integer() {
    [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -ge 2 ]]
}

# ==============================================================================
# ПРЕОБРАЗОВАНИЕ ВХОДНЫХ ДАННЫХ
# ==============================================================================

# Конвертируем время в сотые доли секунды
total_cs_str=$(parse_time_to_centiseconds "$time_arg")
total_cs="${total_cs_str%.*}"

# Проверяем count, если задан
if [[ -n "$count_arg" ]]; then
    if ! is_positive_integer "$count_arg"; then
        echo "ОШИБКА: --count должен быть целым числом >= 2." >&2
        exit 3
    fi
    count=$((count_arg))
fi

# ==============================================================================
# ВЫЧИСЛЕНИЕ STEP и START (если count задан)
# ==============================================================================

if [[ -n "$count_arg" ]]; then
    # Режим count: вычисляем step
    if [[ -z "$start_arg" ]]; then
        # start не задан: start = step (по умолчанию)
        # step = time / count
        step_cs_str=$(echo "scale=0; $total_cs / $count" | bc -l)
        start_cs_str="$step_cs_str"
    else
        # start задан явно
        if ! is_nonnegative_number "$start_arg"; then
            echo "ОШИБКА: старт (--start/-s) должен быть неотрицательным числом." >&2
            exit 3
        fi
        # Конвертируем start в сотые
        start_cs_str=$(echo "scale=0; ($start_arg * 100 + 0.5)/1" | bc -l)
        start_cs="${start_cs_str%.*}"

        if [[ -z "$start_cs" ]] || ! [[ "$start_cs" =~ ^[0-9]+$ ]]; then
            echo "ОШИБКА: не удалось преобразовать start в число." >&2
            exit 3
        fi

        # Проверяем, что start < time
        if ((start_cs >= total_cs)); then
            echo "ОШИБКА: старт должен быть меньше общего времени." >&2
            exit 3
        fi

        # step = (time - start) / (count - 1)
        step_cs_str=$(echo "scale=0; ($total_cs - $start_cs) / ($count - 1)" | bc -l)
    fi
else
    # Режим step: step задан явно
    if ! is_nonnegative_number "$step_arg"; then
        echo "ОШИБКА: шаг (--step/-p) должен быть неотрицательным числом." >&2
        exit 3
    fi
    step_cs_str=$(echo "scale=0; ($step_arg * 100 + 0.5)/1" | bc -l)

    # Обработка start
    if [[ -z "$start_arg" ]]; then
        start_cs_str="$step_cs_str"
    else
        if ! is_nonnegative_number "$start_arg"; then
            echo "ОШИБКА: старт (--start/-s) должен быть неотрицательным числом." >&2
            exit 3
        fi
        start_cs_str=$(echo "scale=0; ($start_arg * 100 + 0.5)/1" | bc -l)
    fi
fi

# Убираем возможную дробную часть (защита от 12200.0)
step_cs="${step_cs_str%.*}"
start_cs="${start_cs_str%.*}"

# Проверяем, что получили только цифры
if ! [[ "$total_cs" =~ ^[0-9]+$ ]] || ! [[ "$step_cs" =~ ^[0-9]+$ ]] || ! [[ "$start_cs" =~ ^[0-9]+$ ]]; then
    echo "ОШИБКА: не удалось преобразовать параметры в целые числа." >&2
    exit 3
fi

# Преобразуем в числа для арифметики
total_cs=$((total_cs))
step_cs=$((step_cs))
start_cs=$((start_cs))

# Финальные проверки
if ((step_cs <= 0)); then
    echo "ОШИБКА: шаг должен быть больше нуля." >&2
    exit 3
fi

if ((start_cs > total_cs)); then
    echo "ОШИБКА: начальная точка выходит за пределы заданного времени." >&2
    exit 3
fi

# Дополнительная проверка для count режима: вычисленные точки не выходят за time
if [[ -n "$count_arg" ]]; then
    last_point=$((start_cs + step_cs * (count - 1)))
    # Из-за округлений возможна небольшая погрешность, проверяем с допуском 1 сотую
    if ((last_point > total_cs + 1)); then
        echo "ОШИБКА: вычисленный шаг приводит к выходу за пределы времени." >&2
        exit 3
    fi
fi

# ==============================================================================
# ГЕНЕРАЦИЯ ТОЧЕК
# ==============================================================================

declare -A point_to_index
index=1

current=$start_cs
while ((current <= total_cs)); do
    point_to_index[$current]=$index
    index=$((index + 1))
    current=$((current + step_cs))
done

# ==============================================================================
# СБОРКА И ВЫВОД
# ==============================================================================

# Список точек: 0, промежуточные (без 0 и total), total (если ≠ 0)
output_points=(0)

for pt in "${!point_to_index[@]}"; do
    if ((pt == 0 || pt == total_cs)); then
        continue
    fi
    output_points+=("$pt")
done

if ((total_cs > 0)); then
    output_points+=("$total_cs")
fi

# Сортируем
mapfile -t sorted_points < <(printf '%s\n' "${output_points[@]}" | sort -n)

# Вывод сводки параметров
printf "=====================\n"
printf "Время: %s  " "$(centiseconds_to_mmss "$total_cs")"

if [[ -n "$count_arg" ]]; then
    printf "Кол-во: %s  Шаг: %s  " "$count_arg" "$(centiseconds_to_mmss "$step_cs")"
else
    printf "Шаг: %s  " "$(centiseconds_to_mmss "$step_cs")"
fi

printf "Старт: %s\n" "$(centiseconds_to_mmss "$start_cs")"
printf "=====================\n"

# Вывод
for pt in "${sorted_points[@]}"; do
    mmss=$(centiseconds_to_mmss "$pt")
    label="${point_to_index[$pt]:--}"
    printf "| %s | %s |\n" "$mmss" "$label"
done
printf "=====================\n"
