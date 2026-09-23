# Python 3.12 slim (Debian) как базовый образ.
# Тег зафиксирован для воспроизводимости сборок.
FROM python:3.12-slim

ENV TZ=Europe/Moscow \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# cron — планировщик (раз в минуту шлёт SIGHUP для reload gunicorn),
# tzdata — данные часовых поясов для TZ.
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        cron \
        tzdata && \
    ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
    echo "${TZ}" > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY cronfile /etc/cron.d/cronfile
COPY entrypoint.sh /entrypoint.sh

# cron игнорирует файлы в /etc/cron.d/ без прав 0644 и ругается без пустой строки в конце.
# Entrypoint должен быть исполняемым (COPY не гарантирует +x с Windows-хостов).
RUN chmod 0644 /etc/cron.d/cronfile && \
    chmod +x /entrypoint.sh

# Зависимости ставятся раньше кода — слой кэшируется и не пересобирается при правках app/.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 8000

# Entrypoint поднимает cron в фоне и exec'ом запускает CMD (gunicorn становится PID 1,
# поэтому `kill -HUP 1` из cronfile долетает именно до gunicorn и делает graceful reload).
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "root.wsgi:application", "--bind=0.0.0.0:8000"]
