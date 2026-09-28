#!/usr/bin/env python3
"""mouse_mover_setup.py — установщик/менеджер user-сервиса «шевелитель мышки» (Mouse Mover).

НАЗНАЧЕНИЕ
    Ставит и сопровождает systemd --user сервис, который периодически двигает
    курсор мыши в случайную точку (против AFK-статуса). Всё живёт под обычным
    пользователем: каталог ~/.local/share/mouse-mover с venv (pyautogui) и
    скриптом-шевелителем, юнит ~/.config/systemd/user/mouse-mover.service.
    Root не нужен и не проверяется.

КОМАНДЫ (CLI)
    python3 mouse_mover_setup.py [--dry-run] [сабкоманда]
        install      установка: проверка окружения, venv, pip install pyautogui,
                     запись скрипта и юнита, daemon-reload + enable + start
        start        запустить сервис
        stop         остановить сервис
        restart      перезапустить сервис
        status       состояние сервиса (read-only)
        logs [-f]    последние 15 строк лога (--follow: следить)
        remove       удаление (подтверждение, по умолчанию НЕТ)
        run          ручной запуск шевелителя (для отладки, не для сервиса)
    Без сабкоманды — тумблер: не установлен → install; установлен → stop/start.

ПРИМЕРЫ
    ./mouse_mover_setup.py install
    ./mouse_mover_setup.py                 # тумблер
    ./mouse_mover_setup.py status
    ./mouse_mover_setup.py logs --follow
    ./mouse_mover_setup.py --dry-run install
    ./mouse_mover_setup.py remove

ПАКЕТЫ ПО ДИСТРИБУТИВАМ (если venv/tkinter отсутствуют)
    Arch/Manjaro        sudo pacman -S python tk
    Debian/Ubuntu/Mint  sudo apt install python3-venv python3-tk
    Fedora/RHEL         sudo dnf install python3-tkinter
    openSUSE            sudo zypper install python3-tk

ПРИВЯЗКА К ГРАФИЧЕСКОЙ СЕССИИ
    Юнит привязан к graphical-session.target (PartOf/After/WantedBy): шевелитель
    стартует вместе с графической сессией и останавливается вместе с ней.

ЗАВИСИМОСТЬ pyautogui
    pyautogui внедряется в venv и управляет указателем через X11/XWayland.
    В чистой Wayland-сессии без XWayland движение мыши может не работать;
    ручной run без pyautogui печатает понятную подсказку.

DRY-RUN
    --dry-run (глобальный флаг до сабкоманды): ни одного системного эффекта —
    mkdir, создание venv, pip, запись файлов, systemctl и удаления только
    печатаются с префиксом [dry-run]. Проверки окружения (venv/tkinter/os-release)
    реальны: они read-only.

Exit-коды: 0 успех/отмена; 1 ошибка операции; 2 неверные аргументы; 130 Ctrl-C.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import random
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
SERVICE_NAME = "mouse-mover.service"
SERVICE_TITLE = "Mouse Mover"
LOG_LINES = 15

SHARE_DIR = Path.home() / ".local" / "share" / "mouse-mover"
VENV_DIR = SHARE_DIR / ".venv"
VENV_PY = VENV_DIR / "bin" / "python"
MOVER_PY = SHARE_DIR / "mouse-mover.py"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT = UNIT_DIR / SERVICE_NAME

EXIT_OK = 0
EXIT_ERR = 1
EXIT_ARGS = 2
EXIT_SIGINT = 130

# ANSI-цвета (как в mouse-mover-ctl.sh)
C_GREEN = "1;32"
C_RED = "1;31"
C_YELLOW = "1;33"
C_CYAN = "1;36"
C_DIM = "2"

# Записываемый автономный шевелитель. Логику/дефолты/тексты держать синхронными
# с подкомандой run (в AGENT NOTES есть пометка).
MOVER_SOURCE = (
    textwrap.dedent(
        r'''
    #!/usr/bin/env python
    """Случайно двигать курсор мыши против определения простоя/AFK.

    Каждые ``interval`` секунд двигает курсор в случайную точку внутри
    прямоугольной области до прерывания по Ctrl+C.

    Требуется:
        pip install pyautogui
    """

    import argparse
    import random
    import time


    def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
        """Разобрать аргументы командной строки.

        Args:
            argv: Необязательный список аргументов для тестов. По умолчанию ``None``
                (используется ``sys.argv``).

        Returns:
            Разобранный ``argparse.Namespace`` с атрибутами ``interval``, ``min_xy``
            и ``max_xy``.

        При неверных аргументах завершается с кодом 2 и печатает usage.
        """
        parser = argparse.ArgumentParser(
            description="Периодически двигать мышь в случайные координаты.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=5.0,
            help="Секунд между движениями (по умолчанию: %(default)s).",
        )
        parser.add_argument(
            "--min-xy",
            nargs=2,
            type=int,
            default=[100, 100],
            metavar=("MIN_X", "MIN_Y"),
            help="Левый верхний угол области (по умолчанию: %(default)s).",
        )
        parser.add_argument(
            "--max-xy",
            nargs=2,
            type=int,
            default=[1000, 1000],
            metavar=("MAX_X", "MAX_Y"),
            help="Правый нижний угол области (по умолчанию: %(default)s).",
        )
        args = parser.parse_args(argv)
        if args.interval <= 0:
            parser.error("--interval должен быть положительным.")
        min_x, min_y = args.min_xy
        max_x, max_y = args.max_xy
        if min_x > max_x or min_y > max_y:
            parser.error("--min-xy не должен превышать --max-xy.")
        return args


    def main(argv: list[str] | None = None) -> None:
        """Запустить цикл движения мыши до прерывания.

        Args:
            argv: Необязательный список аргументов, передаваемый в :func:`parse_args`.

        При неверных аргументах завершается с кодом 2 (через ``argparse``).
        """
        args = parse_args(argv)
        min_x, min_y = args.min_xy
        max_x, max_y = args.max_xy

        # Импорт здесь, чтобы импорт модуля, --help и проверка аргументов работали без дисплея (headless).
        import pyautogui

        pyautogui.FAILSAFE = True
        print(
            f"Двигаю мышь каждые {args.interval} с в x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]. Ctrl+C для остановки."
        )
        try:
            while True:
                pyautogui.moveTo(random.randint(min_x, max_x), random.randint(min_y, max_y))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nОстановлено.")


    if __name__ == "__main__":
        main()
    '''
    ).strip()
    + "\n"
)


# ---------------------------------------------------------------------------
# Ошибки
# ---------------------------------------------------------------------------
class StepError(Exception):
    """Ошибка операции (subprocess/файлы) — exit 1."""


# ---------------------------------------------------------------------------
# Утилиты вывода
# ---------------------------------------------------------------------------
def _colors_enabled() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


_COLOR = _colors_enabled()


def c(code: str, text: str) -> str:
    """Обернуть текст ANSI-цветом (или вернуть как есть при no-color)."""
    if not _COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def log(level: str, msg: str) -> None:
    """Единая точка логирования: INFO/WARN/ERR/DRY."""
    if level == "INFO":
        prefix = c(C_CYAN, "[INFO]")
    elif level == "WARN":
        prefix = c(C_YELLOW, "[WARN]")
    elif level == "ERR":
        prefix = c(C_RED, "[ERR] ")
    else:
        prefix = c(C_DIM, "[dry-run]")
    print(f"{prefix} {msg}", flush=True)


def confirm(prompt: str, default: bool = False) -> bool:
    """Подтверждение y/N. Пустой ввод/EOF → default. Только «y/да» = да."""
    sys.stdout.write(c(C_CYAN, prompt) + " ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        log("WARN", "ввод недоступен (EOF) — принят ответ по умолчанию")
        return default
    raw = line.strip().lower()
    if raw == "":
        return default
    return raw in {"y", "yes", "да", "д"}


# ---------------------------------------------------------------------------
# Runner — единственная точка outward-эффектов
# ---------------------------------------------------------------------------
class Runner:
    """Все мутации проходят здесь. В dry-run только печатает, ничего не делает."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def run(
        self,
        cmd: list[str],
        *,
        mutates: bool = False,
        check: bool = True,
        capture: bool = True,
        timeout: int | None = 300,
    ) -> subprocess.CompletedProcess:
        if mutates and self.dry_run:
            log("DRY", " ".join(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        try:
            cp = subprocess.run(
                cmd,
                capture_output=capture,
                text=capture,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            if check:
                raise StepError(f"команда не найдена: {cmd[0]}") from None
            return subprocess.CompletedProcess(cmd, 127, "", f"команда не найдена: {cmd[0]}")
        except subprocess.TimeoutExpired:
            if check:
                raise StepError(f"таймаут команды: {' '.join(cmd)}") from None
            return subprocess.CompletedProcess(cmd, 124, "", "timeout")
        if check and cp.returncode != 0:
            detail = (cp.stderr or "").strip() or (cp.stdout or "").strip()
            raise StepError(
                f"команда завершилась с кодом {cp.returncode}: {' '.join(cmd)}\n{detail}"
            )
        return cp

    def mkdir(self, path: str, mode: int = 0o755) -> None:
        if self.dry_run:
            log("DRY", f"mkdir -p {path} (mode={oct(mode)})")
            return
        Path(path).mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)

    def write_file(self, path: str, content: str, *, mode: int = 0o644, dump: bool = True) -> None:
        if self.dry_run:
            log("DRY", f"запись файла {path} (mode={oct(mode)}, {len(content)} байт)")
            if dump:
                for line in content.rstrip("\n").splitlines():
                    log("DRY", "    " + line)
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        os.chmod(target, mode)

    def remove_file(self, path: str) -> None:
        if self.dry_run:
            log("DRY", f"rm -f {path}")
            return
        Path(path).unlink(missing_ok=True)

    def rmtree(self, path: Path) -> None:
        if self.dry_run:
            log("DRY", f"rm -rf {path}")
            return
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Вспомогательные функции (только чтения)
# ---------------------------------------------------------------------------
def is_installed() -> bool:
    """Установлен ли сервис (по наличию unit-файла)."""
    return UNIT.exists()


def os_release_ids() -> tuple[str, str]:
    """(ID, ID_LIKE) из /etc/os-release в нижнем регистре; ('','') при неудаче."""
    values: dict[str, str] = {}
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", ""
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
    return values.get("ID", "").lower(), values.get("ID_LIKE", "").lower()


def package_hint(ident: str, like: str) -> str:
    """Команда установки недостающих пакетов для дистрибутива."""
    if ident == "arch" or "arch" in like:
        return "sudo pacman -S python tk"
    if ident in ("debian", "ubuntu", "linuxmint") or "debian" in like or "ubuntu" in like:
        return "sudo apt install python3-venv python3-tk"
    if ident == "fedora" or "fedora" in like:
        return "sudo dnf install python3-tkinter"
    if ident.startswith("opensuse") or "suse" in like:
        return "sudo zypper install python3-tk"
    return (
        "установите пакеты python3-venv и python3-tk (или аналогичные для вашего "
        "дистрибутива) и повторите install"
    )


def systemd_state(runner: Runner) -> tuple[str, str]:
    """(ActiveState, UnitFileState) через systemctl --user show (read-only)."""
    cp = runner.run(
        [
            "systemctl",
            "--user",
            "show",
            SERVICE_NAME,
            "--property=ActiveState",
            "--property=UnitFileState",
            "--value",
        ],
        check=False,
    )
    lines = (cp.stdout or "").splitlines()
    active = lines[0].strip() if lines else ""
    unit_state = lines[1].strip() if len(lines) > 1 else ""
    return active, unit_state


_STATE_STYLE = {
    "active": (C_GREEN, "▶ Сервис Mouse Mover ЗАПУЩЕН"),
    "reloading": (C_YELLOW, "↻ Сервис Mouse Mover ПЕРЕЗАПУСКАЕТСЯ"),
    "inactive": (C_RED, "○ Сервис Mouse Mover ОСТАНОВЛЕН"),
    "failed": (C_RED, "✖ Сервис Mouse Mover ОШИБКА"),
}


def show_status(runner: Runner) -> int:
    """Напечатать человекочитаемый статус. Всегда 0 (кроме системных сбоев)."""
    if not is_installed():
        print(c(C_DIM, "○ Сервис Mouse Mover не установлен (выполните install)"))
        return EXIT_OK
    active, unit_state = systemd_state(runner)
    code, text = _STATE_STYLE.get(
        active, (C_DIM, f"? Сервис Mouse Mover СТАТУС: {active or 'неизвестно'}")
    )
    print(c(code, text))
    if unit_state in ("enabled", "enabled-runtime"):
        auto = "включён в автозапуск"
    else:
        auto = f"автозапуск: {unit_state or 'выключен'}"
    print(c(C_DIM, f"  юнит: {UNIT} ({auto})"))
    return EXIT_OK


def unit_template() -> str:
    return (
        "[Unit]\n"
        "Description=Mouse Mover (anti-AFK)\n"
        "PartOf=graphical-session.target\n"
        "After=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=%h/.local/share/mouse-mover/.venv/bin/python "
        "%h/.local/share/mouse-mover/mouse-mover.py\n"
        "Restart=always\n"
        "RestartSec=3\n"
        "\n"
        "[Install]\n"
        "WantedBy=graphical-session.target\n"
    )


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------
def cmd_install(runner: Runner, _args) -> int:
    log("INFO", "=== Шаг 1/5: проверка окружения ===")
    ident, like = os_release_ids()
    missing = [m for m in ("venv", "tkinter") if importlib.util.find_spec(m) is None]
    systemd_ok = shutil.which("systemctl") is not None
    if missing or not systemd_ok:
        if missing:
            log("ERR", "не найдены модули Python: " + ", ".join(missing))
            print("    Установите зависимости: " + package_hint(ident, like))
        if not systemd_ok:
            log("ERR", "systemd недоступен: команда systemctl не найдена")
        return EXIT_ERR

    if is_installed():
        log("INFO", "уже установлен (переустановка = remove + install)")
        show_status(runner)
        return EXIT_OK

    log("INFO", "=== Шаг 2/5: каталог и venv ===")
    runner.mkdir(str(SHARE_DIR))
    runner.run([sys.executable, "-m", "venv", str(VENV_DIR)], mutates=True)
    log("INFO", "=== Шаг 3/5: pyautogui в venv ===")
    log("INFO", "pip install pyautogui")
    cp = runner.run([str(VENV_PY), "-m", "pip", "install", "pyautogui"], mutates=True, check=False)
    if not runner.dry_run and cp.returncode != 0:
        log("ERR", "pip install pyautogui не удался (проверьте сеть и повторите install)")
        detail = (cp.stderr or "").strip() or (cp.stdout or "").strip()
        if detail:
            print(detail)
        return EXIT_ERR

    log("INFO", "=== Шаг 4/5: скрипт-шевелитель и юнит ===")
    runner.write_file(str(MOVER_PY), MOVER_SOURCE, mode=0o755, dump=False)
    runner.write_file(str(UNIT), unit_template(), mode=0o644)

    log("INFO", "=== Шаг 5/5: systemd --user ===")
    runner.run(["systemctl", "--user", "daemon-reload"], mutates=True, check=False)
    runner.run(["systemctl", "--user", "enable", SERVICE_NAME], mutates=True, check=False)
    runner.run(["systemctl", "--user", "start", SERVICE_NAME], mutates=True, check=False)
    if runner.dry_run:
        log("DRY", "установка НЕ выполнена — это сухой прогон; запустите без --dry-run")
        return EXIT_OK
    log("INFO", "установлено и запущено")
    show_status(runner)
    return EXIT_OK


def _service_action(runner: Runner, action: str) -> int:
    if not is_installed():
        log("ERR", "сервис не установлен — выполните install")
        return EXIT_ERR
    cp = runner.run(["systemctl", "--user", action, SERVICE_NAME], mutates=True, check=False)
    if not runner.dry_run and cp.returncode != 0:
        log("ERR", f"systemctl {action} не удался: {(cp.stderr or '').strip()}")
        return EXIT_ERR
    show_status(runner)
    return EXIT_OK


def cmd_start(runner: Runner, _args) -> int:
    return _service_action(runner, "start")


def cmd_stop(runner: Runner, _args) -> int:
    return _service_action(runner, "stop")


def cmd_restart(runner: Runner, _args) -> int:
    return _service_action(runner, "restart")


def cmd_status(runner: Runner, _args) -> int:
    return show_status(runner)


def cmd_logs(runner: Runner, args) -> int:
    cmd = ["journalctl", "--user", "-u", SERVICE_NAME, "-n", str(LOG_LINES), "--no-pager"]
    follow = getattr(args, "follow", False)
    if follow:
        cmd.append("-f")
    # journalctl -f стримит бесконечно — таймаут по умолчанию (300 c) убил бы его молча.
    runner.run(cmd, check=False, capture=False, timeout=None if follow else 300)
    return EXIT_OK


def cmd_default(runner: Runner, args) -> int:
    """Без сабкоманды: не установлен → install; иначе тумблер stop/start."""
    if not is_installed():
        return cmd_install(runner, args)
    active, _ = systemd_state(runner)
    action = "stop" if active == "active" else "start"
    cp = runner.run(["systemctl", "--user", action, SERVICE_NAME], mutates=True, check=False)
    if cp.returncode != 0:
        log("ERR", f"systemctl --user {action} завершился с кодом {cp.returncode}")
        show_status(runner)
        return EXIT_ERR
    log("INFO", "остановлено" if action == "stop" else "запущено")
    show_status(runner)
    return EXIT_OK


def _guard_share_dir() -> None:
    """Проверка перед рекурсивным удалением: удаляем только SHARE_DIR."""
    expected = Path.home() / ".local" / "share" / "mouse-mover"
    if SHARE_DIR != expected:
        raise StepError(f"отказ: путь {SHARE_DIR} не совпадает с ожидаемым {expected}")
    if SHARE_DIR.is_symlink():
        raise StepError(f"отказ: {SHARE_DIR} — симлинк, удаляю только настоящий каталог")
    if SHARE_DIR.resolve() == Path.home().resolve():
        raise StepError("отказ: каталог совпадает с домашним — не удаляю")


def cmd_remove(runner: Runner, _args) -> int:
    if not is_installed():
        log("INFO", "удалять нечего: сервис не установлен")
        return EXIT_OK
    if not confirm(f"Удалить сервис {SERVICE_TITLE}, venv и каталог {SHARE_DIR}? [y/N]:", False):
        log("INFO", "удаление отменено")
        return EXIT_OK
    _guard_share_dir()
    runner.run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], mutates=True, check=False)
    log("INFO", "сервис остановлен и отключён")
    runner.remove_file(str(UNIT))
    log("INFO", f"удалён {UNIT}")
    runner.rmtree(SHARE_DIR)
    log("INFO", f"удалён каталог {SHARE_DIR}")
    runner.run(["systemctl", "--user", "daemon-reload"], mutates=True, check=False)
    log("INFO", "демонтаж завершён")
    return EXIT_OK


