#!/usr/bin/env python3
"""telemt_setup.py — установщик/менеджер MTProto-прокси telemt (один экземпляр, telemt).

НАЗНАЧЕНИЕ
    Установка, обновление и сопровождение MTProto-прокси telemt (https://github.com/telemt/telemt)
    на серверах Debian/Ubuntu: пользователь telemt, каталоги /opt/telemt и /etc/telemt,
    конфиг /etc/telemt/telemt.toml, systemd-юнит telemt.service, правило ufw со вставкой
    блока rate-limit (xt_recent) в /etc/ufw/before.rules, сетевой тюнинг 99-tg-telemt.conf
    (bbr/fq). Скрипт также умеет менять домен-маску, печатать клиентскую ссылку и удалять всё
    созданное. Опционально ставит systemd-таймер ежедневного автообновления (03:00).

КОМАНДЫ (CLI)
    python3 telemt_setup.py [глобальные опции] [сабкоманда]
    Глобальные опции: --dry-run, --yes, --quiet, --port N, --domain D.
    Сабкоманды (без сабкоманды открывается интерактивное меню):
        install      полная установка (вопросы: порт, домен, автообновление, сводка)
        update       проверка и замена бинарника по GitHub (--yes не спрашивает, --quiet —
                     только результат; при отсутствии новой версии exit 0)
        restart      перезапуск сервиса telemt (таймер не трогает)
        set-domain   смена домена-маски, рестарт, новая ссылка (профиль client_mss не меняет)
        link         печать клиентской ссылки tg://proxy?...
        info         статус, версия, порт, домен, client_mss, ufw, таймер, конфиг
        remove       полный демонтаж (по умолчанию НЕ подтверждается через --yes)
        menu         интерактивное меню

ПРИМЕРЫ
    sudo python3 telemt_setup.py                       # меню
    sudo python3 telemt_setup.py install               # интерактивная установка
    sudo python3 telemt_setup.py install --port 5223 --domain www.apple.com
    sudo python3 telemt_setup.py --dry-run install     # план без изменений в системе
    printf '5223\nwww.apple.com\ny\n' | sudo python3 telemt_setup.py install
    sudo python3 telemt_setup.py info
    sudo python3 telemt_setup.py link
    sudo python3 telemt_setup.py set-domain --domain www.cloudflare.com
    sudo python3 telemt_setup.py update --yes --quiet
    sudo python3 telemt_setup.py remove

АВТООБНОВЛЕНИЕ (systemd-таймер)
    При install (вопрос «Установить автообновление по расписанию (03:00 ночи)?», дефолт «да»)
    скрипт копирует сам себя в /usr/local/bin/telemt_setup.py и ставит два юнита:
      /etc/systemd/system/telemt-update.service — oneshot, ExecStart=/usr/bin/env python3
          /usr/local/bin/telemt_setup.py update --yes --quiet, User=root, Nice=10;
      /etc/systemd/system/telemt-update.timer   — OnCalendar=*-*-* 03:00:00, Persistent=true,
          RandomizedDelaySec=900, Unit=telemt-update.service, WantedBy=timers.target.
    Затем daemon-reload и systemctl enable --now telemt-update.timer. Если исходный файл
    недоступен — WARN, таймер не ставится. update без новой версии завершается exit 0
    («обновление не требуется»), поэтому ночной прогон не трогает сервис впустую.
    remove останавливает и удаляет таймер и оба юнита; restart таймер не затрагивает.

ПРОФИЛЬ client_mss
    server.client_mss выбирается по порту: порт 5223 → "" (мягкий профиль, ниже пинг), любой
    другой порт → "tspu". Источник: docs/Config_params телемта (допустимы "", "extreme-low",
    "tspu", "2in8", число 88..4096) и боевой runbook сообщества. set-domain порт не меняет,
    поэтому профиль сохраняется; info показывает текущее client_mss.

DRY-RUN
    --dry-run переводит все мутации в режим «логируй-не-делай»: команды печатаются с префиксом
    [dry-run], файлы пишутся в зеркало (временный каталог), а не в /etc. Реально выполняются
    только чтения: /etc/os-release, конфиг, /etc/ufw/before.rules, наличия путей, команды чтения
    (ss, systemctl is-active/enabled, ufw status, telemt --version) и сетевой GET GitHub API.
    Скачивание релиза в dry-run не выполняется. Скрипт в dry-run работает без root на любой
    Linux (ОС-гейт выдаёт предупреждение и продолжает), следов вне временного зеркала не
    оставляет (зеркало удаляется при выходе). Итоговая строка: сколько мутаций запланировано.

ОГРАНИЧЕНИЯ
    - Поддерживаются только Debian/Ubuntu (определяется по ID/ID_LIKE в /etc/os-release).
      В обычном режиме другая ОС → exit 4; в dry-run — предупреждение и продолжение.
    - Обычный режим требует root (иначе подсказка с sudo и exit 3).
    - Управляются только systemd и ufw; при их отсутствии шаги ufw/systemd пропускаются
      с предупреждением.
    - Один экземпляр сервиса (telemt); мультиинстансы вне области.
    - Python 3.10+; модуль tomllib (Python 3.11+) при отсутствии делает чтение конфига
      недоступным с предупреждением.

ЧТО СКРИПТ МЕНЯЕТ В СИСТЕМЕ (полная установка)
    /etc/passwd, /etc/group      — системный пользователь/группа telemt
    /opt/telemt                  — рабочий каталог (telemt:telemt)
    /etc/telemt/telemt.toml     — конфиг (0640 root:telemt), секрет генерируется один раз
    /bin/telemt                  — бинарник из релиза GitHub, проверенный по sha256
    /etc/systemd/system/telemt.service — systemd-юнит, enable --now
    /usr/local/bin/telemt_setup.py — копия скрипта для таймера автообновления (если включён)
    /etc/systemd/system/telemt-update.service, telemt-update.timer — автообновление (если включено)
    /etc/ufw/before.rules        — блок rate-limit между маркерами (с бэкапом)
    /etc/modules-load.d/...      — xt_recent, tcp_bbr/sch_fq
    /etc/sysctl.d/99-tg-telemt.conf — сетевой тюнинг (bbr/fq), sysctl --system
    ufw allow <порт>/tcp и ufw reload
    Удаление убирает всё созданное: сервисы, таймер, юниты, бинарник, каталоги,
    sysctl/modules-load файлы, правило ufw, блок rate-limit (по маркерам), пользователя telemt.
    Что ОСТАЁТСЯ после remove (осознанно):
      - бэкапы /etc/ufw/before.rules.bak-* (для восстановления);
      - загруженные модули ядра (xt_recent, tcp_bbr, sch_fq) — выгрузятся при перезагрузке;
      - значения sysctl (bbr/fq/keepalive) — действуют до перезагрузки, файл уже удалён;
      - правила ufw, добавленные вручную пользователем, скрипт не трогает.

Exit-коды: 0 успех; 1 ошибка операции; 2 неверные аргументы/ввод; 3 отказ пользователя;
4 неподдерживаемая ОС; 130 Ctrl-C.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - 3.10 fallback
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
DEFAULT_PORT = 5223
DEFAULT_DOMAIN = "www.apple.com"
SERVICE = "telemt"
SERVICE_USER = "telemt"
BIN = "/bin/telemt"
ETC_DIR = "/etc/telemt"
OPT_DIR = "/opt/telemt"
UNIT = f"/etc/systemd/system/{SERVICE}.service"
CFG = f"{ETC_DIR}/telemt.toml"
BEFORE_RULES = "/etc/ufw/before.rules"
SYSCTL_FILE = "/etc/sysctl.d/99-tg-telemt.conf"
MODULES_RECENT = "/etc/modules-load.d/telemt-recent.conf"
MODULES_BBR = "/etc/modules-load.d/telemt-bbr.conf"
API_URL = "https://api.github.com/repos/telemt/telemt/releases/latest"
ASSET = "telemt-x86_64-linux-gnu.tar.gz"
DEFAULT_TAG = "3.5.8"  # фолбэк, если GitHub API недоступен (install не падает целиком)
RELEASE_URL_TMPL = "https://github.com/telemt/telemt/releases/download/{tag}/{asset}"
MARK_BEGIN = "# BEGIN telemt_setup rate-limit"
MARK_END = "# END telemt_setup rate-limit"
IP_PLACEHOLDER = "SERVER_IP"

# Автообновление (systemd-таймер) — Задача B.
SELF_PATH = "/usr/local/bin/telemt_setup.py"
UPDATE_SERVICE_NAME = "telemt-update.service"
UPDATE_TIMER_NAME = "telemt-update.timer"
UPDATE_SERVICE = f"/etc/systemd/system/{UPDATE_SERVICE_NAME}"
UPDATE_TIMER = f"/etc/systemd/system/{UPDATE_TIMER_NAME}"
MSS_PORT_SOFT = 5223  # на этом порту мягкий профиль client_mss = ""

EXIT_OK = 0
EXIT_ERR = 1
EXIT_ARGS = 2
EXIT_REFUSED = 3
EXIT_OS = 4
EXIT_SIGINT = 130

# ANSI-цвета (INFO/WARN/ERR/DRY)
C_INFO = "36"
C_WARN = "33"
C_ERR = "31"
C_DRY = "35"

_YES = False  # глобальный режим --yes (все подтверждения = да, вопросы = дефолты)
_QUIET = False  # глобальный режим --quiet (только результат: INFO/DRY подавляются)


# ---------------------------------------------------------------------------
# Ошибки
# ---------------------------------------------------------------------------
class StepError(Exception):
    """Ошибка операции (subprocess/файлы) — exit 1."""


class NetError(Exception):
    """Сетевая ошибка — exit 1."""


class VerifyError(Exception):
    """Ошибка проверки sha256 — exit 1."""


class Abort(Exception):
    """Отказ пользователя / исчерпание попыток ввода — exit 3."""


class ArgError(Exception):
    """Неверный аргумент CLI — exit 2."""


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
    """Единая точка логирования. Секреты здесь печатать запрещено.
    --quiet подавляет информационные уровни (INFO/DRY), оставляя WARN/ERR."""
    if _QUIET and level in ("INFO", "DRY"):
        return
    if level == "INFO":
        prefix = c(C_INFO, "[INFO]")
    elif level == "WARN":
        prefix = c(C_WARN, "[WARN]")
    elif level == "ERR":
        prefix = c(C_ERR, "[ERR] ")
    elif level == "DRY":
        prefix = c(C_DRY, "[dry-run]")
    else:
        prefix = f"[{level}]"
    print(f"{prefix} {msg}", flush=True)


YES_WORDS = {"y", "yes", "да", "д", "1", "true"}
NO_WORDS = {"n", "no", "нет", "н", "0", "false"}


def ask(prompt: str, default, validator) -> object:
    """Единая точка вопросов. --yes → дефолт без печати; пустой ввод → дефолт;
    EOF → до 5 попыток → Abort; исчерпание попыток при неверном вводе → Abort."""
    if _YES:
        ok, value, err = validator(str(default))
        if not ok:
            raise ArgError(f"значение по умолчанию недопустимо для {prompt!r}: {err}")
        return value
    attempts = 0
    while attempts < 5:
        sys.stdout.write(c(C_INFO, prompt) + " ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            log("WARN", "ввод недоступен (EOF)")
            attempts += 1
            continue
        raw = line.strip()
        if raw == "":
            raw = "" if default is None else str(default)
        ok, value, err = validator(raw)
        if ok:
            return value
        log("WARN", err or "неверное значение")
        attempts += 1
    raise Abort(f"превышено число попыток ввода ({prompt!r})")


def confirm(prompt: str, default: bool = True) -> bool:
    """Подтверждение. --yes → default (небезопасные дефолты = False)."""
    if _YES:
        return default
    attempts = 0
    while attempts < 5:
        sys.stdout.write(c(C_INFO, prompt) + " ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            log("WARN", "ввод недоступен (EOF)")
            attempts += 1
            continue
        raw = line.strip().lower()
        if raw == "":
            return default
        if raw in YES_WORDS:
            return True
        if raw in NO_WORDS:
            return False
        log("WARN", "ответьте да/нет (y/n)")
        attempts += 1
    raise Abort("превышено число попыток ввода")


def pause() -> None:
    """Пауза после пункта меню — не подтверждение, --yes игнорирует."""
    sys.stdout.write(c(C_INFO, "Enter — продолжить") + " ")
    sys.stdout.flush()
    sys.stdin.readline()


# Маскировка значения секрета в печатаемом контенте (dry-run-дамп): строка `tg = "..."`.
_TG_LINE_RE = re.compile(r"^(\s*tg\s*=\s*).*$")


def redact_secret_line(line: str) -> str:
    """Заменить значение строки `tg = ...` на `"<redacted>"` (для логов/дампа)."""
    match = _TG_LINE_RE.match(line)
    if match:
        return match.group(1) + '"<redacted>"'
    return line


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def build_link(ip: str, port: int, secret_hex: str, domain: str) -> str:
    """Собрать клиентскую ссылку (домен кодируется hex от UTF-8 байт)."""
    dom_hex = domain.encode("utf-8").hex()
    return f"tg://proxy?server={ip}&port={port}&secret=ee{secret_hex}{dom_hex}"


def ssh_hint() -> str:
    """Подсказка для запуска с sudo."""
    return (
        f"sudo python3 {sys.argv[0]} " + " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else f"sudo python3 {sys.argv[0]}"
    )


def detect_ip() -> str | None:
    """Попытка определить публичный IPv4; None при неудаче или loopback."""
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        return None
    if not ip or ip.startswith("127."):
        return None
    return ip


def resolve_ip() -> str:
    """IP для ссылки: автоопределение, иначе ручной ввод (M2).

    В неинтерактивном режиме (--yes) и при недоступном вводе — плейсхолдер с WARN.
    """
    ip = detect_ip()
    if ip:
        return ip
    if _YES:
        log(
            "WARN",
            "не удалось определить публичный IP — в ссылке использован плейсхолдер "
            f"{IP_PLACEHOLDER} (--yes не запрашивает ввод); замените его на адрес сервера",
        )
        return IP_PLACEHOLDER
    try:
        value = ask(
            "Не удалось определить публичный IP. Введите IP/хост сервера:",
            None,
            validate_ip,
        )
    except Abort:
        log(
            "WARN",
            f"IP не введён — в ссылке использован плейсхолдер {IP_PLACEHOLDER}; "
            "замените его на адрес сервера",
        )
        return IP_PLACEHOLDER
    assert isinstance(value, str)
    return value


_IPV4_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_HOST_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$"
)


def validate_domain(value: str) -> tuple[bool, object, str | None]:
    """Валидатор домена (Q2)."""
    domain = value.strip().rstrip(".")
    if not domain:
        return False, None, "домен не может быть пустым"
    if len(domain) > 253:
        return False, None, "домен длиннее 253 символов"
    pattern = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9]))+$"
    if not re.match(pattern, domain):
        return False, None, "неверный формат домена (пример: www.apple.com)"
    for label in domain.split("."):
        if len(label) > 63:
            return False, None, "метка домена длиннее 63 символов"
    return True, domain, None


def validate_ip(value: str) -> tuple[bool, object, str | None]:
    """Валидатор IP/хоста для ссылки (M2): IPv4 или доменное имя."""
    addr = value.strip()
    if not addr:
        return False, None, "адрес не может быть пустым"
    if _IPV4_RE.match(addr):
        if all(0 <= int(part) <= 255 for part in addr.split(".")):
            return True, addr, None
        return False, None, "неверный IPv4-адрес (октет вне 0–255)"
    if len(addr) <= 253 and _HOST_RE.match(addr):
        return True, addr, None
    return False, None, "укажите IPv4-адрес (1.2.3.4) или имя хоста"


def validate_port(value: str) -> tuple[bool, int | None, str | None]:
    """Валидатор порта (Q1)."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False, None, "порт должен быть целым числом"
    if not 1 <= port <= 65535:
        return False, None, "порт должен быть в диапазоне 1–65535"
    return True, port, None


