# Docker

Минимальные, воспроизводимые примеры Docker и Docker Compose:
cron-таймеры на bash и Python, Django dev-сервер и связка Django + gunicorn + cron.

Запуск — изнутри папки примера (`docker/docker-bash/` и т.д.).

## Состав

| Пример | Что внутри | Порт |
|---|---|---|
| [`docker-bash/`](docker-bash/) | bash-скрипт по cron каждую минуту, Debian slim | — |
| [`docker-python/`](docker-python/) | Python-скрипт по cron каждую минуту | — |
| [`docker-django/`](docker-django/) | Django dev-сервер (`runserver`) | 8000 |
| [`docker-django-cron/`](docker-django-cron) | gunicorn + cron, graceful reload каждую минуту | 8000 |

Каждый пример — отдельная папка со своим `Dockerfile`, `docker-compose.yml` и `README.md`.
Примеры независимы: собирать и запускать можно из любой папки.

## Требования

* Docker Engine 24+ с плагином Docker Compose v2 (`docker compose version`).
* Свободный порт 8000 для примеров с Django.

Проверено на Docker 29 / Compose v2.

## Быстрый старт

```bash
cd docker/docker-bash   # или docker-python / docker-django / docker-django-cron
docker compose up -d --build
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

### Django-примеры: переменные окружения

Перед первым запуском скопируйте шаблон окружения:

```bash
cd docker/docker-django   # или docker-django-cron
cp .env.example .env
```

`.env` не хранится в git (только `.env.example`). Значение по умолчанию
`DJANGO_SECRET_KEY=django-insecure-change-me` — тестовое, для продакшена
сгенерируйте свой ключ.

## Как устроен cron в образах

* Задачи лежат в `/etc/cron.d/cronfile` с правами `0644` и пустой строкой в конце —
  без этого cron молча игнорирует файл. Права выставляются в `Dockerfile`.
* В `docker-bash/` и `docker-python/` cron — PID 1 (`CMD ["cron", "-f"]`), поэтому
  задачи дописывают вывод в `/proc/1/fd/1` — так он попадает в `docker logs`.
  Дополнительно пишется файл `logs/*.log` (примонтирован volume `./logs`).
* В `docker-django-cron/` cron поднят фоном через `entrypoint.sh`, а PID 1 —
  gunicorn. Задача `* * * * * root kill -HUP 1` шлёт ему `SIGHUP`, gunicorn
  делает graceful reload воркеров. Это демо механики, интервал подбирайте под себя.

Часовой пояс во всех образах — `Europe/Moscow` (`TZ`, `tzdata`, `/etc/localtime`).
Чтобы сменить, поправьте `ENV TZ=...` в `Dockerfile` и `TIME_ZONE` в настройках Django.

## Структура репозитория

```
docker/
├── docker-bash/          # bash + cron
├── docker-python/        # python + cron
├── docker-django/        # Django runserver
├── docker-django-cron/   # gunicorn + cron reload
└── README.md
```

## Лицензия

[MIT](../LICENSE).