def cmd_run(_runner: Runner, args) -> int:
    """Ручной запуск шевелителя (для отладки; сервис использует свой файл)."""
    if args.interval <= 0:
        log("ERR", "--interval должен быть положительным")
        return EXIT_ARGS
    min_x, min_y = args.min_xy
    max_x, max_y = args.max_xy
    if min_x > max_x or min_y > max_y:
        log("ERR", "--min-xy не должен превышать --max-xy")
        return EXIT_ARGS
    try:
        import pyautogui  # ty: ignore[unresolved-import]
    except ImportError:
        log("ERR", "нет pyautogui — запустите install (создаст venv с pyautogui)")
        return EXIT_ERR
    pyautogui.FAILSAFE = True
    print(
        f"Двигаю мышь каждые {args.interval} с в x=[{min_x}, {max_x}], "
        f"y=[{min_y}, {max_y}]. Ctrl+C для остановки."
    )
    try:
        while True:
            pyautogui.moveTo(random.randint(min_x, max_x), random.randint(min_y, max_y))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nОстановлено.")
    return EXIT_OK


COMMANDS = {
    "install": cmd_install,
    "start": cmd_start,
    "stop": cmd_stop,
    "restart": cmd_restart,
    "status": cmd_status,
    "logs": cmd_logs,
    "remove": cmd_remove,
    "run": cmd_run,
}