def _port_warning(port: int) -> str | None:
    if port in (22, 80, 443, 53):
        return f"порт {port} относится к системным/стандартным — использование возможно, но не рекомендуется"
    return None


def client_mss_profile(port: int) -> str:
    """Профиль client_mss по порту: 5223 → мягкий "" (ниже пинг), иначе "tspu".

    Источник: docs/Config_params телемта (допустимы "", "extreme-low", "tspu",
    "2in8", число 88..4096) и боевой runbook сообщества: на 5223 мягкий профиль,
    tspu — для 443/нестандартных портов. Значение подставляется в конфиг.
    """
    return "" if port == MSS_PORT_SOFT else "tspu"


def format_mss(value: object) -> str:
    """Человекочитаемое значение client_mss для info."""
    if value is None:
        return "неизвестно (конфиг не читается)"
    if value == "":
        return '"" (мягкий профиль)'
    if isinstance(value, int):
        return str(value)
    return f'"{value}"'


def _ephemeral_range() -> tuple[int, int] | None:
    """Диапазон эфемерных портов ядра (ip_local_port_range) или None."""
    try:
        parts = Path("/proc/sys/net/ipv4/ip_local_port_range").read_text().split()
        return int(parts[0]), int(parts[1])
    except (OSError, ValueError, IndexError):
        return None


def _ephemeral_warning(port: int) -> str | None:
    """WARN, если выбранный порт попадает в диапазон эфемерных (гонка bind)."""
    rng = _ephemeral_range()
    if rng and rng[0] <= port <= rng[1]:
        return (
            f"порт {port} попадает в диапазон эфемерных портов ядра "
            f"({rng[0]}–{rng[1]}) — теоретическая гонка при bind; лучше выбрать "
            "порт вне диапазона"
        )
    return None


# ---------------------------------------------------------------------------
# Состояние
# ---------------------------------------------------------------------------
@dataclass
class State:
    installed: bool = False
    version: str | None = None
    port: int | None = None
    domain: str | None = None
    service_active: bool = False
    service_enabled: bool = False
    ufw_present: bool = False
    ufw_active: bool = False
    sysctl_file: bool = False
    module_files: list[str] = field(default_factory=list)
    user_exists: bool = False
    before_rules_block: bool = False


