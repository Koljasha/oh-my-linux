#!/usr/bin/env bash
#
# git pull every folder: во всех подкаталогах с заданным remote делает pull ветки.
#
# Использование:
#   ./git_pull_all.sh [UPSTREAM] [BRANCH]
#
#   UPSTREAM  имя remote (по умолчанию: origin)
#   BRANCH    ветка (по умолчанию: master, для совместимости)

set -euo pipefail

usage() {
    cat <<EOF
Использование: $(basename "$0") [UPSTREAM] [BRANCH]

Делает 'git pull UPSTREAM BRANCH' в каждом подкаталоге текущего каталога,
у которого есть remote UPSTREAM.

  UPSTREAM  имя remote (по умолчанию: origin)
  BRANCH    ветка (по умолчанию: master)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if (($# > 2)); then
    usage >&2
    exit 2
fi

upstream="${1:-origin}"
branch="${2:-master}"

shopt -s nullglob

for d in *; do
    if [[ ! -d "$d" ]]; then
        continue
    fi
    echo "*** $d ***"
    if ! (
        cd "$d"
        if git remote | grep -Fx -- "$upstream" >/dev/null; then
            git pull "$upstream" "$branch"
        else
            echo "No upstream: $upstream"
        fi
    ); then
        echo "WARNING: каталог '$d': git-команда завершилась с ошибкой, пропускаем." >&2
    fi

    echo "---"
done

# bitbucket count js:
# document.querySelectorAll('.assistive + table > tbody > tr')