# ---------------------------------------------------------------------------
# CLI и main
# ---------------------------------------------------------------------------
def build_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mouse_mover_setup.py",
        description=(
            "Установщик и менеджер user-сервиса «шевелитель мышки» (Mouse Mover): "
            "двигает курсор против AFK-статуса."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="режим без изменений в системе")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install", help="установить и запустить сервис")
    sub.add_parser("start", help="запустить сервис")
    sub.add_parser("stop", help="остановить сервис")
    sub.add_parser("restart", help="перезапустить сервис")
    sub.add_parser("status", help="показать состояние сервиса")
    logs = sub.add_parser("logs", help=f"последние {LOG_LINES} строк лога")
    logs.add_argument("-f", "--follow", action="store_true", help="следить за логом")
    sub.add_parser("remove", help="удалить сервис, venv и каталог")
    runp = sub.add_parser("run", help="ручной запуск шевелителя (для сервиса, отладка)")
    runp.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="секунд между движениями (по умолчанию: %(default)s)",
    )
    runp.add_argument(
        "--min-xy",
        nargs=2,
        type=int,
        default=[100, 100],
        metavar=("MIN_X", "MIN_Y"),
        help="левый верхний угол области (по умолчанию: %(default)s)",
    )
    runp.add_argument(
        "--max-xy",
        nargs=2,
        type=int,
        default=[1000, 1000],
        metavar=("MAX_X", "MAX_Y"),
        help="правый нижний угол области (по умолчанию: %(default)s)",
    )
    return parser


