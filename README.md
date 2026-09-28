# Oh My Linux

Личная микро-база знаний по Linux: заметки, шпаргалки и учебные примеры, собранные в процессе настройки и использования системы.

Актуальные персональные настройки (дотфайлы и конфиги окружения) живут в отдельном репозитории — [Koljasha/archlinux](https://github.com/Koljasha/archlinux) — и здесь не дублируются.

## Структура

- **[handbook](handbook/README.md)** — основной раздел: заметки по установке и настройке Linux (окружение, systemd, Samba, монтирование, оболочки, сборка Python из исходников, Termux на Android).

Остальное — по алфавиту:

- [browsers](browsers/README.md) — настройки Firefox через `about:config`.
  - [firefox-policies](browsers/firefox-policies/README.md) — пример киоск-политики (доступ только к разрешённым сайтам).
- [docker](docker/README.md) — минимальные примеры Docker и Docker Compose: cron-таймеры на bash и Python, Django dev-сервер, связка Django + gunicorn + cron.
- [encryption](encryption/README.md) — шифрование: бэкап хранилища pass, GPG, OpenSSL, cryptsetup.
- [gist](gist/README.md) — короткие сниппеты и шаблоны на bash и Python (цветной вывод, ffmpeg, pip, logging, декораторы).
- [git](git/README.md) — шпаргалка по основным командам и настройкам Git.
- [mouse_mover_setup.py](scripts/mouse_mover_setup.py) — установщик/менеджер сервиса против AFK-статуса: периодически двигает курсор (systemd --user, venv с pyautogui, `--dry-run`).
- [packaging/hello-world-pkgbuild](packaging/hello-world-pkgbuild/README.md) — минимальный учебный PKGBUILD для Arch Linux.
- [packaging/python-pypi-pkgbuild](packaging/python-pypi-pkgbuild/README.md) — упаковка Python-пакетов из PyPI в PKGBUILD.
- [scripts](scripts/README.md) — коллекция утилит на Python и Bash: сетевые проверки, мониторинг цен, закладки, Steam, Twitter, Lightroom, пакетная работа с git.
- [sublime](sublime/README.md) — базовые плагины Sublime Text.

## Как пользоваться

Откройте нужный раздел из списка выше и выполняйте шаги по порядку. Примеры команд копируйте как есть, подставляя свои пути и имена.

## Примечание

Примеры ориентированы на Arch и Debian-производные; перед выполнением проверяйте команды под свой дистрибутив.

## Лицензия

MIT, см. файл [LICENSE](LICENSE).
