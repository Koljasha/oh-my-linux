# docker-python: python-таймер по cron

Каждую минуту запускает `main.py`, который пишет текущую дату в
`logs/main.py.log` и дублирует её в stdout контейнера.

## Запуск

```bash
docker compose up -d --build
docker compose logs -f timer
```

Логи также лежат в `./logs/` на хосте (volume `./logs:/app/logs`).

## Как это работает

* Базовый образ — `python:3.12-slim` + пакеты `cron`, `tzdata`.
  Выставлены `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`
  (без `.pyc` и с небуферизованным выводом — логи видны сразу).
* `cronfile` ставится в `/etc/cron.d/cronfile` с правами `0644`
  (иначе cron его игнорирует) и заканчивается пустой строкой.
* cron — PID 1 (`CMD ["cron", "-f"]`), поэтому задача перенаправляет вывод
  в `/proc/1/fd/1` — так он виден в `docker compose logs`.

Расписание меняется в `cronfile`, не забудьте пересобрать образ
(`docker compose up -d --build`).

## Остановка

```bash
docker compose down
```