def main(argv: list[str]) -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 — проверка для реального запуска, не для линтера
        print(f"[ERR] требуется Python 3.10+ (найден {sys.version_info[0]}.{sys.version_info[1]})")
        return EXIT_ARGS

    parser = build_argparse()
    args = parser.parse_args(argv)
    runner = Runner(dry_run=args.dry_run)
    rc = EXIT_OK
    try:
        if args.command is None:
            rc = cmd_default(runner, args)
        else:
            rc = COMMANDS[args.command](runner, args)
    except StepError as exc:
        log("ERR", str(exc))
        rc = EXIT_ERR
    except KeyboardInterrupt:
        log("WARN", "прервано (Ctrl-C)")
        rc = EXIT_SIGINT
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


# ===========================================================================
# AGENT NOTES (кратко, для правок агентом; больше агентского не добавлять)
# ---------------------------------------------------------------------------
# ПРОВЕРКИ: python3 -m py_compile mouse_mover_setup.py;
#   ruff check --output-format=concise mouse_mover_setup.py;
#   ty check --output-format=concise mouse_mover_setup.py.
#   smoke (все безопасны, 0 следов):
#     ./mouse_mover_setup.py --help
#     ./mouse_mover_setup.py --dry-run install   # план: venv, pip, файлы, systemctl
#     ./mouse_mover_setup.py --dry-run           # не установлен -> план install
#     ./mouse_mover_setup.py status              # read-only
#     ./mouse_mover_setup.py --dry-run logs
#     printf 'n\n' | ./mouse_mover_setup.py --dry-run remove
#     ./mouse_mover_setup.py run --help          # headless
#     ./mouse_mover_setup.py run                 # без pyautogui -> подсказка
# ---------------------------------------------------------------------------
# ИНВАРИАНТЫ: MOVER_SOURCE (записываемый автономный шевелитель) и cmd_run
#   (ручной запуск) ДЕРЖАТЬ СИНХРОННЫМИ по логике/дефолтам/текстам; удаление
#   каталога — rmtree только для зафиксированного SHARE_DIR (проверка
#   _guard_share_dir обязательна); venv и pip — только внутри
#   ~/.local/share/mouse-mover; root не требуется и не проверяется; remove
#   всегда требует подтверждения (дефолт НЕТ); Runner — единственное место
#   outward-эффектов: в dry-run он печатает их и ничего не делает.
# ===========================================================================
