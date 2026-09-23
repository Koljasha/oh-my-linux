# Oh My Linux

Личная микро-база знаний по Linux: заметки, шпаргалки и учебные примеры, собранные в процессе настройки и использования системы.

Актуальные персональные настройки (дотфайлы и конфиги окружения) живут в отдельном репозитории — [Koljasha/archlinux](https://github.com/Koljasha/archlinux) — и здесь не дублируются.

## Структура

- [handbook](handbook/README.md) — заметки по установке и настройке Linux (окружение, systemd, Samba, монтирование, оболочки, сборка Python из исходников).
- [browsers](browsers/README.md) — настройки Firefox через `about:config`.
  - [firefox-policies](browsers/firefox-policies/README.md) — пример киоск-политики (доступ только к разрешённым сайтам).
- [encryption](encryption/README.md) — шифрование: бэкап хранилища pass, GPG, OpenSSL, cryptsetup.
- [git](git/README.md) — шпаргалка по основным командам и настройкам Git.
- [packaging/hello-world-pkgbuild](packaging/hello-world-pkgbuild/README.md) — минимальный учебный PKGBUILD для Arch Linux.
- [packaging/python-pypi-pkgbuild](packaging/python-pypi-pkgbuild/README.md) — упаковка Python-пакетов из PyPI в PKGBUILD.
- [sublime](sublime/README.md) — базовые плагины Sublime Text.
- [termux](termux/README.md) — настройка Termux на Android.

## Как пользоваться

Откройте нужный раздел из списка выше и выполняйте шаги по порядку. Примеры команд копируйте как есть, подставляя свои пути и имена.

## Примечание

Примеры ориентированы на Arch и Debian-производные; перед выполнением проверяйте команды под свой дистрибутив.

## Лицензия

MIT, см. файл [LICENSE](LICENSE).
