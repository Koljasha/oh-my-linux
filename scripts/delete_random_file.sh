#!/usr/bin/env bash
#
# Удаляем случайные файлы в каталоге, пока их число не станет <= STOP_COUNT.
#
# Использование:
#   ./delete_random_file.sh [DIR] [STOP_COUNT]
#
#   DIR         каталог, откуда удаляем (по умолчанию: Wallpapers)
#   STOP_COUNT  останавливаемся, когда файлов станет не больше этого числа (по умолчанию: 500)

set -euo pipefail

usage() {
    cat <<EOF
Использование: $(basename "$0") [DIR] [STOP_COUNT]

Удаляет случайные файлы из каталога DIR, пока их число не станет <= STOP_COUNT.

  DIR         каталог с файлами (по умолчанию: Wallpapers)
  STOP_COUNT  порог остановки (по умолчанию: 500)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if (($# > 2)); then
    usage >&2
    exit 2
fi

# каталог откуда удаляем
folder="${1:-Wallpapers}"
# количество файлов, когда перестаем удалять
stop_count="${2:-500}"

if [[ ! -d "$folder" ]]; then
    echo "ОШИБКА: каталог '$folder' не существует." >&2
    exit 1
fi

if ! [[ "$stop_count" =~ ^[0-9]+$ ]]; then
    echo "ОШИБКА: STOP_COUNT должен быть неотрицательным целым числом, получено: '$stop_count'." >&2
    exit 2
fi

while :; do
    count=$(find "$folder" -maxdepth 1 -type f -printf '.' | wc -c)
    if ((count <= stop_count)); then
        break
    fi

    # Случайный файл: find с NUL-разделителем + shuf (имена с пробелами/переводами строк безопасны).
    # read -d '' возвращает 1 на EOF после NUL, поэтому || true + явная проверка ниже.
    target=""
    IFS= read -r -d '' target < <(find "$folder" -maxdepth 1 -type f -print0 | shuf -zn1) || true
    if [[ -z "$target" ]]; then
        echo "ОШИБКА: не удалось выбрать файл в каталоге '$folder'." >&2
        exit 1
    fi

    rm -v -- "$target"
done

echo "OK"
