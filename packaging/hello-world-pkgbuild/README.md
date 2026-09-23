# Минимальный учебный PKGBUILD

Пример простейшего пакета для Arch Linux: один shell-скрипт, который
устанавливается в `/usr/bin/hello` и печатает `Hello, World!`.

## Состав

* `PKGBUILD` — рецепт сборки пакета;
* `source.tar.gz` — архив с исходниками (внутри каталог `hello-world/`
  с файлом `script.sh`);
* `script.sh` — тот же скрипт в открытом виде, чтобы было видно
  содержимое архива без его распаковки.

## Как собрать и установить

```bash
cd packaging/hello-world-pkgbuild
makepkg -si
```

После установки:

```bash
hello
# Hello, World!
```

## Замечания

* `chmod +x` на `script.sh` в git не обязателен: права на исполнение
  выставляет команда `install -Dm755` в функции `package()`.
* Поле `url` указывает на руководство по упаковке пакетов Arch,
  `license` стоит `MIT` под этот учебный скрипт.
* Смежная тема — сборка пакетов Python из PyPI:
  [../python-pypi-pkgbuild/README.md](../python-pypi-pkgbuild/README.md).
