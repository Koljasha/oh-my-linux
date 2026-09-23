# docker-django: Django в Docker (dev-сервер)

Минимальный Django-проект за dev-сервером `runserver` на порту 8000.
Для продакшена смотрите [`docker-django-cron/`](../docker-django-cron/) (gunicorn).

## Запуск

```bash
cp .env.example .env   # один раз
docker compose up -d --build
```

Проверка: http://127.0.0.1:8000/admin/ (админка; суперпользователь не создан —
создайте через `docker compose exec django-app python manage.py createsuperuser`).

Логи:

```bash
docker compose logs -f
```

## Как это работает

* Базовый образ — `python:3.12-slim`, зависимости из `requirements.txt`
  ставятся в отдельный слой до копирования кода (кэш не инвалидируется правками `app/`).
* Настройки (`app/root/settings.py`) читают `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
  `DJANGO_ALLOWED_HOSTS` из окружения (`.env` через `env_file`, локально — через `load_dotenv`).
* `./app:/app` примонтирован для live-правок кода без пересборки.
  БД — sqlite (`app/db.sqlite3`, исключена из git и образа).
* Часовой пояс образа — `Europe/Moscow` (`TZ` + `tzdata`); `TIME_ZONE` в Django совпадает.

## Локальный запуск без Docker

```bash
python app/manage.py runserver
# или
gunicorn root.wsgi:application --chdir=./app --reload
```

## Остановка

```bash
docker compose down
```
