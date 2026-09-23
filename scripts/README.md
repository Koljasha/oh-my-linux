# Скрипты

Коллекция небольших утилит на Python и Bash: сетевые проверки, мониторинг цен,
работа с закладками, обоями, Steam, Twitter, Lightroom и пакетная работа с git.
Отдельный сервис — `../mouse-mover/` (шевеление мышкой против AFK).

Команды ниже даны от корня репозитория.

## Структура

```text
scripts/           # одиночные скрипты (каждый запускается сам по себе)
../mouse-mover/    # сервис «шевелитель мышки» (systemd + скрипт управления)
```

## Скрипты `scripts/`

| Файл | Назначение (1 строка) | Зависимости |
|---|---|---|
| `bookmarks_converter.py` | Конвертер закладок между форматами Firefox и Chromium (JSON → JSON, направление автоопределяется) | только stdlib Python |
| `delete_random_file.sh` | Удаляет случайные файлы в каталоге, пока их число не станет `<= STOP_COUNT` | bash |
| `dns_check.py` | Проверяет DNS-резолверы из KB AdGuard: скачивает список через curl, реально резолвит `example.com` и меряет пинг | Python stdlib + `curl`, `dig` или `kdig` |
| `git_pull_all.sh` | Делает `git pull UPSTREAM BRANCH` в каждом подкаталоге с таким remote | bash + `git` |
| `git_push_all.sh` | Делает `git push UPSTREAM BRANCH` в каждом подкаталоге с таким remote | bash + `git` |
| `lightroom_rename_images.sh` | Переименовывает `LRM_*.jpeg` по дате съёмки из EXIF в `IMG_YYYYMMDD_HHMMSS.jpeg` | bash + `identify` (ImageMagick) |
| `opencode_ollama_cloud_free.sh` | Проверяет все модели `ollama-cloud` в opencode тестовым запросом, выводит таблицу «кто ответил / кому нужен upgrade» | bash + CLI `opencode` |
| `opencode_limits_prices.py` | Печатает отчёт по OpenCode: цены Zen и лимиты/цены Go (парсит docs.opencode.ai) | только stdlib Python |
| `opencode_monitor.py` | Мониторит таблицы OpenCode Go/Zen по cron, хранит снапшот в `state.json`, шлёт изменения в Telegram | `requests`, `beautifulsoup4`, файл `.env` с `TG_BOT_TOKEN` и `TG_CHAT_ID` (не коммитить!) |
| `steam_discount.py` | Парсит распродажу Steam: `-p` пишет `steam.csv`, `-s 1/2` показывает игры со 100% скидкой | `requests`, `beautifulsoup4` |
| `time_replay_counter.sh` | Генерирует временные метки `MM:SS.ss` с дробными шагами (`--step` или `--count`, взаимоисключающие) | bash + GNU `getopt` (util-linux), `bc` |
| `twitter_del_tweets.py` | Список (и удаление с `--no-dry-run`) твитов через legacy Twitter API v1.1 | `requests`, `requests_oauthlib`, локальный `config.py` с ключами Twitter (не коммитить, шаблон в начале скрипта) |

## mouse-mover

Сервис, который периодически двигает курсор в случайную точку, чтобы не
срабатывал idle/AFK-статус. Подробная установка (venv, systemd-юнит, автозапуск) —
в [../mouse-mover/README.md](../mouse-mover/README.md).

Кратко:

```bash
./mouse-mover/mouse-mover-ctl.sh           # интерактивное меню (статус + лог)
./mouse-mover/mouse-mover-ctl.sh status    # статус сервиса
./mouse-mover/mouse-mover-ctl.sh start     # запустить
./mouse-mover/mouse-mover-ctl.sh stop      # остановить
./mouse-mover/mouse-mover-ctl.sh restart   # перезапустить
./mouse-mover/mouse-mover-ctl.sh logs      # последние строки лога (--follow: следить)
```

Зависимости: `python3`, `pyautogui` (`pip install pyautogui`), для сборки venv —
`python3-venv`, `python3-tk` (см. [../mouse-mover/README.md](../mouse-mover/README.md)).

## Требования

- `python3`, `bash`, `git`
- Для отдельных скриптов (только то, что реально используется):
  - `dns_check.py` — `curl`, `dig` или `kdig`
  - `lightroom_rename_images.sh` — `identify` (пакет ImageMagick)
  - `time_replay_counter.sh` — GNU `getopt` (util-linux), `bc`
  - `opencode_ollama_cloud_free.sh` — CLI `opencode`
  - Python-пакеты: `pip install requests beautifulsoup4` (монитор, Steam),
    `pip install pyautogui` (mouse-mover)

## Как запускать

У каждого скрипта есть `--help` (у `time_replay_counter.sh` справка печатается
при запуске без аргументов или с неверными флагами):

```bash
python3 scripts/bookmarks_converter.py --help
python3 scripts/dns_check.py --help
python3 scripts/steam_discount.py --help
python3 scripts/twitter_del_tweets.py --help
bash scripts/delete_random_file.sh --help
bash scripts/lightroom_rename_images.sh --help
bash scripts/opencode_ollama_cloud_free.sh --help
bash scripts/time_replay_counter.sh --time=1:30 --step=10
python3 scripts/opencode_limits_prices.py
python3 scripts/opencode_monitor.py
```

Примеры:

```bash
# Конвертация закладок Firefox -> Chromium
python3 scripts/bookmarks_converter.py ~/bookmarks-firefox.json -o ~/Bookmarks-Chromium.json

# Проверка DNS (только группы STANDART, 1 проход)
python3 scripts/dns_check.py --groups STANDART --passes 1

# Парсинг скидок Steam в steam.csv
python3 scripts/steam_discount.py -p

# Dry-run удаления твитов (без --no-dry-run ничего не удаляет)
python3 scripts/twitter_del_tweets.py --screen-name Koljasha
```

## Проверки

```bash
ruff check scripts/*.py mouse-mover/*.py
ty check scripts/*.py mouse-mover/*.py
shellcheck -x scripts/*.sh mouse-mover/*.sh
shfmt -d -i 4 scripts/*.sh mouse-mover/*.sh
```

## Лицензия

MIT, см. [../LICENSE](../LICENSE). Copyright (c) 2026 Koljasha.
