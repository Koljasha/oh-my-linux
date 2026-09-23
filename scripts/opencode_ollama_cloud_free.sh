#!/usr/bin/env bash
#
# Проверка всех моделей ollama-cloud в opencode.
# Каждой модели отправляется тестовый запрос; в конце выводится таблица:
# кто ответил, а кому нужен upgrade / более высокий тариф.
#
# Использование:
#   ./opencode_ollama_cloud_free.sh              # все модели ollama-cloud
#   ./opencode_ollama_cloud_free.sh glm-5.2      # только модели с подстрокой в имени
#
# Уборка: сессия удаляется ВСЕГДА, когда из вывода удалось достать её ID —
# в том числе при ошибке API ("upgrade required"), таймауте и т.п.,
# потому что sessionID присутствует в каждой строке JSON-событий,
# независимо от кода выхода opencode run.

set -euo pipefail

usage() {
    cat <<EOF
Использование: $(basename "$0") [ФИЛЬТР]

Проверяет все модели ollama-cloud в opencode тестовым запросом.

  ФИЛЬТР    опциональная подстрока имени модели (по умолчанию: все модели)
  -h, --help  показать эту справку и выйти
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if (($# > 1)); then
    usage >&2
    exit 2
fi

PROMPT="Привет, что ты за модель"
CONCURRENCY=5 # параллельных проверок
TIMEOUT=120   # сек на одну модель
FILTER="${1:-}"
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

die() {
    echo "ОШИБКА: $*" >&2
    exit 1
}
have() { command -v "$1" >/dev/null 2>&1; }

have jq || die "нужен jq"
have timeout || die "нужен timeout (coreutils)"

# ---------- 1. Получаем список моделей ----------
mapfile -t ALL < <(opencode models 2>/dev/null | grep '^ollama-cloud/' || true)
((${#ALL[@]} > 0)) || die "модели ollama-cloud не найдены (проверь 'opencode models')"

MODELS=()
for m in "${ALL[@]}"; do
    [[ $m == *"$FILTER"* ]] && MODELS+=("$m")
done
((${#MODELS[@]} > 0)) || die "под фильтр '$FILTER' не попало ни одной модели"

TOTAL=${#MODELS[@]}
echo "Найдено моделей ollama-cloud: ${#ALL[@]}, к проверке: $TOTAL${FILTER:+ (фильтр: $FILTER)}"
echo

# ---------- 2. Классификация ошибок ----------
classify_error() {
    local msg="$1" lower
    lower=$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]')

    # Высший тариф: "requires both a Pro, Max, or Team plan and extra usage"
    # (проверяется ПЕРВЫМ, т.к. это сообщение тоже содержит "upgrade for access")
    if [[ "$lower" == *'pro, max, or team'* || "$lower" == *'extra usage'* || "$lower" == *'plan max'* || "$lower" == *'max plan'* ]]; then
        STATUS="Нужен тариф Pro/Max/Team"
    elif [[ "$lower" == *'requires a subscription'* ]]; then
        STATUS="Нужен upgrade (подписка)"
    elif [[ "$lower" == *'upgrade'* ]]; then
        STATUS="Нужен upgrade"
    elif [[ "$lower" == *'retired'* ]]; then
        STATUS="Удалена (retired)"
    elif [[ "$lower" == *'rate limit'* || "$lower" == *'too many requests'* || "$lower" == *'"code":429'* || "$lower" == *'statuscode":429'* ]]; then
        STATUS="Rate limit"
    elif [[ "$lower" == *'unauthorized'* || "$lower" == *'api key'* || "$lower" == *'auth'* ]]; then
        STATUS="Ошибка авторизации"
    elif [[ "$lower" == *'not found'* ]]; then
        STATUS="Модель не найдена"
    else
        STATUS="Другая ошибка"
    fi
}

# Сокращение длинного текста до одной строки заданной ширины
shorten() {
    local text="$1" width=$2
    text=$(printf '%s' "$text" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
    if ((${#text} > width)); then
        printf '%s…' "${text:0:width-1}"
    else
        printf '%s' "$text"
    fi
}

# ---------- 3. Проверка одной модели ----------
check_model() {
    local model="$1" idx=$2
    local safe out res rc=0 detail="" status session_id="" del_out

    safe=$(printf '%s' "$model" | tr -c 'a-zA-Z0-9._-' '_')
    out="$WORKDIR/$safe.out"
    res="$WORKDIR/$safe.result"

    # Запуск; --title с именем модели: если сессию вдруг не удастся удалить,
    # её легко найти руками в списке сессий
    rc=0
    timeout "$TIMEOUT" opencode run -m "$model" --format json \
        --title "check: $model" \
        "$PROMPT" >"$out" 2>/dev/null || rc=$?

    # sessionID достаём ВСЕГДА: он есть в каждой строке JSON-событий и на
    # успехе (rc=0), и на ошибке API (rc=1, например "upgrade required")
    if [[ -s $out ]]; then
        session_id=$(jq -r '.sessionID // empty' "$out" 2>/dev/null | sort -u | head -n1)
    fi

    # Классификация ответа
    if ((rc == 0)) && grep -q '"type":"text"' "$out"; then
        status="OK"
        detail=$(jq -r 'select(.type=="text") | .part.text' "$out" 2>/dev/null | paste -sd ' ')
    else
        local err=""
        err=$(jq -r 'select(.type=="error") | .error.data.message // .error.message // empty' "$out" 2>/dev/null | head -n1)
        [[ -z "$err" && $rc -eq 124 ]] && err="Превышен таймаут ${TIMEOUT}s"
        [[ -z "$err" ]] && err="(exit code $rc)"
        classify_error "$err"
        status=$STATUS
        if [[ "$status" != "Нужен upgrade (подписка)" && "$status" != "Нужен upgrade" ]]; then
            detail=$(shorten "$err" 60)
        fi
    fi

    # Уборка сессии: ВСЕГДА, даже при ошибке API или таймауте
    if [[ -n "$session_id" ]]; then
        if ! del_out=$(opencode session delete "$session_id" 2>&1); then
            status="$status [СЕССИЯ НЕ УДАЛЕНА]"
            detail="$(shorten "$del_out" 40) ${detail:+| $detail}"
        fi
    else
        status="$status [sessionID не найден]"
    fi

    # Результат: idx<TAB>status<TAB>detail
    printf '%d\t%s\t%s\n' "$idx" "$status" "$detail" >"$res"

    printf '[%2d/%d] %-40s %s\n' "$idx" "$TOTAL" "$model" "$(shorten "$status" 50)" >&2
}

# ---------- 4. Запуск с ограничением параллелизма ----------
i=0
for model in "${MODELS[@]}"; do
    i=$((i + 1))
    check_model "$model" "$i" &
    while (($(jobs -rp | wc -l) >= CONCURRENCY)); do
        sleep 0.3
    done
done
wait

# ---------- 5. Итоговая таблица ----------
echo
echo "==================== РЕЗУЛЬТАТЫ ===================="
printf '%-4s %-36s %-46s %s\n' '#' 'МОДЕЛЬ' 'СТАТУС' 'ОТВЕТ / ДЕТАЛИ'
printf '%s\n' "$(printf '%.0s-' {1..140})"

ok_count=0
fail_count=0
leftover=0
i=0
for model in "${MODELS[@]}"; do
    i=$((i + 1))
    safe=$(printf '%s' "$model" | tr -c 'a-zA-Z0-9._-' '_')
    IFS=$'\t' read -r _idx status detail <"$WORKDIR/$safe.result"

    if [[ "$status" == "OK" ]]; then
        ok_count=$((ok_count + 1))
        color='\033[32m'
    else
        fail_count=$((fail_count + 1))
        color='\033[31m'
    fi
    [[ $status == *"НЕ УДАЛЕНА"* || $status == *"не найден"* ]] && leftover=$((leftover + 1))
    reset='\033[0m'

    printf '%-4d %-36s %b%-46s%b %s\n' "$i" "$model" "$color" "$(shorten "$status" 46)" "$reset" "$(shorten "$detail" 55)"
done

printf '%s\n' "$(printf '%.0s-' {1..140})"
echo "Итого: $ok_count ответили, $fail_count с ошибкой (из $TOTAL); неубранных сессий: $leftover"
