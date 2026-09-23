# docker-bash: bash-таймер по cron

Каждую минуту запускает `script.sh`, который пишет текущую дату в
`logs/script.sh.log` и дублирует её в stdout контейнера.

## Запуск

```bash
docker compose up -d --build
docker compose logs -f timer
```

Логи также лежат в `./logs/` на хосте (volume `./logs:/app/logs`).

## Как это работает

* Базовый образ — `debian:13-slim` + пакеты `cron`, `tzdata`.
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
