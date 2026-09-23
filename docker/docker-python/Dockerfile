# Python 3.12 slim (Debian) как базовый образ.
# Тег зафиксирован для воспроизводимости сборок.
FROM python:3.12-slim

ENV TZ=Europe/Moscow \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# cron — планировщик, tzdata — данные часовых поясов для TZ.
# --no-install-recommends держит образ минимальным.
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        cron \
        tzdata && \
    ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
    echo "${TZ}" > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY main.py .
COPY cronfile /etc/cron.d/cronfile

# cron игнорирует файлы в /etc/cron.d/ без прав 0644 и ругается без пустой строки в конце.
RUN chmod 0644 /etc/cron.d/cronfile

# cron в foreground: контейнер жив, пока жив cron; логи задач см. в `docker logs`
# (задача пишет в /proc/1/fd/1 — stdout PID 1, т.е. этого процесса).
CMD ["cron", "-f"]
