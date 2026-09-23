#!/usr/bin/env bash
set -e

# Поднимаем cron в фоне (задачи из /etc/cron.d/cronfile),
# затем exec'ом запускаем основную команду — она становится PID 1.
service cron start

exec "$@"