# ---------------------------------------------------------------------------
# Runner — единственная точка outward-эффектов
# ---------------------------------------------------------------------------
class Runner:
    """Все мутации проходят здесь. В dry-run только логирует и пишет в зеркало."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.mutations = 0
        self.tmp_mirror: Path | None = None
        if dry_run:
            self.tmp_mirror = Path(tempfile.mkdtemp(prefix="telemt_setup_mirror_"))

    # -- служебное ---------------------------------------------------------
    def _count(self) -> None:
        self.mutations += 1

    def _mirror(self, path: str | Path) -> Path | None:
        if self.tmp_mirror is None:
            return None
        target = self.tmp_mirror / str(path).lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def dry_note(self, text: str) -> None:
        """Пометка только для dry-run (в обычном режиме молчит)."""
        if self.dry_run:
            log("DRY", text)

    # -- команды -----------------------------------------------------------
    def run(
        self, cmd: list[str], *, check: bool = True, mutates: bool = False, timeout: int = 60
    ) -> subprocess.CompletedProcess:
        if mutates and self.dry_run:
            self._count()
            log("DRY", " ".join(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError:
            if check:
                raise StepError(f"команда не найдена: {cmd[0]}")
            return subprocess.CompletedProcess(cmd, 127, "", f"команда не найдена: {cmd[0]}")
        except subprocess.TimeoutExpired:
            if check:
                raise StepError(f"таймаут команды: {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 124, "", "timeout")
        if check and cp.returncode != 0:
            detail = cp.stderr.strip() or cp.stdout.strip()
            raise StepError(
                f"команда завершилась с кодом {cp.returncode}: {' '.join(cmd)}\n{detail}"
            )
        return cp

    def mkdir(self, path: str, owner: str | None = None, mode: int = 0o750) -> None:
        if self.dry_run:
            self._count()
            log("DRY", f"mkdir -p {path} (mode={oct(mode)}, owner={owner or '-'})")
        else:
            Path(path).mkdir(parents=True, exist_ok=True)
            os.chmod(path, mode)
            if owner:
                self._chown(path, owner)
        if self.dry_run:
            mirror = self._mirror(path)
            if mirror is not None:
                mirror.mkdir(parents=True, exist_ok=True)

    def write_file(
        self,
        path: str,
        content: str,
        *,
        mode: int = 0o600,
        owner: str | None = None,
        dump: bool = True,
    ) -> bool:
        if self.dry_run:
            self._count()
            log("DRY", f"запись файла {path} (mode={oct(mode)}, owner={owner or '-'})")
            if dump:
                for line in content.rstrip("\n").splitlines():
                    log("DRY", "    " + redact_secret_line(line))
            mirror = self._mirror(path)
            if mirror is not None:
                mirror.write_text(content, encoding="utf-8")
                os.chmod(mirror, mode)
            return True
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        os.chmod(target, mode)
        if owner:
            self._chown(path, owner)
        return True

    def remove(self, path: str) -> None:
        target = Path(path)
        if self.dry_run:
            mirror = self._mirror(path)
            mirror_exists = mirror is not None and (mirror.exists() or mirror.is_symlink())
            if not target.exists() and not target.is_symlink() and not mirror_exists:
                log("DRY", f"rm -rf {path} (отсутствует — пропуск)")
                return
            self._count()
            log("DRY", f"rm -rf {path}")
            if mirror is not None and (mirror.exists() or mirror.is_symlink()):
                if mirror.is_dir() and not mirror.is_symlink():
                    shutil.rmtree(mirror, ignore_errors=True)
                else:
                    mirror.unlink(missing_ok=True)
            return
        if target.is_symlink() or target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    def download(self, url: str, dest: str | Path) -> bool:
        if self.dry_run:
            self._count()
            log("DRY", f"GET {url} -> {dest}")
            mirror = self._mirror(str(dest))
            if mirror is not None:
                mirror.write_text("")
            return True
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as response, open(target, "wb") as handle:
                shutil.copyfileobj(response, handle)
        except (urllib.error.URLError, OSError) as exc:
            raise NetError(f"не удалось скачать {url}: {exc}") from exc
        return True

    def unpack_binary(self, tar_path: str | Path, dest_dir: str | Path) -> Path:
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        self.run(["tar", "-xzf", str(tar_path), "-C", str(dest_dir)], mutates=True)
        candidate = Path(dest_dir) / "telemt"
        if self.dry_run:
            return candidate
        if candidate.exists():
            return candidate
        found = sorted(Path(dest_dir).rglob("telemt"))
        if not found:
            raise StepError("в архиве не найден бинарник telemt")
        return found[0]

    def replace_binary(self, src: str | Path) -> bool:
        if self.dry_run:
            self._count()
            log("DRY", f"замена бинарника {src} -> {BIN} (chmod 0755 + setcap)")
            mirror = self._mirror(BIN)
            if mirror is not None:
                mirror.write_text("")
            return True
        if not Path(src).exists():
            raise StepError(f"исходный бинарник не найден: {src}")
        shutil.copy2(src, BIN)
        os.chmod(BIN, 0o755)
        cp = self.run(["setcap", "cap_net_bind_service=+ep", BIN], check=False, mutates=True)
        if cp.returncode != 0:
            log("WARN", f"setcap не применился для {BIN}: {cp.stderr.strip() or cp.stdout.strip()}")
        return True

    def edit_before_rules(self, port: int, op: str, *, reload: bool = True) -> None:
        """Правка /etc/ufw/before.rules: вставка/удаление блока по маркерам.

        reload=False (ufw неактивен) — файл правится, но `ufw reload` не вызывается.
        """
        path = Path(BEFORE_RULES)
        if not path.exists():
            log("WARN", f"{BEFORE_RULES} не найден — правка пропущена")
            return
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            log("WARN", f"не удалось прочитать {BEFORE_RULES}: {exc}")
            return
        lines = text.splitlines()

        if op == "insert":
            if MARK_BEGIN in text:
                log(
                    "INFO",
                    "блок rate-limit уже присутствует в before.rules — пропуск (идемпотентно)",
                )
                return
            anchor = None
            for idx, line in enumerate(lines):
                if "ufw-before-input" in line and "RELATED,ESTABLISHED" in line:
                    anchor = idx
                    break
            if anchor is None:
                log(
                    "WARN",
                    "якорная строка conntrack не найдена — вставка блока rate-limit пропущена",
                )
                return
            block = self._rate_limit_block(port)
            lines.insert(anchor + 1, block.rstrip("\n"))
            new_text = "\n".join(lines) + "\n"
        elif op == "remove":
            begin = end = None
            for idx, line in enumerate(lines):
                if MARK_BEGIN in line:
                    begin = idx
                elif MARK_END in line and begin is not None:
                    end = idx
                    break
            if begin is None or end is None:
                log("INFO", "блок rate-limit в before.rules не найден — удалять нечего")
                return
            del lines[begin : end + 1]
            new_text = "\n".join(lines) + "\n"
        else:
            raise StepError(f"неизвестная операция правки before.rules: {op}")

        backup = f"{BEFORE_RULES}.bak-{int(time.time())}"
        if self.dry_run:
            self._count()
            log("DRY", f"бэкап {BEFORE_RULES} -> {backup}")
            if op == "insert":
                log("DRY", f"вставка в {BEFORE_RULES} после якорной строки conntrack:")
                for line in self._rate_limit_block(port).splitlines():
                    log("DRY", "    " + line)
            else:
                log("DRY", f"удаление блока {MARK_BEGIN} … {MARK_END} из {BEFORE_RULES}")
            mirror = self._mirror(BEFORE_RULES)
            if mirror is not None:
                mirror.write_text(new_text, encoding="utf-8")
        else:
            shutil.copy2(BEFORE_RULES, backup)
            log("INFO", f"бэкап before.rules: {backup}")
            path.write_text(new_text, encoding="utf-8")
            log("INFO", f"{BEFORE_RULES} обновлён ({op})")
        if reload:
            self.run(["ufw", "reload"], check=False, mutates=True)
        else:
            log("INFO", "ufw reload пропущен (ufw неактивен) — правило применится после включения")

    @staticmethod
    def _rate_limit_block(port: int) -> str:
        return (
            f"{MARK_BEGIN}\n"
            f"# Ограничение новых TCP-соединений на порт {port} (rate-limit через xt_recent)\n"
            f"-A ufw-before-input -p tcp --dport {port} -m conntrack --ctstate NEW "
            f"-m recent --set --name TELEMT\n"
            f"-A ufw-before-input -p tcp --dport {port} -m conntrack --ctstate NEW "
            f"-m recent --update --seconds 1 --hitcount 30 --name TELEMT -j DROP\n"
            f"{MARK_END}\n"
        )

    @staticmethod
    def _chown(path: str, owner: str) -> None:
        user, _, group = owner.partition(":")
        shutil.chown(path, user or None, group or None)

    def summary(self) -> str:
        return f"DRY-RUN завершён: {self.mutations} мутаций запланировано, 0 выполнено"

    def cleanup(self) -> None:
        if self.tmp_mirror is not None and self.tmp_mirror.exists():
            shutil.rmtree(self.tmp_mirror, ignore_errors=True)


# ---------------------------------------------------------------------------
# Checks — только чтения
# ---------------------------------------------------------------------------
class Checks:
    def __init__(self, runner: Runner):
        self.runner = runner

    @staticmethod
    def os_supported() -> tuple[bool, str]:
        """Проверка ОС по /etc/os-release. Возврат (ok, описание)."""
        path = Path("/etc/os-release")
        if not path.exists():
            return False, "файл /etc/os-release не найден"
        values: dict[str, str] = {}
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    values[key.strip()] = val.strip().strip('"')
        except OSError as exc:
            return False, f"не удалось прочитать /etc/os-release: {exc}"
        ident = values.get("ID", "").lower()
        like = values.get("ID_LIKE", "").lower()
        pretty = values.get("PRETTY_NAME", ident or "неизвестно")
        if "debian" in ident or "ubuntu" in ident or "debian" in like:
            return True, pretty
        return False, pretty

    def _quiet(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return self.runner.run(cmd, check=False, timeout=15)

    def is_root(self) -> bool:
        return os.geteuid() == 0

    def user_exists(self) -> bool:
        return self._quiet(["id", "-u", SERVICE_USER]).returncode == 0

    def systemd_present(self) -> bool:
        return Path("/run/systemd/system").is_dir()

    def telemt_version(self) -> str | None:
        if not Path(BIN).exists():
            return None
        cp = self._quiet([BIN, "--version"])
        match = re.search(r"\d+\.\d+\.\d+", cp.stdout or cp.stderr)
        return match.group(0) if match else None

    def port_owner(self, port: int) -> str | None:
        cp = self._quiet(["ss", "-tlnp"])
        for line in cp.stdout.splitlines():
            if f":{port} " in line or line.rstrip().endswith(f":{port}"):
                match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                if match:
                    return f"процесс {match.group(1)} (PID {match.group(2)})"
                return "процесс (PID неизвестен, нужен root для деталей)"
        return None

    def port_free(self, port: int) -> bool:
        cp = self._quiet(["ss", "-tln"])
        if cp.returncode != 0:
            return True  # ss недоступен — считаем свободным (мягко)
        for line in cp.stdout.splitlines():
            if line.rstrip().endswith(f":{port}") or f":{port} " in line:
                return False
        return True

    def ufw_state(self) -> tuple[bool, bool]:
        if shutil.which("ufw") is None:
            return False, False
        cp = self._quiet(["ufw", "status"])
        return True, ("Status: active" in cp.stdout)

    def firewalld_active(self) -> bool:
        cp = self._quiet(["systemctl", "is-active", "firewalld"])
        return cp.stdout.strip() == "active"

    def update_timer_present(self) -> bool:
        return Path(UPDATE_TIMER).exists()

    def update_timer_enabled(self) -> bool:
        cp = self._quiet(["systemctl", "is-enabled", UPDATE_TIMER_NAME])
        return cp.stdout.strip() in ("enabled", "enabled-runtime")

    def update_timer_next(self) -> str | None:
        """Строка из systemctl list-timers (NEXT/LEFT/…) или None."""
        cp = self._quiet(["systemctl", "list-timers", UPDATE_TIMER_NAME, "--no-pager"])
        for line in cp.stdout.splitlines():
            stripped = line.strip()
            if stripped and UPDATE_TIMER_NAME in stripped and "NEXT" not in stripped:
                return " ".join(stripped.split())
        return None

    def service_active(self) -> bool:
        cp = self._quiet(["systemctl", "is-active", SERVICE])
        return cp.stdout.strip() == "active"

    def service_enabled(self) -> bool:
        cp = self._quiet(["systemctl", "is-enabled", SERVICE])
        return cp.stdout.strip() in ("enabled", "enabled-runtime")

    def installed(self) -> bool:
        return Path(BIN).exists() and Path(CFG).exists() and Path(UNIT).exists()

    def tlsfront_exists(self, domain: str | None) -> bool:
        if not domain:
            return False
        return Path(OPT_DIR, "tlsfront", f"{domain}.json").exists()

    def read_config(self) -> tuple[int | None, str | None, str | None]:
        """(port, domain, secret) из конфига через tomllib; при ошибке — (None, None, None)."""
        if tomllib is None or not Path(CFG).exists():
            return None, None, None
        try:
            data = tomllib.loads(Path(CFG).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, None, None
        port = data.get("server", {}).get("port")
        domain = data.get("censorship", {}).get("tls_domain")
        users = data.get("access", {}).get("users", {})
        secret = next(iter(users.values()), None) if isinstance(users, dict) else None
        if not isinstance(port, int):
            port = None
        return port, domain, secret

    def read_client_mss(self) -> object:
        """Текущее значение server.client_mss из конфига (или None, если не прочитать)."""
        if tomllib is None or not Path(CFG).exists():
            return None
        try:
            data = tomllib.loads(Path(CFG).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data.get("server", {}).get("client_mss")

    def before_rules_block(self) -> bool:
        path = Path(BEFORE_RULES)
        if not path.exists():
            return False
        try:
            return MARK_BEGIN in path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

    def collect(self) -> State:
        present, active = self.ufw_state()
        port, domain, _ = self.read_config()
        modules = [f for f in (MODULES_RECENT, MODULES_BBR) if Path(f).exists()]
        state = State(
            installed=self.installed(),
            version=self.telemt_version(),
            port=port,
            domain=domain,
            service_active=self.service_active(),
            service_enabled=self.service_enabled(),
            ufw_present=present,
            ufw_active=active,
            sysctl_file=Path(SYSCTL_FILE).exists(),
            module_files=modules,
            user_exists=self.user_exists(),
            before_rules_block=self.before_rules_block(),
        )
        return state


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------
class GitHub:
    def __init__(self, runner: Runner):
        self.runner = runner

    def latest(self) -> tuple[str, str, str | None]:
        """(tag, asset_url, sha256_url). raises NetError."""
        try:
            with urllib.request.urlopen(API_URL, timeout=10) as response:
                data = json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise NetError(
                f"Не удалось получить данные с GitHub (timeout/DNS/HTTP): {exc}"
            ) from exc
        tag = data.get("tag_name")
        asset_url = None
        sha_url = None
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name == ASSET:
                asset_url = asset.get("browser_download_url")
            elif name == ASSET + ".sha256":
                sha_url = asset.get("browser_download_url")
        if not tag or not asset_url:
            raise NetError(f"в релизе GitHub не найден ожидаемый файл {ASSET}")
        return tag, asset_url, sha_url

    def resolve(self, fallback_tag: str) -> tuple[str, str, str | None]:
        """(tag, asset_url, sha_url): через API, а при недоступности — по фолбэк-тегу.

        Позволяет install не падать целиком, когда GitHub API недоступен: ссылка
        на ассет строится напрямую по тегу (стандартная схема релизов GitHub).
        """
        try:
            return self.latest()
        except NetError as exc:
            log(
                "WARN",
                f"не удалось проверить актуальность ({exc}); ставлю {fallback_tag}",
            )
            asset_url = RELEASE_URL_TMPL.format(tag=fallback_tag, asset=ASSET)
            return fallback_tag, asset_url, asset_url + ".sha256"

    def fetch_release(
        self,
        tmpdir: str | Path,
        asset_url: str | None = None,
        sha_url: str | None = None,
    ) -> tuple[Path, str | None]:
        """Скачать архив и .sha256. В dry-run — только логи; expected=None.

        Если asset_url передан — используется он, иначе берётся из GitHub API.
        """
        if asset_url is None:
            _, asset_url, sha_url = self.latest()
        tar_path = Path(tmpdir) / ASSET
        expected: str | None = None
        self.runner.download(asset_url, tar_path)
        if sha_url:
            self.runner.dry_note(f"проверить sha256 по {sha_url}")
            sha_path = Path(tmpdir) / (ASSET + ".sha256")
            self.runner.download(sha_url, sha_path)
            if not self.runner.dry_run:
                try:
                    expected = sha_path.read_text(encoding="utf-8").split()[0]
                except (OSError, IndexError) as exc:
                    raise VerifyError(f"не удалось прочитать контрольную сумму: {exc}") from exc
        return tar_path, expected

    def verify_sha256(self, path: str | Path, expected: str | None) -> None:
        if expected is None:
            self.runner.dry_note("sha256 не проверяется (dry-run / нет контрольной суммы)")
            return
        digest = hashlib.sha256()
        try:
            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise VerifyError(f"не удалось прочитать скачанный файл: {exc}") from exc
        actual = digest.hexdigest()
        if actual != expected.lower():
            raise VerifyError("скачанный файл не совпал со сборкой на GitHub (sha256 mismatch)")


# ---------------------------------------------------------------------------
# Шаблоны (конфиг, юнит, sysctl)
# ---------------------------------------------------------------------------
def config_template(port: int, domain: str, secret: str) -> str:
    mss = client_mss_profile(port)
    return (
        "[general]\n"
        "use_middle_proxy = false\n"
        "\n"
        "[general.modes]\n"
        "classic = false\n"
        "secure = false\n"
        "tls = true\n"
        "\n"
        "[server]\n"
        f"port = {port}\n"
        f'client_mss = "{mss}"\n'
        "\n"
        # Свой менеджер фаервола telemt требует CAP_NET_ADMIN и nft/iptables —
        # у нас фильтрацию ведёт ufw, сервис работает без CAP_NET_ADMIN.
        "[server.conntrack_control]\n"
        "inline_conntrack_control = false\n"
        "\n"
        "[server.api]\n"
        "enabled = true\n"
        'listen = "127.0.0.1:9091"\n'
        'whitelist = ["127.0.0.1/32"]\n'
        "\n"
        "[censorship]\n"
        f'tls_domain = "{domain}"\n'
        "mask = true\n"
        "tls_emulation = true\n"
        'tls_front_dir = "tlsfront"\n'
        "mask_port = 443\n"
        "\n"
        "[access.users]\n"
        f'tg = "{secret}"\n'
    )


def unit_template() -> str:
    return (
        "[Unit]\n"
        "Description=Telemt MTProto Proxy (telemt)\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={SERVICE_USER}\n"
        f"Group={SERVICE_USER}\n"
        f"WorkingDirectory={OPT_DIR}\n"
        f"ExecStart={BIN} {CFG}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "LimitNOFILE=65536\n"
        "NoNewPrivileges=true\n"
        "AmbientCapabilities=CAP_NET_BIND_SERVICE\n"
        "CapabilityBoundingSet=CAP_NET_BIND_SERVICE\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def update_service_template() -> str:
    return (
        "[Unit]\n"
        "Description=Telemt auto-update\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart=/usr/bin/env python3 {SELF_PATH} update --yes --quiet\n"
        "User=root\n"
        "Nice=10\n"
    )


def update_timer_template() -> str:
    return (
        "[Unit]\n"
        "Description=Telemt auto-update timer (daily 03:00)\n"
        "\n"
        "[Timer]\n"
        "OnCalendar=*-*-* 03:00:00\n"
        "Persistent=true\n"
        "RandomizedDelaySec=900\n"
        f"Unit={UPDATE_SERVICE_NAME}\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def sysctl_template() -> str:
    return (
        "# telemt_setup: сетевой тюнинг для MTProto-прокси\n"
        "net.core.default_qdisc = fq\n"
        "net.ipv4.tcp_congestion_control = bbr\n"
        "net.core.somaxconn = 1024\n"
        "net.ipv4.tcp_max_syn_backlog = 4096\n"
        "net.ipv4.tcp_syncookies = 1\n"
        "net.ipv4.tcp_fin_timeout = 30\n"
        "net.ipv4.tcp_keepalive_time = 120\n"
        "net.ipv4.ip_local_port_range = 10000 65000\n"
    )


MODULES_RECENT_CONTENT = "xt_recent\n"
MODULES_BBR_CONTENT = "tcp_bbr\nsch_fq\n"


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------
class Installer:
    def __init__(
        self,
        runner: Runner,
        checks: Checks,
        state: State,
        port: int,
        domain: str,
        timer: bool = True,
    ):
        self.runner = runner
        self.checks = checks
        self.state = state
        self.port = port
        self.domain = domain
        self.timer = timer
        self.github = GitHub(runner)

    def summary(self) -> str:
        mss = client_mss_profile(self.port)
        mss_display = f'"{mss}"' if mss else '"" (мягкий профиль, ниже пинг)'
        timer_line = (
            "автообновление  : ежедневно в 03:00 (systemd timer)"
            if self.timer
            else "автообновление  : не устанавливать"
        )
        return (
            "Сводка установки:\n"
            f"  порт прокси     : {self.port}\n"
            f"  client_mss      : {mss_display}\n"
            f"  домен-маска     : {self.domain}\n"
            f"  конфиг          : {CFG}\n"
            f"  бинарник        : {BIN}\n"
            f"  сервис          : {SERVICE} (systemd, enable --now)\n"
            f"  {timer_line}\n"
            f"  скрипт в /usr/local/bin: {SELF_PATH}\n"
            f"  рабочий каталог : {OPT_DIR}\n"
            f"  ufw             : allow {self.port}/tcp + rate-limit в before.rules"
        )

    def _log_mss(self) -> None:
        mss = client_mss_profile(self.port)
        display = "«» (мягкий профиль)" if not mss else f"«{mss}»"
        log("INFO", f"профиль client_mss для порта {self.port}: {display}")

    def install_timer(self) -> None:
        """Скопировать скрипт в /usr/local/bin и поставить systemd-таймер (Задача B)."""
        r = self.runner
        try:
            self_text = Path(__file__).read_text(encoding="utf-8")
        except OSError as exc:
            log("WARN", f"не удалось прочитать собственный скрипт ({exc}) — таймер не ставится")
            return
        if Path(SELF_PATH).exists() and not confirm(
            f"{SELF_PATH} уже существует. Перезаписать? [да]:", True
        ):
            log("WARN", f"{SELF_PATH} не перезаписан — таймер не ставится")
            return
        r.write_file(SELF_PATH, self_text, mode=0o755, owner="root:root", dump=False)
        log("INFO", f"скрипт скопирован: {SELF_PATH}")
        r.write_file(UPDATE_SERVICE, update_service_template(), mode=0o644, owner="root:root")
        r.write_file(UPDATE_TIMER, update_timer_template(), mode=0o644, owner="root:root")
        if self.checks.systemd_present():
            r.run(["systemctl", "daemon-reload"], mutates=True)
            cp = r.run(
                ["systemctl", "enable", "--now", UPDATE_TIMER_NAME],
                check=False,
                mutates=True,
            )
            if cp.returncode != 0:
                log(
                    "WARN",
                    f"не удалось включить таймер {UPDATE_TIMER_NAME}: "
                    f"{cp.stderr.strip() or cp.stdout.strip()}",
                )
            else:
                log("INFO", f"таймер {UPDATE_TIMER_NAME} включён (ежедневно в 03:00)")
        else:
            log("WARN", "systemd не обнаружен — юниты таймера записаны, но не включены")

    def install(self) -> None:
        r = self.runner

        # Шаг 1. Пользователь
        log("INFO", "=== Шаг 1/9: системный пользователь telemt ===")
        if self.checks.user_exists():
            log("INFO", f"пользователь {SERVICE_USER} уже существует")
        else:
            r.run(
                ["useradd", "-r", "-U", "-s", "/usr/sbin/nologin", "-d", OPT_DIR, SERVICE_USER],
                mutates=True,
            )
            log("INFO", f"создан системный пользователь {SERVICE_USER}")

        # Шаг 2. Каталоги
        log("INFO", "=== Шаг 2/9: каталоги ===")
        r.mkdir(OPT_DIR, owner=f"{SERVICE_USER}:{SERVICE_USER}", mode=0o750)
        r.mkdir(ETC_DIR, owner=f"root:{SERVICE_USER}", mode=0o750)

        # Шаг 3. Секрет и конфиг
        log("INFO", "=== Шаг 3/9: конфиг и секрет ===")
        secret = os.urandom(16).hex()
        r.dry_note("секрет сгенерирован (значение не печатается)")
        r.write_file(
            CFG,
            config_template(self.port, self.domain, secret),
            mode=0o640,
            owner=f"root:{SERVICE_USER}",
        )
        log("INFO", f"конфиг записан: {CFG}")
        self._log_mss()

        # Шаг 4. Бинарник (при недоступности GitHub — фолбэк-тег, install не падает целиком)
        log("INFO", "=== Шаг 4/9: бинарник telemt ===")
        tag, asset_url, sha_url = self.github.resolve(DEFAULT_TAG)
        log("INFO", f"версия релиза: {tag}")
        try:
            with tempfile.TemporaryDirectory(prefix="telemt_setup_") as tmpdir:
                tar_path, expected = self.github.fetch_release(tmpdir, asset_url, sha_url)
                self.github.verify_sha256(tar_path, expected)
                bin_src = r.unpack_binary(tar_path, Path(tmpdir) / "extract")
                r.replace_binary(bin_src)
            log("INFO", f"бинарник установлен: {BIN}")
        except NetError as exc:
            log(
                "WARN",
                f"не удалось скачать бинарник ({exc}) — установка продолжена без замены {BIN}; "
                "повторите позже командой update",
            )

        # Шаг 5. systemd
        log("INFO", "=== Шаг 5/9: systemd-юнит ===")
        r.write_file(UNIT, unit_template(), mode=0o644, owner="root:root")
        if self.checks.systemd_present():
            r.run(["systemctl", "daemon-reload"], mutates=True)
            cp = r.run(["systemctl", "enable", "--now", SERVICE], check=False, mutates=True)
            if cp.returncode != 0:
                log(
                    "WARN",
                    f"systemctl enable --now {SERVICE} не удался: {cp.stderr.strip() or cp.stdout.strip()}",
                )
        else:
            log("WARN", "systemd не обнаружен — сервис не запущен, проверьте запуск вручную")

        # Шаг 6. Автообновление
        log("INFO", "=== Шаг 6/9: автообновление по расписанию ===")
        if self.timer:
            self.install_timer()
        else:
            log("INFO", "автообновление не запрошено — таймер не устанавливается")

        # Шаг 7. ufw
        log("INFO", "=== Шаг 7/9: ufw и защита от перебора ===")
        present, active = self.checks.ufw_state()
        if not present:
            if self.checks.firewalld_active():
                log(
                    "WARN",
                    "обнаружен firewalld — добавьте порт вручную: "
                    f"firewall-cmd --permanent --add-port={self.port}/tcp && firewall-cmd --reload",
                )
            else:
                log(
                    "WARN",
                    "ufw не установлен — правило и rate-limit не применяются. "
                    f"Добавьте вручную: sudo ufw allow {self.port}/tcp",
                )
        elif active:
            r.run(["ufw", "allow", f"{self.port}/tcp"], mutates=True)
            loaded = r.run(["modprobe", "xt_recent"], check=False, mutates=True)
            r.write_file(MODULES_RECENT, MODULES_RECENT_CONTENT, mode=0o644, owner="root:root")
            if loaded.returncode != 0:
                log("WARN", "модуль xt_recent не загрузился — rate-limit в before.rules не пишется")
            else:
                r.edit_before_rules(self.port, "insert")
        else:
            # ufw установлен, но неактивен: правило фиксируем в конфиге, reload не делаем.
            r.run(["ufw", "allow", f"{self.port}/tcp"], mutates=True)
            log(
                "WARN",
                "ufw неактивен — правило добавлено в конфиг ufw, но не действует; "
                "включите: sudo ufw enable",
            )
            loaded = r.run(["modprobe", "xt_recent"], check=False, mutates=True)
            r.write_file(MODULES_RECENT, MODULES_RECENT_CONTENT, mode=0o644, owner="root:root")
            if loaded.returncode == 0:
                r.edit_before_rules(self.port, "insert", reload=False)

        # Шаг 8. Сетевой тюнинг
        log("INFO", "=== Шаг 8/9: сетевой тюнинг (bbr/fq) ===")
        r.write_file(SYSCTL_FILE, sysctl_template(), mode=0o644, owner="root:root")
        r.write_file(MODULES_BBR, MODULES_BBR_CONTENT, mode=0o644, owner="root:root")
        r.run(["modprobe", "tcp_bbr"], check=False, mutates=True)
        r.run(["modprobe", "sch_fq"], check=False, mutates=True)
        r.run(["sysctl", "--system"], check=False, mutates=True)

        # Шаг 9. Проверки и ссылка
        log("INFO", "=== Шаг 9/9: проверка и итог ===")
        if self.checks.service_active():
            log("INFO", f"сервис {SERVICE}: active")
        else:
            log(
                "WARN",
                f"сервис {SERVICE} не в состоянии active (проверьте: systemctl status {SERVICE})",
            )
        if self.checks.tlsfront_exists(self.domain):
            log("INFO", "TLS-сертификат (tlsfront) на месте")
        else:
            log("WARN", "tlsfront-сертификат пока не создан (сервис сформирует его при работе)")
        if self.timer and (self.runner.dry_run or self.checks.update_timer_present()):
            log("INFO", f"таймер автообновления: установлен ({UPDATE_TIMER_NAME})")
        elif self.timer:
            log("WARN", "таймер автообновления не установлен (см. предупреждения выше)")
        ip = resolve_ip()
        print(build_link(ip, self.port, secret, self.domain))


# ---------------------------------------------------------------------------
# Updater
# ---------------------------------------------------------------------------
class Updater:
    def __init__(self, runner: Runner, checks: Checks, state: State):
        self.runner = runner
        self.checks = checks
        self.state = state
        self.github = GitHub(runner)

    def check(self) -> tuple[str, str]:
        """(latest_tag, decision in {'update','same'})."""
        tag, _, _ = self.github.latest()
        current = self.checks.telemt_version()
        if current is None:
            log("WARN", "текущая версия telemt не определена — будет выполнена установка/замена")
            return tag, "update"
        if current == tag:
            return tag, "same"
        log("INFO", f"текущая версия {current}, доступна {tag}")
        return tag, "update"

    def update(self) -> None:
        tag, decision = self.check()
        if decision == "same":
            if _YES:
                # Таймер/--yes: молча выходим без переустановки (важно для автообновления).
                print(f"telemt update: обновление не требуется (версия {tag})")
                return
            if not confirm(f"Версия {tag} уже установлена. Переустановить? [нет]:", False):
                print(f"telemt update: обновление не требуется (версия {tag})")
                return
        with tempfile.TemporaryDirectory(prefix="telemt_setup_") as tmpdir:
            # Скачивание и проверка ДО остановки сервиса (сокращаем даунтайм).
            tar_path, expected = self.github.fetch_release(tmpdir)
            self.github.verify_sha256(tar_path, expected)
            bin_src = self.runner.unpack_binary(tar_path, Path(tmpdir) / "extract")
            # --yes (в т.ч. таймер) никогда не спрашивает; интерактивно — подтверждение.
            if not _YES and not confirm(
                "Обновление остановит сервис и разорвёт активные подключения. Продолжить? [нет]:",
                False,
            ):
                raise Abort("обновление отменено")
            r = self.runner
            r.run(["systemctl", "stop", SERVICE], mutates=True)
            r.replace_binary(bin_src)
            r.run(["systemctl", "start", SERVICE], mutates=True)
        new_version = self.checks.telemt_version()
        print(
            f"telemt update: бинарник заменён, версия релиза {tag}"
            + (f", сейчас {new_version}" if new_version else "")
        )
        if not new_version:
            log("WARN", "не удалось подтвердить версию после обновления")


# ---------------------------------------------------------------------------
# DomainChanger
# ---------------------------------------------------------------------------
class DomainChanger:
    def __init__(self, runner: Runner, checks: Checks, state: State):
        self.runner = runner
        self.checks = checks
        self.state = state

    def change(self, new_domain: str) -> None:
        port, _old_domain, secret = self.checks.read_config()
        if port is None or secret is None:
            log("WARN", "конфиг не читается (отсутствует или битый TOML)")
            if not confirm(
                "Файл конфига будет перезаписан шаблоном (порт = 5223, новый секрет). Продолжить? [нет]:",
                False,
            ):
                raise Abort("смена домена отменена")
            port = DEFAULT_PORT
            secret = os.urandom(16).hex()
            self.runner.dry_note("секрет перегенерирован (значение не печатается)")
        if not confirm(
            "Смена домена изменит конфиг и перезапустит сервис (активные клиенты отключатся). Продолжить? [нет]:",
            False,
        ):
            raise Abort("смена домена отменена")
        self.runner.write_file(
            CFG, config_template(port, new_domain, secret), mode=0o640, owner=f"root:{SERVICE_USER}"
        )
        log("INFO", f"домен-маска изменена на {new_domain}")
        self.runner.run(["systemctl", "restart", SERVICE], mutates=True)
        if self.checks.tlsfront_exists(new_domain):
            log("INFO", "tlsfront-сертификат для нового домена на месте")
        else:
            log("WARN", "tlsfront для нового домена появится после первых подключений")
        ip = resolve_ip()
        print(build_link(ip, port, secret, new_domain))


# ---------------------------------------------------------------------------
# Remover
# ---------------------------------------------------------------------------
class Remover:
    def __init__(self, runner: Runner, checks: Checks, state: State):
        self.runner = runner
        self.checks = checks
        self.state = state

    def list_items(self) -> str:
        st = self.state
        items = []
        if self.checks.systemd_present():
            items.append(f"остановка и disable сервиса {SERVICE}")
        if Path(UNIT).exists():
            items.append(f"юнит {UNIT}")
        if self.checks.update_timer_present() or Path(UPDATE_SERVICE).exists():
            items.append(
                f"автообновление: disable таймера {UPDATE_TIMER_NAME} + юниты "
                f"{UPDATE_TIMER} и {UPDATE_SERVICE}"
            )
        if Path(SELF_PATH).exists() and Path(SELF_PATH).resolve() != Path(__file__).resolve():
            items.append(f"копия скрипта {SELF_PATH}")
        if Path(BIN).exists():
            items.append(f"бинарник {BIN}")
        if Path(ETC_DIR).exists():
            items.append(f"каталог {ETC_DIR} (вместе с конфигом)")
        if Path(OPT_DIR).exists():
            items.append(f"каталог {OPT_DIR} (tlsfront, рабочие данные)")
        if Path(SYSCTL_FILE).exists():
            items.append(f"sysctl-файл {SYSCTL_FILE}")
        for f in (MODULES_RECENT, MODULES_BBR):
            if Path(f).exists():
                items.append(f"modules-load {f}")
        if st.before_rules_block:
            items.append(f"блок rate-limit в {BEFORE_RULES}")
        if st.ufw_present:
            items.append(f"правило ufw allow {st.port or DEFAULT_PORT}/tcp")
        items.append(f"системный пользователь {SERVICE_USER} (userdel)")
        if not items:
            items.append("(ничего не найдено — система уже чиста)")
        return "\n".join("  - " + it for it in items)

    def _clear_xt_recent(self) -> None:
        """Best-effort очистка счётчиков xt_recent (только root и не dry-run)."""
        r = self.runner
        names = [f"mtp{self.state.port}"] if self.state.port is not None else []
        names.append("TELEMT")
        for name in names:
            path = f"/proc/net/xt_recent/{name}"
            if not Path(path).exists():
                continue
            if r.dry_run or not self.checks.is_root():
                r.dry_note(f"очистка {path} (echo - > {path})")
                continue
            try:
                with open(path, "w", encoding="ascii") as proc_file:
                    proc_file.write("-\n")
                log("OK", f"очищен {path}")
            except OSError as exc:
                log("WARN", f"не удалось очистить {path}: {exc}")

    def _residue_report(self) -> None:
        """Самопроверка после remove: печать остатков; остатки = WARNING, не ошибка."""
        r = self.runner
        print("Самопроверка остатков после демонтажа:")
        leftovers: list[str] = []
        for path in (
            BIN,
            CFG,
            UNIT,
            UPDATE_TIMER,
            UPDATE_SERVICE,
            SELF_PATH,
            SYSCTL_FILE,
            MODULES_RECENT,
            MODULES_BBR,
            ETC_DIR,
            OPT_DIR,
        ):
            exists = Path(path).exists()
            print(f"  {'ЕСТЬ' if exists else 'нет '}  {path}")
            if exists:
                leftovers.append(path)
        block = self.checks.before_rules_block()
        print(f"  {'ЕСТЬ' if block else 'нет '}  блок rate-limit в {BEFORE_RULES}")
        if block:
            leftovers.append("блок before.rules")
        if self.checks.systemd_present():
            cp = r.run(["systemctl", "list-unit-files", "telemt*", "--no-pager"], check=False)
            units = [
                ln
                for ln in cp.stdout.splitlines()
                if ln.strip() and ln.split()[0].startswith("telemt")
            ]
            if units:
                print("  systemctl list-unit-files 'telemt*':")
                for line in units:
                    print(f"    {line}")
                    leftovers.append(line.split()[0])
            cp = r.run(
                ["systemctl", "list-timers", UPDATE_TIMER_NAME, "--no-pager"],
                check=False,
            )
            timers = [ln for ln in cp.stdout.splitlines() if UPDATE_TIMER_NAME in ln]
            if timers:
                print("  systemctl list-timers 'telemt-update.timer':")
                for line in timers:
                    print(f"    {' '.join(line.split())}")
                    leftovers.append(UPDATE_TIMER_NAME)
        self._clear_xt_recent()
        if leftovers:
            log("WARN", "обнаружены остатки: " + ", ".join(leftovers))
        else:
            log("INFO", "остатков не обнаружено — система чиста")

    def run(self) -> None:
        r = self.runner
        if self.checks.systemd_present():
            r.run(["systemctl", "stop", SERVICE], check=False, mutates=True)
            r.run(["systemctl", "disable", SERVICE], check=False, mutates=True)
            r.run(["systemctl", "disable", "--now", UPDATE_TIMER_NAME], check=False, mutates=True)
        r.remove(UNIT)
        r.remove(UPDATE_TIMER)
        r.remove(UPDATE_SERVICE)
        if Path(SELF_PATH).resolve() != Path(__file__).resolve():
            r.remove(SELF_PATH)
        r.remove(BIN)
        r.remove(ETC_DIR)
        r.remove(OPT_DIR)
        r.remove(SYSCTL_FILE)
        r.remove(MODULES_RECENT)
        r.remove(MODULES_BBR)
        if self.state.port is None:
            log("WARN", "порт из конфига не читается — правило ufw allow не удаляется")
        else:
            r.run(
                ["ufw", "--force", "delete", "allow", f"{self.state.port}/tcp"],
                check=False,
                mutates=True,
            )
        if self.state.before_rules_block:
            # reload один раз в конце (ниже), а не внутри правки before.rules.
            r.edit_before_rules(self.state.port or DEFAULT_PORT, "remove", reload=False)
        if self.checks.systemd_present():
            r.run(["systemctl", "daemon-reload"], mutates=True)
        present, active = self.checks.ufw_state()
        if present and active:
            r.run(["ufw", "reload"], check=False, mutates=True)
        cp = r.run(["userdel", SERVICE_USER], check=False, mutates=True)
        if cp.returncode == 0:
            log("OK", f"системный пользователь {SERVICE_USER} удалён")
        elif cp.returncode == 6:
            log("INFO", f"пользователь {SERVICE_USER} уже отсутствует")
        else:
            log("WARN", f"userdel {SERVICE_USER}: {cp.stderr.strip() or cp.returncode}")
        log("INFO", "демонтаж завершён")
        self._residue_report()


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------
def cmd_install(runner: Runner, checks: Checks, args) -> int:
    state = checks.collect()
    if args.port is not None:
        ok, _v, err = validate_port(str(args.port))
        if not ok:
            raise ArgError(f"--port: {err}")
        if not checks.port_free(args.port):
            raise ArgError(
                f"--port: порт {args.port} занят ({checks.port_owner(args.port) or 'процесс неизвестен'})"
            )
        eph = _ephemeral_warning(args.port)
        if eph:
            log("WARN", eph)
    if args.domain is not None:
        ok, _v, err = validate_domain(args.domain)
        if not ok:
            raise ArgError(f"--domain: {err}")

    if state.installed:
        # Q4: уже установлен — предложить обновление (сводка Q3 не повторяется).
        if not confirm(
            f"Уже установлен (v{state.version or '?'}, порт {state.port or '?'}, "
            f"домен {state.domain or '?'}). Обновить? [да]:",
            True,
        ):
            raise Abort("отменено пользователем")
        Updater(runner, checks, state).update()
        return EXIT_OK

    # D9: чужой/старый бинарник на месте при неполной установке — подтверждение перезаписи.
    if Path(BIN).exists() and not confirm(
        f"{BIN} уже существует (не наш или от старой установки). Перезаписать? [да]:",
        True,
    ):
        raise Abort("установка отменена: существующий бинарник не перезаписан")

    default_port = args.port if args.port is not None else DEFAULT_PORT
    default_domain = args.domain if args.domain is not None else DEFAULT_DOMAIN

    def _port_validator(value: str) -> tuple[bool, int | None, str | None]:
        ok, port, err = validate_port(value)
        if not ok or port is None:
            return False, None, err
        if not checks.port_free(port):
            owner = checks.port_owner(port) or "процесс неизвестен"
            return False, None, f"порт {port} занят ({owner})"
        warning = _port_warning(port)
        if warning:
            log("WARN", warning)
        eph = _ephemeral_warning(port)
        if eph:
            log("WARN", eph)
        return True, port, None

    port = ask(f"Порт прокси [{default_port}]:", default_port, _port_validator)
    domain = ask(f"Домен-маска [{default_domain}]:", default_domain, validate_domain)
    assert isinstance(port, int) and isinstance(domain, str)
    timer = confirm("Установить автообновление по расписанию (03:00 ночи)? [да]:", True)
    installer = Installer(runner, checks, state, port, domain, timer)
    if not confirm(installer.summary() + "\nПодтвердить сводку? [да]:", True):
        raise Abort("установка отменена")
    installer.install()
    log("INFO", "установка завершена")
    return EXIT_OK


def cmd_update(runner: Runner, checks: Checks, _args) -> int:
    state = checks.collect()
    if not state.installed:
        log("WARN", f"{BIN} не установлен — сначала выполните install")
        return EXIT_ERR
    Updater(runner, checks, state).update()
    timer = "установлен" if checks.update_timer_present() else "нет"
    print(f"таймер автообновления: {timer}")
    return EXIT_OK


def cmd_restart(runner: Runner, checks: Checks, _args) -> int:
    state = checks.collect()
    if not state.installed:
        log("WARN", f"{SERVICE} не установлен")
        return EXIT_ERR
    if not confirm(
        f"Перезапуск {SERVICE} разорвёт активные подключения клиентов. Продолжить? [нет]:", False
    ):
        raise Abort("перезапуск отменён")
    runner.run(["systemctl", "restart", SERVICE], mutates=True)
    log("INFO", f"сервис {SERVICE} перезапущен")
    return EXIT_OK


def cmd_set_domain(runner: Runner, checks: Checks, args) -> int:
    state = checks.collect()
    if not state.installed:
        log("WARN", f"{SERVICE} не установлен — смена домена невозможна")
        return EXIT_ERR
    if args.domain is not None:
        ok, _v, err = validate_domain(args.domain)
        if not ok:
            raise ArgError(f"--domain: {err}")
    default_domain = args.domain if args.domain is not None else (state.domain or DEFAULT_DOMAIN)
    domain = ask(f"Домен-маска [{default_domain}]:", default_domain, validate_domain)
    assert isinstance(domain, str)
    DomainChanger(runner, checks, state).change(domain)
    return EXIT_OK


def cmd_link(runner: Runner, checks: Checks, _args) -> int:
    state = checks.collect()
    if not state.installed:
        log("WARN", f"{SERVICE} не установлен — ссылка недоступна")
        return EXIT_ERR
    port, domain, secret = checks.read_config()
    if port is None or domain is None or secret is None:
        log("WARN", "конфиг не читается — не удалось построить ссылку")
        return EXIT_ERR
    ip = resolve_ip()
    url = build_link(ip, port, secret, domain)
    print(url)
    # Сверка с локальным API — недоступность тихо игнорируем.
    try:
        with urllib.request.urlopen("http://127.0.0.1:9091/v1/users", timeout=3) as response:
            json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return EXIT_OK


def cmd_info(runner: Runner, checks: Checks, _args) -> int:
    state = checks.collect()
    _port, _domain, secret = checks.read_config()
    print("Информация о telemt:")
    print(f"  установлен      : {'да' if state.installed else 'нет'}")
    print(f"  версия          : {state.version or 'неизвестно'}")
    print(
        f"  сервис {SERVICE:8}: {'active' if state.service_active else 'inactive'} / "
        f"{'enabled' if state.service_enabled else 'disabled'}"
    )
    print(f"  порт            : {state.port if state.port is not None else '—'}")
    print(f"  домен-маска     : {state.domain or '—'}")
    print(f"  client_mss      : {format_mss(checks.read_client_mss())}")
    print(f"  конфиг          : {CFG} ({'читается' if secret is not None else 'не читается'})")
    print(f"  tlsfront        : {'есть' if checks.tlsfront_exists(state.domain) else 'нет'}")
    print(
        f"  ufw             : {'есть' if state.ufw_present else 'нет'}, "
        f"{'active' if state.ufw_active else 'inactive'}"
    )
    print(f"  блок в before.rules: {'есть' if state.before_rules_block else 'нет'}")
    print(f"  sysctl-файл     : {'есть' if state.sysctl_file else 'нет'}")
    mods = ", ".join(state.module_files) if state.module_files else "нет"
    print(f"  modules-load    : {mods}")
    print(f"  пользователь {SERVICE_USER}: {'есть' if state.user_exists else 'нет'}")
    if checks.update_timer_present():
        if runner.dry_run:
            print(f"  таймер обновл.  : установлен ({UPDATE_TIMER}, {UPDATE_SERVICE})")
        else:
            timer_state = "enabled" if checks.update_timer_enabled() else "disabled"
            nxt = checks.update_timer_next()
            print(f"  таймер обновл.  : {timer_state}" + (f"; next: {nxt}" if nxt else ""))
    else:
        print("  таймер обновл.  : нет")
    return EXIT_OK


def cmd_remove(runner: Runner, checks: Checks, _args) -> int:
    state = checks.collect()
    if not state.installed:
        log("INFO", "удалять нечего: прокси не установлен")
        return EXIT_OK
    remover = Remover(runner, checks, state)
    listing = remover.list_items()
    if not confirm("Будет удалено:\n" + listing + "\nПродолжить? [нет]:", False):
        if _YES:
            raise Abort(
                "удаление не выполнено: --yes не подтверждает опасные операции; "
                "подтвердите интерактивно"
            )
        raise Abort("удаление отменено")
    remover.run()
    return EXIT_OK


COMMANDS = {
    "install": cmd_install,
    "update": cmd_update,
    "restart": cmd_restart,
    "set-domain": cmd_set_domain,
    "link": cmd_link,
    "info": cmd_info,
    "remove": cmd_remove,
}


def run_command(name: str, runner: Runner, checks: Checks, args) -> int:
    return COMMANDS[name](runner, checks, args)


# ---------------------------------------------------------------------------
# Меню
# ---------------------------------------------------------------------------
class Menu:
    def __init__(self, runner: Runner, checks: Checks, args):
        self.runner = runner
        self.checks = checks
        self.args = args

    def _header(self, state: State) -> str:
        if state.installed:
            status = f"установлено v{state.version or '?'}, порт {state.port or '?'}, домен {state.domain or '?'}"
        else:
            status = "не установлено"
        return f"telemt_setup — {status}"

    def run(self) -> int:
        while True:
            state = self.checks.collect()
            print()
            print(c(C_INFO, "=" * 60))
            print(c(C_INFO, self._header(state)))
            print(c(C_INFO, "=" * 60))
            # Меню зависит от состояния: до установки показываем только
            # установку и состояние системы; после — только управление.
            if state.installed:
                items = [
                    ("Информация", "info"),
                    ("Сменить домен-маску", "set-domain"),
                    ("Показать ссылку", "link"),
                    ("Обновить", "update"),
                    ("Перезапустить сервис", "restart"),
                    ("Удалить", "remove"),
                ]
            else:
                items = [
                    ("Установить", "install"),
                    ("Состояние системы (среда, ufw, порты)", "info"),
                ]
            for number, (label, _cmd) in enumerate(items, start=1):
                print(f" {number}) {label}")
            exit_number = len(items) + 1
            print(f" {exit_number}) Выход")
            sys.stdout.write(c(C_INFO, "Выбор:") + " ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if line == "":
                return EXIT_OK
            choice = line.strip().lower()
            if choice in ("", str(exit_number), "q", "quit", "exit", "выход"):
                return EXIT_OK
            command = next(
                (
                    cmd
                    for number, (_label, cmd) in enumerate(items, start=1)
                    if choice == str(number)
                ),
                None,
            )
            if command is None:
                log("WARN", "неизвестный пункт меню")
                continue
            try:
                run_command(command, self.runner, self.checks, self.args)
            except Abort as exc:
                log("WARN", str(exc))
            except (StepError, NetError, VerifyError) as exc:
                log("ERR", str(exc))
            except ArgError as exc:
                log("ERR", str(exc))
            except KeyboardInterrupt:
                log("WARN", "прервано")
            pause()


# ---------------------------------------------------------------------------
# CLI и main
# ---------------------------------------------------------------------------
def build_argparse() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="режим без изменений: только логирование команд",
    )
    common.add_argument(
        "--yes",
        action="store_true",
        default=argparse.SUPPRESS,
        help="все подтверждения = да, вопросы = значения по умолчанию",
    )
    common.add_argument("--port", type=int, default=argparse.SUPPRESS, help="порт прокси (Q1)")
    common.add_argument("--domain", default=argparse.SUPPRESS, help="домен-маска (Q2)")
    common.add_argument(
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="минимум вывода: только результат (для таймера)",
    )

    parser = argparse.ArgumentParser(
        prog="telemt_setup.py",
        description="Установщик и менеджер MTProto-прокси telemt (экземпляр telemt).",
    )
    parser.add_argument("--dry-run", action="store_true", help="режим без изменений в системе")
    parser.add_argument("--yes", action="store_true", help="подтверждать все действия")
    parser.add_argument("--port", type=int, default=None, help="порт прокси")
    parser.add_argument("--domain", default=None, help="домен-маска")
    parser.add_argument("--quiet", action="store_true", help="минимум вывода (только результат)")
    sub = parser.add_subparsers(dest="command")
    for name in ("install", "update", "restart", "set-domain", "link", "info", "remove", "menu"):
        sub.add_parser(name, parents=[common])
    return parser


def main(argv: list[str]) -> int:
    global _YES, _QUIET

    if sys.version_info < (3, 10):  # noqa: UP036 — проверка для реального запуска, не для цели линтера
        print(f"[ERR] требуется Python 3.10+ (найден {sys.version_info[0]}.{sys.version_info[1]})")
        return EXIT_ARGS

    if tomllib is None:
        log(
            "WARN",
            "tomllib/tomli недоступен — чтение конфига невозможно (нужен Python 3.11+ или tomli)",
        )

    parser = build_argparse()
    args = parser.parse_args(argv)
    _YES = bool(getattr(args, "yes", False))
    _QUIET = bool(getattr(args, "quiet", False))

    ok_os, os_desc = Checks.os_supported()
    if not args.dry_run:
        if not ok_os:
            log("ERR", f"Поддерживаются Debian/Ubuntu (см. /etc/os-release). Обнаружено: {os_desc}")
            return EXIT_OS
        if os.geteuid() != 0:
            log("ERR", "Нужны root-права. Запустите:")
            print(f"    {ssh_hint()}")
            return EXIT_REFUSED
    else:
        if not ok_os:
            log("WARN", f"ОС {os_desc} не поддерживается — dry-run продолжается без изменений")
        if os.geteuid() != 0:
            log("WARN", "запуск без root в dry-run: мутации только логируются")

    runner = Runner(dry_run=args.dry_run)
    checks = Checks(runner)
    rc = EXIT_OK
    try:
        if args.command in (None, "menu"):
            rc = Menu(runner, checks, args).run()
        else:
            rc = run_command(args.command, runner, checks, args)
    except Abort as exc:
        log("WARN", str(exc))
        rc = EXIT_REFUSED
    except ArgError as exc:
        log("ERR", str(exc))
        rc = EXIT_ARGS
    except (StepError, NetError, VerifyError) as exc:
        log("ERR", str(exc))
        rc = EXIT_ERR
    except subprocess.CalledProcessError as exc:
        log("ERR", f"команда завершилась с кодом {exc.returncode}: {exc.cmd}")
        rc = EXIT_ERR
    except KeyboardInterrupt:
        log("WARN", "прервано пользователем (Ctrl-C)")
        rc = EXIT_SIGINT
    finally:
        if runner.dry_run:
            if runner.tmp_mirror is not None:
                print(c(C_DRY, runner.summary()))
                print(c(C_DRY, f"зеркало dry-run: {runner.tmp_mirror}"))
            else:
                print(c(C_DRY, runner.summary()))
        runner.cleanup()
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


# ===========================================================================
# AGENT NOTES (кратко, для правок агентом; больше агентского не добавлять)
# ---------------------------------------------------------------------------
# КАРТА: docstring ~1-95; константы ~119-165; лог/ask/confirm ~194-300;
#   валидаторы+client_mss_profile/format_mss/_ephemeral_warning ~305-457;
#   State ~462; Runner ~480-733 (единственная точка мутаций); Checks ~737-897
#   (read_config, read_client_mss, ufw_state, firewalld_active, update_timer_*);
#   GitHub ~901-984 (resolve — фолбэк по тегу); шаблоны ~988-1091; Installer
#   ~1095-1311; Updater ~1315-1367; DomainChanger ~1371-1406; Remover
#   ~1410-1549 (residue-report); cmd_* ~1553-1742; Menu ~1750; main ~1853.
# ---------------------------------------------------------------------------
# ПРОВЕРКИ: python3 -m py_compile telemt_setup.py; ruff check --output-format=
#   concise telemt_setup.py; ty check --output-format=concise telemt_setup.py.
#   smoke dry-run (без root, 0 следов):
#     printf '5223\nwww.apple.com\ny\ny\n' | ./telemt_setup.py --dry-run install
#     printf '8443\nwww.apple.com\ny\ny\n' | ./telemt_setup.py --dry-run install
#     ./telemt_setup.py --dry-run --yes install
#     printf 'n\n' | ./telemt_setup.py --dry-run install   # отказ от таймера
#     ./telemt_setup.py --dry-run --yes --quiet update
#     printf 'y\n' | ./telemt_setup.py --dry-run remove
#     ./telemt_setup.py --dry-run info; printf 'q\n' | ./telemt_setup.py --dry-run menu
# ---------------------------------------------------------------------------
# ИНВАРИАНТЫ DRY-RUN: Runner — единственная точка outward-эффектов; ветвление
#   только внутри Runner и ОС-гейта; мутации пишут зеркало tmp_mirror (mkdtemp,
#   удаляется в cleanup); никаких "if dry_run" в Installer/Updater/Remover/Menu.
# НЕ ТРОГАТЬ (безопасность): redact_secret_line (секрет не печатать); маркеры
#   MARK_BEGIN/MARK_END и вставку после якорной conntrack-строки; exit-коды
#   0/1/2/3/4/130; `--yes` НЕ подтверждает remove (Q5 default=нет); ufw reload
#   ровно один раз (install — в edit_before_rules, remove — в конце).
# ===========================================================================
