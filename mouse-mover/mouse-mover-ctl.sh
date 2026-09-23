#!/usr/bin/env bash
#
# Управление user-сервисом Mouse Mover (systemd --user).
#
# Использование:
#   ./mouse-mover-ctl.sh                 # интерактивное меню
#   ./mouse-mover-ctl.sh status          # показать статус сервиса
#   ./mouse-mover-ctl.sh start           # запустить сервис
#   ./mouse-mover-ctl.sh stop            # остановить сервис
#   ./mouse-mover-ctl.sh restart         # перезапустить сервис
#   ./mouse-mover-ctl.sh logs [--follow] # последние строки лога (--follow: следить)
#   ./mouse-mover-ctl.sh --help          # эта справка

set -euo pipefail

# ── Параметры (путь/имя сервиса меняется здесь) ────
SERVICE_TITLE="Mouse Mover"
SERVICE_NAME="mouse-mover.service"
LOG_LINES=10

# ── Цвета ──────────────────────────────────────────
CLR_RESET="\033[0m"
CLR_GREEN="\033[1;32m"
CLR_RED="\033[1;31m"
CLR_YELLOW="\033[1;33m"
CLR_CYAN="\033[1;36m"
CLR_DIM="\033[2m"

usage() {
    cat <<EOF
Использование: $(basename "$0") [КОМАНДА]

КОМАНДЫ:
  status           показать статус сервиса
  start            запустить сервис
  stop             остановить сервис
  restart          перезапустить сервис
  logs [--follow]  последние $LOG_LINES строк лога (--follow|-f: следить)
  -h, --help       показать эту справку

Без аргументов — интерактивное меню.
Сервис: $SERVICE_NAME
EOF
}

# ── Получить статус systemd ────────────────────────
get_state() {
    systemctl --user show "$SERVICE_NAME" --property=ActiveState --value 2>/dev/null
}

# ── Проверки состояний ─────────────────────────────
is_active() {
    [[ "$(get_state)" == "active" ]]
}

is_reloading() {
    [[ "$(get_state)" == "reloading" ]]
}

# ── Показать логи ──────────────────────────────────
# $1: "--follow" — следить за логом
show_logs() {
    local follow=0
    if [[ "${1:-}" == "--follow" ]]; then
        follow=1
    fi
    echo ""
    echo -e "  ${CLR_DIM}── Последние $LOG_LINES строк лога ──${CLR_RESET}"
    if ((follow)); then
        journalctl --user -u "$SERVICE_NAME" -n "$LOG_LINES" -f --no-pager 2>/dev/null |
            sed -u 's/^/    /'
    else
        journalctl --user -u "$SERVICE_NAME" -n "$LOG_LINES" --no-pager 2>/dev/null |
            sed 's/^/    /'
    fi
    echo ""
}

# ── Показать статус ────────────────────────────────
show_status() {
    local state
    # systemctl может отсутствовать/упасть вне user-сессии — показываем "неизвестно", а не падаем
    state=$(get_state || true)

    echo ""
    case "$state" in
    active)
        echo -e "  ${CLR_GREEN}▶ Сервис ==$SERVICE_TITLE== ЗАПУЩЕН${CLR_RESET}"
        ;;
    reloading)
        echo -e "  ${CLR_YELLOW}↻ Сервис ==$SERVICE_TITLE== ПЕРЕЗАПУСКАЕТСЯ...${CLR_RESET}"
        ;;
    inactive)
        echo -e "  ${CLR_RED}○ Сервис ==$SERVICE_TITLE== ОСТАНОВЛЕН${CLR_RESET}"
        ;;
    failed)
        echo -e "  ${CLR_RED}✖ Сервис ==$SERVICE_TITLE== ОШИБКА${CLR_RESET}"
        ;;
    *)
        echo -e "  ${CLR_DIM}? Сервис ==$SERVICE_TITLE== СТАТУС: $state${CLR_RESET}"
        ;;
    esac
    echo ""
}

# ── Действия с сервисом ────────────────────────────
do_start() {
    systemctl --user start "$SERVICE_NAME"
}

do_stop() {
    systemctl --user stop "$SERVICE_NAME"
}

do_restart() {
    systemctl --user restart "$SERVICE_NAME"
}

# ── Показать меню ──────────────────────────────────
show_menu() {
    if is_active; then
        echo "  [1] Перезапустить  │  [0] Остановить  │  [Enter] Выйти"
    elif is_reloading; then
        echo "  [1] Принудительно перезапустить  │  [0] Остановить  │  [Enter] Выйти"
    else
        echo "  [1] Запустить  │  [0] Остановить  │  [Enter] Выйти"
    fi
    echo ""
}

# ════════════════════════════════════════════════════
#  ИНТЕРАКТИВНЫЙ РЕЖИМ
# ════════════════════════════════════════════════════
interactive() {
    clear 2>/dev/null || true
    show_status
    show_logs
    show_menu

    echo -n "  Выбор: "
    choice=""
    IFS= read -r -n1 choice || true
    echo ""

    case "$choice" in
    1)
        if is_reloading; then
            echo -e "  ${CLR_YELLOW}Принудительная перезагрузка...${CLR_RESET}"
            if ! do_restart; then
                echo -e "  ${CLR_RED}Не удалось перезапустить сервис${CLR_RESET}"
            fi
        elif is_active; then
            echo -e "  ${CLR_CYAN}Перезапускаем...${CLR_RESET}"
            if ! do_restart; then
                echo -e "  ${CLR_RED}Не удалось перезапустить сервис${CLR_RESET}"
            fi
        else
            echo -e "  ${CLR_CYAN}Запускаем...${CLR_RESET}"
            if ! do_start; then
                echo -e "  ${CLR_RED}Не удалось запустить сервис${CLR_RESET}"
            fi
        fi
        sleep 1
        show_status
        ;;

    0)
        if is_active || is_reloading; then
            echo -e "  ${CLR_RED}Останавливаем...${CLR_RESET}"
            if ! do_stop; then
                echo -e "  ${CLR_RED}Не удалось остановить сервис${CLR_RESET}"
            fi
            sleep 1
            show_status
        else
            echo -e "  ${CLR_DIM}Сервис уже остановлен${CLR_RESET}"
        fi
        ;;

    *)
        echo -e "  ${CLR_DIM}Выход без изменений${CLR_RESET}"
        ;;
    esac

    echo ""
}

# ════════════════════════════════════════════════════
#  НЕИНТЕРАКТИВНЫЙ РЕЖИМ
# ════════════════════════════════════════════════════

# Без аргументов — интерактивное меню (как раньше)
if (($# == 0)); then
    interactive
    exit 0
fi

cmd="${1:-}"
case "$cmd" in
-h | --help | help)
    usage
    ;;
status)
    if (($# > 1)); then
        usage >&2
        exit 2
    fi
    show_status
    ;;
start)
    if (($# > 1)); then
        usage >&2
        exit 2
    fi
    do_start
    show_status
    ;;
stop)
    if (($# > 1)); then
        usage >&2
        exit 2
    fi
    do_stop
    show_status
    ;;
restart)
    if (($# > 1)); then
        usage >&2
        exit 2
    fi
    do_restart
    show_status
    ;;
logs)
    if (($# == 1)); then
        show_logs
    elif (($# == 2)) && [[ "${2:-}" == "--follow" || "${2:-}" == "-f" ]]; then
        show_logs --follow
    else
        usage >&2
        exit 2
    fi
    ;;
*)
    echo "ОШИБКА: неизвестная команда '$cmd'." >&2
    usage >&2
    exit 2
    ;;
esac
