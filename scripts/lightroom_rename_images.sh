#!/usr/bin/env bash
#
# Переименование файлов, выгруженных из Lightroom Mobile:
# дата выгрузки -> дата фото (EXIF DateTime -> IMG_YYYYMMDD_HHMMSS.jpeg).
#
# Использование:
#   ./lightroom_rename_images.sh   # переименовать LRM_*.jpeg в текущем каталоге

set -euo pipefail

usage() {
    cat <<EOF
Использование: $(basename "$0")

Переименовывает файлы LRM_*.jpeg в текущем каталоге по дате съёмки из EXIF
в формат IMG_YYYYMMDD_HHMMSS.jpeg. Существующие файлы не перезаписываются.
Требуется утилита 'identify' (ImageMagick).
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if (($# > 0)); then
    usage >&2
    exit 2
fi

if ! command -v identify >/dev/null 2>&1; then
    echo "ОШИБКА: требуется утилита 'identify' (пакет ImageMagick)." >&2
    exit 1
fi

shopt -s nullglob
arr=(LRM_*.jpeg)

if ((${#arr[@]} == 0)); then
    echo "Файлы LRM_*.jpeg не найдены, нечего переименовывать."
    exit 0
fi

for line in "${arr[@]}"; do
    if ! dt=$(identify -format "%[EXIF:DateTime]\n" "$line" | sed 's/://g' | sed 's/\ /_/'); then
        echo "WARNING: не удалось прочитать EXIF из '$line', пропускаем." >&2
        continue
    fi
    if [[ -z "$dt" ]]; then
        echo "WARNING: в '$line' нет EXIF DateTime, пропускаем." >&2
        continue
    fi
    name="IMG_$dt.jpeg"
    if [[ -e "$name" ]]; then
        echo "WARNING: '$name' уже существует, пропускаем '$line' (не перезаписываем)." >&2
        continue
    fi
    mv -- "$line" "$name"
    echo "$line  -->  $name"
done
