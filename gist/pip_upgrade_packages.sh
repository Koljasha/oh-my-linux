#!/usr/bin/env bash
# Обновить все устаревшие pip-пакеты, по одному за вызов.
#
# Запуск:
#   bash pip_upgrade_packages.sh
set -euo pipefail

pip --disable-pip-version-check list --outdated --format=json |
    python3 -c "import json, sys; print('\n'.join(x['name'] for x in json.load(sys.stdin)))" |
    xargs -r -n1 pip install -U
# Флаг -r (--no-run-if-empty): не запускать pip, если обновлять нечего.
# Без него xargs при пустом вводе вызовет голый `pip install -U`,
# а тот упадёт с ошибкой «You must give at least one requirement».
