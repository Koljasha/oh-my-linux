# Python 3.12 slim (Debian) как базовый образ.
# Тег зафиксирован для воспроизводимости сборок.
FROM python:3.12-slim

ENV TZ=Europe/Moscow \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# tzdata нужен, чтобы работал часовой пояс из TZ (в slim-образе его нет).
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        tzdata && \
    ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
    echo "${TZ}" > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости ставятся раньше кода — слой кэшируется и не пересобирается при правках app/.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 8000

# Dev-сервер Django. Для продакшена используйте gunicorn
# (см. пример docker-django-cron).
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
