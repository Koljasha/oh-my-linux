#!/usr/bin/env bash

#
# Печатаем дату в файл лога и выводим её в стандартный поток вывода
#

SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")
SCRIPTNAME=$(basename "$0")

logs_dir="$SCRIPTPATH/logs"
if [[ ! -d $logs_dir ]]; then
    mkdir -p "$logs_dir"
fi
log_file="${logs_dir}/${SCRIPTNAME}.log"

# Получаем текущую дату и время
current_date=$(date '+%Y-%m-%d %H:%M:%S')

# Формируем сообщение
message="${SCRIPTNAME} | ${current_date}"

# Выводим сообщение в файл и стандартный поток вывода
echo "$message" | tee -a "$log_file"

