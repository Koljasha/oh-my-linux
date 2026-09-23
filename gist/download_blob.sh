#!/usr/bin/env bash
# Скачивание HLS-потока (.m3u8) в mp4 без перекодирования.
# Ссылку на плейлист ищут в инструментах разработчика браузера,
# на вкладке «Сеть» (запрос вида index.m3u8).
#
# Запуск:
#   bash download_blob.sh
set -euo pipefail

ffmpeg -user_agent 'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0' \
    -i 'https://site.link/index.m3u8' \
    -c copy -bsf:a aac_adtstoasc downloaded_video.mp4
