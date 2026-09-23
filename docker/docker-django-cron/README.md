# docker-django-cron: Django под gunicorn + reload по cron

Django-приложение под gunicorn на порту 8000. Cron каждую минуту шлёт `SIGHUP`
в PID 1 (gunicorn) — тот делает graceful reload воркеров. Пример показывает механику
связки «cron + главный процесс», интервал — демо, подбирайте под свою задачу.

## Запуск

```bash
cp .env.example .env   # один раз
docker compose up -d --build
```

Проверка: http://127.0.0.1:8000/admin/. Reload виден в логах:

```bash
docker compose logs -f
```

## Как это работает

* Базовый образ — `python:3.12-slim` + `cron`, `tzdata`.
* `entrypoint.sh` поднимает cron фоном (`service cron start`) и `exec`-ом
  запускает `CMD` — gunicorn становится PID 1, поэтому `kill -HUP 1`
  из `cronfile` долетает именно до него.
* `cronfile` (`* * * * * root kill -HUP 1`) лежит в `/etc/cron.d/cronfile`
  с правами `0644` и пустой строкой в конце, иначе cron его игнорирует.
* Настройки читают окружение так же, как в [`docker-django/`](../docker-django/):
  `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` из `.env`.
* `./app:/app` примонтирован для live-правок кода. БД — sqlite
  (`app/db.sqlite3`, исключена из git и образа).

## Локальный запуск без Docker

```bash
python app/manage.py runserver
# или
gunicorn root.wsgi:application --chdir=./app --reload
```

## Осторожно

* `SIGHUP` для gunicorn — reload конфигурации и воркеров, но не замена образа:
  для нового кода/зависимостей делайте `docker compose up -d --build`.
* Ежеминутный reload — только для демонстрации; в проде укажите реальное
  расписание в `cronfile` и пересоберите образ.

## Остановка

```bash
docker compose down
```
