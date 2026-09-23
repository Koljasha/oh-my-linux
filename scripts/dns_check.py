#!/usr/bin/env python3
"""Проверка DNS-резолверов по KB AdGuard.

Источник списка провайдеров:
    https://adguard-dns.io/kb/ru/general/dns-providers/

Что делает:
    * скачивает страницу через curl и сам её парсит (stdlib html.parser);
    * собирает все "DNS, IPv4" и "DNS-over-HTTPS" записи;
    * раскладывает их по группам (см. GROUPS) — что проверяем, задаётся
      константами CHECK_GROUPS/TIMEOUT/PASSES/WORKERS либо флагами CLI;
    * РЕАЛЬНО проверяет DNS, а не просто гоняет curl:
        - IPv4 (порт 53): запрос A для example.com через dig/kdig, ждём
          status: NOERROR и минимум одну A-запись в ответе;
        - DoH: GET-запрос ?dns=, тело ответа парсим как DNS-сообщение:
          совпадение ID, flag QR, RCODE = 0, в ответе есть A-запись;
        - для DoH также обязательно content-type: application/dns-message
      (использующиеся "dig"/"kdig" и "curl" на старте проверяются на наличие);
    * прогресс по проходам, в конце две таблицы от лучшего к худшему:
      DNS, IPv4 и DNS-over-HTTPS;
    * дополнительные записи (CUSTOM_V4 / CUSTOM_DOH) — всегда проверяются,
      CUSTOM_DOH можно переопределить флагом --custom-doh или переменной
      окружения DNS_CHECK_CUSTOM_DOH.

Зависимости (внешние): curl, dig или kdig.
Точные названия пакетов под вашу систему скрипт подскажет при запуске.
Библиотек из pip не используется.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import html.parser
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# НАСТРОЙКИ — меняйте здесь
# ---------------------------------------------------------------------------

# Страница, откуда берём список провайдеров.
KB_URL = "https://adguard-dns.io/kb/ru/general/dns-providers/"

# Домен, которым проверяем резолвер (A-запись).
PROBE_NAME = "example.com"

# Короткие ключи групп для CHECK_GROUPS — полные имена в GROUPS ниже.
# Ключ принимается без учёта регистра.
GROUP_KEYS = {
    "STANDART": "обычные (стандарт, без фильтров)",
    "CHILD": "семья / дети / взрослый контент",
    "MALWARE": "защита / вредоносное ПО",
    "ADS": "реклама / трекеры",
}

# Какие группы проверяем (по ключам из GROUP_KEYS).
# Пустой кортеж () = все группы, у которых on=True.
# Пример: CHECK_GROUPS = ("STANDART",)
CHECK_GROUPS: tuple[str, ...] = ("STANDART", "MALWARE", "ADS")

# Секунд на одну попытку (у dig также +time=).
TIMEOUT = 2
# Сколько проходов по всему списку (в таблице видно каждый проход).
PASSES = 7
# Сколько запросов параллельно.
WORKERS = 25

# Для DoH требовать content-type: application/dns-message.
# Поставь False, если провайдер честно отвечает DNS, но отдаёт другой content-type.
DOH_REQUIRE_CTYPE = True

# Переменная окружения для переопределения CUSTOM_DOH без правки кода.
# Формат: записи через ";" или перевод строки, каждая — "Имя|URL",
# "Имя=URL" либо голый URL (именем станет сам URL).
CUSTOM_DOH_ENV_VAR = "DNS_CHECK_CUSTOM_DOH"


class DnsCheckError(Exception):
    """Фатальная ошибка проверки (нет инструментов, не скачалась страница и т.п.)."""


@dataclass(frozen=True, slots=True)
class Group:
    """Группа проверки. Вариант (подсекция) провайдера попадает в первую
    группу, чьё ключевое слово встречается в его заголовке. Всё остальное
    (включая провайдеров без подсекций) — в группу с catch_all=True."""

    name: str
    on: bool = True
    keywords: tuple[str, ...] = ()
    catch_all: bool = False


GROUPS: tuple[Group, ...] = (
    Group(name="обычные (стандарт, без фильтров)", catch_all=True),
    Group(
        name="семья / дети / взрослый контент",
        keywords=("семейн", "семь", "дет", "взросл", "family", "kid", "adult"),
    ),
    Group(
        name="защита / вредоносное ПО",
        keywords=(
            "безопасн",
            "вредонос",
            "защит",
            "угроз",
            "фильтр безопасности",
            "malware",
            "security",
            "threat",
            "safe",
            "block",
            "strict",
            "adaptive",
        ),
    ),
    Group(
        name="реклама / трекеры",
        keywords=("реклам", "tracker", "ads", "adblock", "социальн"),
    ),
)

# Дополнительные записи (идут как сейчас — всегда проверяются).
# Формат: ("имя для таблицы", "адрес"). Чтобы добавить свой IPv4 — заполни CUSTOM_V4.
CUSTOM_V4: list[tuple[str, str]] = []
# Пример своей записи (адрес нерабочий, заглушка для формата "Имя|URL").
# Замените своим резолвером или передайте через --custom-doh / DNS_CHECK_CUSTOM_DOH.
CUSTOM_DOH: list[tuple[str, str]] = [("koljasha (свой)", "https://koljasha.ru:443/dns-query")]

# ---------------------------------------------------------------------------
# Формат DNS-запроса (A record для example.com), id = 0xAABB
# ---------------------------------------------------------------------------

DNS_ID = 0xAABB
DNS_QUERY_HEX = "aabb01000001000000000000076578616d706c6503636f6d0000010001"
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOH_RE = re.compile(r"https://[^\s<>\"'()]+")


def dns_param() -> str:
    """Возвращает URL-кодированный DoH-параметр dns для зонда example.com."""
    raw = base64.urlsafe_b64encode(bytes.fromhex(DNS_QUERY_HEX)).decode().rstrip("=")
    return urllib.parse.quote(raw)


def _skip_name(data: bytes, pos: int) -> int:
    """Пропускает DNS-имя в сообщении, возвращает позицию после него."""
    while True:
        length = data[pos]
        if length == 0:
            return pos + 1
        if length & 0xC0 == 0xC0:  # сжатие имени
            return pos + 2
        pos += 1 + length


def parse_dns_response(data: bytes) -> dict[str, int] | None:
    """Парсим ответ как DNS-сообщение: проверяем ID, flag QR и считаем A-записи."""
    if len(data) < 12:
        return None
    qid, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    if qid != DNS_ID or not (flags & 0x8000):
        return None
    rcode = flags & 0x0F
    pos = 12
    for _ in range(qd):
        pos = _skip_name(data, pos) + 4
    answers = 0
    for _ in range(an):
        pos = _skip_name(data, pos)
        if pos + 10 > len(data):
            return None
        qtype, _qclass, _ttl, rdlen = struct.unpack(">HHIH", data[pos : pos + 10])
        pos += 10
        if pos + rdlen > len(data):
            return None
        if qtype == 1 and rdlen == 4:  # A record
            answers += 1
        pos += rdlen
    return {"rcode": rcode, "answers": answers}


# ---------------------------------------------------------------------------
# Проверка наличия инструментов
# ---------------------------------------------------------------------------

# Пакеты-подсказки по дистрибутиву (ID из /etc/os-release -> семейство).
_ARCH_IDS = {"arch", "manjaro", "endeavouros", "cachyos", "garuda", "artix"}
_DEBIAN_IDS = {
    "debian",
    "ubuntu",
    "linuxmint",
    "kali",
    "pop",
    "elementary",
    "neon",
    "zorin",
    "mx",
    "raspbian",
}
_RPM_IDS = {"fedora", "rhel", "centos", "rocky", "almalinux", "ol", "amzn"}

PACKAGE_HINTS: dict[str, dict[str, str]] = {
    "arch": {"curl": "curl", "dig": "bind", "kdig": "knot"},
    "debian": {"curl": "curl", "dig": "bind9-dnsutils", "kdig": "knot-dnsutils"},
    "rpm": {"curl": "curl", "dig": "bind-utils"},
    "alpine": {"curl": "curl", "dig": "bind-tools"},
}

GENERIC_HINTS = {
    "curl": "curl",
    "dig": "bind9-dnsutils / bind-utils / dnsutils / bind",
    "kdig": "knot / knot-dnsutils",
}


def distro_family() -> str:
    """Семейство дистрибутива по /etc/os-release: arch|debian|rpm|alpine|unknown."""
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            ident = ""
            for line in f:
                if line.startswith("ID="):
                    ident = line[3:].strip().strip('"')
                    break
    except OSError:
        return "unknown"
    if ident in _ARCH_IDS:
        return "arch"
    if ident in _DEBIAN_IDS:
        return "debian"
    if ident in _RPM_IDS:
        return "rpm"
    if ident == "alpine":
        return "alpine"
    return "unknown"


def require_tools() -> tuple[str, str]:
    """Проверяет наличие curl и dig/kdig в PATH.

    Returns:
        Кортеж (путь к curl, путь к dig/kdig).

    Raises:
        DnsCheckError: если нужных программ нет (с подсказкой пакетов).
    """
    curl = shutil.which("curl")
    dig = shutil.which("dig") or shutil.which("kdig")
    wanted: list[str] = []
    if not curl:
        wanted.append("curl")
    if not dig:
        wanted.append("dig или kdig")
    if wanted:
        fam = distro_family()
        lines = ["не найдены нужные программы: " + ", ".join(wanted)]
        for cmd in ("curl", "dig", "kdig"):
            if cmd == "curl" and "curl" not in wanted:
                continue
            if cmd in ("dig", "kdig") and "dig или kdig" not in wanted:
                continue
            pkg = PACKAGE_HINTS.get(fam, {}).get(cmd)
            if pkg:
                lines.append("  %s: пакет %s" % (cmd, pkg))
            else:
                lines.append("  %s: пакеты %s" % (cmd, GENERIC_HINTS[cmd]))
        lines.append("установите и запустите снова")
        raise DnsCheckError("\n".join(lines))
    assert curl is not None and dig is not None
    return curl, dig


# ---------------------------------------------------------------------------
# Скачивание страницы
# ---------------------------------------------------------------------------


def fetch_page(curl: str) -> str:
    """Скачивает страницу KB через curl.

    Args:
        curl: путь к бинарю curl.

    Returns:
        HTML-разметка страницы.

    Raises:
        DnsCheckError: если страницу не удалось скачать.
    """
    try:
        r = subprocess.run(
            [curl, "-s", "-L", "--max-time", "30", KB_URL],
            capture_output=True,
            text=True,
            timeout=35,
        )
    except subprocess.TimeoutExpired:
        raise DnsCheckError("не удалось скачать страницу (таймаут): " + KB_URL)
    if r.returncode != 0 or not r.stdout:
        raise DnsCheckError("не удалось скачать страницу: " + KB_URL)
    return r.stdout


# ---------------------------------------------------------------------------
# Парсинг страницы
# ---------------------------------------------------------------------------


class ProvidersParser(html.parser.HTMLParser):
    """Вытаскивает (провайдер, вариант, протокол, адрес) из таблиц страницы.

    В HTML Docusaurus теги <td> и <tr> не закрываются: граница ячейки —
    следующий <td>/<th>, граница строки — следующий <tr>.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, str, str, str]] = []
        self._provider = ""
        self._variant = ""
        self._hdr: str | None = None
        self._hdr_level = 0
        self._in_hdr = False
        self._hdr_buf: list[str] = []
        self._level = 0
        self._cells: list[str] = []
        self._cell: str | None = None

    def _finish_hdr(self) -> None:
        if self._hdr is None:
            return
        text = re.sub(r"\s+", " ", "".join(self._hdr_buf).replace("\u200b", " ")).strip()
        if self._hdr == "h3":
            self._provider = text
        else:
            self._variant = text
        self._hdr = None
        self._hdr_buf = []

    def _push_cell(self) -> None:
        if self._cell is not None:
            self._cells.append(self._cell.strip())
        self._cell = ""

    def _end_row(self) -> None:
        self._push_cell()
        if len(self._cells) >= 2 and self._provider and self._cells[0]:
            self.rows.append((self._provider, self._variant, self._cells[0], self._cells[1]))
        self._cells = []
        self._cell = None

    def flush(self) -> None:
        """Сбрасывает незавершённую строку таблицы в rows (конец документа)."""
        self._end_row()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._level += 1
        if tag in ("h3", "h4"):
            self._end_row()
            self._finish_hdr()
            if tag == "h3":
                self._variant = ""
            self._hdr = tag
            self._hdr_level = self._level
            self._in_hdr = True
            self._hdr_buf = []
        elif tag == "tr":
            self._end_row()
        elif tag in ("td", "th"):
            self._finish_hdr()
            self._push_cell()
        elif tag == "br" and self._cell is not None:
            self._cell += " "

    def handle_data(self, data: str) -> None:
        if self._in_hdr:
            if self._level == self._hdr_level:
                self._hdr_buf.append(data)
        elif self._cell is not None:
            self._cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h3", "h4") and self._in_hdr:
            self._in_hdr = False
        self._level -= 1


def extract_endpoints(
    html: str,
) -> tuple[OrderedDict[str, tuple[str, str]], OrderedDict[str, tuple[str, str]]]:
    """Извлекает IPv4 и DoH эндпоинты из HTML страницы KB.

    Args:
        html: разметка страницы.

    Returns:
        Кортеж (ipv4, doh): упорядоченные словари адрес -> (провайдер, вариант).
    """
    parser = ProvidersParser()
    parser.feed(html)
    parser.flush()

    ipv4: OrderedDict[str, tuple[str, str]] = OrderedDict()
    doh: OrderedDict[str, tuple[str, str]] = OrderedDict()
    for prov, var, proto, addr in parser.rows:
        proto_l = proto.lower()
        if proto_l.startswith("dns, ipv4"):
            for m in IPV4_RE.finditer(addr):
                ip = m.group(0)
                if all(0 <= int(o) <= 255 for o in ip.split(".")):
                    ipv4.setdefault(ip, (prov, var))
        elif proto_l.startswith("dns-over-https"):
            for m in DOH_RE.finditer(addr):
                url = m.group(0).rstrip(".,);:")
                doh.setdefault(url, (prov, var))
    return ipv4, doh


# ---------------------------------------------------------------------------
# Группировка
# ---------------------------------------------------------------------------


def classify_variant(variant: str) -> str:
    """Относит вариант провайдера к первой подходящей группе по ключевым словам."""
    low = variant.lower()
    for g in GROUPS:
        if g.catch_all:
            continue
        if any(k in low for k in g.keywords):
            return g.name
    for g in GROUPS:
        if g.catch_all:
            return g.name
    return GROUPS[0].name


def resolve_group(token: str) -> str | None:
    """Ключ из GROUP_KEYS или полное имя группы -> имя группы, иначе None."""
    mapped = GROUP_KEYS.get(token.upper())
    if mapped is not None:
        return mapped
    if any(g.name == token for g in GROUPS):
        return token
    return None


def group_enabled(name: str) -> bool:
    """Проверяет, включена ли группа через CHECK_GROUPS (или флаги CLI)."""
    if name == "Дополнительные":
        return True
    if CHECK_GROUPS:
        return name in {resolve_group(t) for t in CHECK_GROUPS}
    for g in GROUPS:
        if g.name == name:
            return g.on
    return True


def server_name(prov: str, variant: str) -> str:
    """Возвращает имя сервера для таблицы: провайдер либо 'провайдер — вариант'."""
    return prov if not variant else "%s — %s" % (prov, variant)


@dataclass(slots=True)
class DnsServer:
    """Один проверяемый резолвер с результатами проходов."""

    name: str
    group: str
    endpoint: str
    kind: str  # "v4" | "doh"
    times: list[int | None] = field(default_factory=lambda: [None] * PASSES)
    ok: int = 0
    best: int | None = None


def build_entries(
    ipv4: OrderedDict[str, tuple[str, str]],
    doh: OrderedDict[str, tuple[str, str]],
) -> tuple[list[DnsServer], list[DnsServer]]:
    """Строит списки серверов IPv4 и DoH с учётом групп и дополнительных записей."""
    v4: list[DnsServer] = []
    dh: list[DnsServer] = []
    for ep, (prov, var) in ipv4.items():
        grp = classify_variant(var)
        if group_enabled(grp):
            v4.append(DnsServer(server_name(prov, var), grp, ep, "v4"))
    for ep, (prov, var) in doh.items():
        grp = classify_variant(var)
        if group_enabled(grp):
            dh.append(DnsServer(server_name(prov, var), grp, ep, "doh"))
    for name, ep in CUSTOM_V4:
        v4.append(DnsServer(name, "Дополнительные", ep, "v4"))
    for name, ep in CUSTOM_DOH:
        dh.append(DnsServer(name, "Дополнительные", ep, "doh"))
    return v4, dh


# ---------------------------------------------------------------------------
# Проверки
# ---------------------------------------------------------------------------


def probe_v4(dig: str, ip: str) -> tuple[bool, int]:
    """Проверяет IPv4-резолвер запросом A через dig/kdig.

    Returns:
        Кортеж (успех, задержка в мс).
    """
    cmd = [
        dig,
        "@" + ip,
        PROBE_NAME,
        "A",
        "+time=%d" % TIMEOUT,
        "+tries=1",
        "+noall",
        "+comments",
        "+answer",
        "+stats",
    ]
    start = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 4)
    except (subprocess.TimeoutExpired, OSError):
        return False, int((time.monotonic() - start) * 1000)
    dt = int((time.monotonic() - start) * 1000)
    st = re.search(r"status:\s*([A-Z]+)", r.stdout)
    if st is None or st.group(1) != "NOERROR":
        return False, dt
    if not re.search(r"\bIN\s+A\s+\d{1,3}(?:\.\d{1,3}){3}\b", r.stdout):
        return False, dt
    mt = re.search(r"Query time:\s*(\d+)", r.stdout)
    return True, int(mt.group(1)) if mt else dt


def probe_doh(curl: str, url: str) -> tuple[bool, int]:
    """Проверяет DoH-резолвер GET-запросом с DNS-телом.

    Returns:
        Кортеж (успех, задержка в мс).
    """
    sep = "&" if "?" in url else "?"
    target = url + sep + "dns=" + dns_param()
    fd, body_path = tempfile.mkstemp(prefix="checkdns-", suffix=".bin")
    os.close(fd)
    start = time.monotonic()
    try:
        r = subprocess.run(
            [
                curl,
                "-s",
                "--max-time",
                str(TIMEOUT),
                "-o",
                body_path,
                "-H",
                "accept: application/dns-message",
                "-w",
                "%{http_code}\t%{content_type}",
                target,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT + 4,
        )
        dt = int((time.monotonic() - start) * 1000)
        code, _, ctype = r.stdout.partition("\t")
        if code != "200":
            return False, dt
        if DOH_REQUIRE_CTYPE and not ctype.strip().lower().startswith("application/dns-message"):
            return False, dt
        try:
            with open(body_path, "rb") as f:
                body = f.read()
        except OSError:
            return False, dt
        parsed = parse_dns_response(body)
        if parsed is None or parsed["rcode"] != 0 or parsed["answers"] < 1:
            return False, dt
        return True, dt
    except (subprocess.TimeoutExpired, OSError):
        return False, int((time.monotonic() - start) * 1000)
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass


def run_pass(servers: list[DnsServer], curl: str, dig: str, pass_no: int) -> None:
    """Выполняет один проход проверки всех серверов параллельно."""

    def one(s: DnsServer) -> tuple[bool, int]:
        return probe_v4(dig, s.endpoint) if s.kind == "v4" else probe_doh(curl, s.endpoint)

    done = ok_v4 = ok_doh = 0
    total_4 = sum(1 for s in servers if s.kind == "v4")
    total_d = len(servers) - total_4
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(one, s): s for s in servers}
        for fut in concurrent.futures.as_completed(futs):
            s = futs[fut]
            ok, ms = fut.result()
            if ok:
                s.ok += 1
                s.times[pass_no - 1] = ms
                if s.best is None or ms < s.best:
                    s.best = ms
                if s.kind == "v4":
                    ok_v4 += 1
                else:
                    ok_doh += 1
            done += 1
            sys.stdout.write(
                "\rпроход %d/%d  ipv4 %d/%d  doh %d/%d  проверено %d/%d"
                % (pass_no, PASSES, ok_v4, total_4, ok_doh, total_d, done, len(servers))
            )
            sys.stdout.flush()


# ---------------------------------------------------------------------------
# Вывод
# ---------------------------------------------------------------------------


def color(text: str, code: str) -> str:
    """Оборачивает текст в ANSI-цвет, если stdout — терминал."""
    if sys.stdout.isatty():
        return "\033[%sm%s\033[0m" % (code, text)
    return text


def cell(ms: int | None) -> str:
    """Форматирует задержку для ячейки таблицы ('-' при отсутствии)."""
    return str(ms) if ms is not None else "-"


def clip(text: str, width: int) -> str:
    """Обрезает текст до ширины с многоточием."""
    return text if len(text) <= width else text[: width - 1] + "…"


def pad(text: str, width: int, left: bool = False) -> str:
    """Выравнивает текст по ширине (влево при left, иначе вправо)."""
    return text.ljust(width) if left else text.rjust(width)


def print_table(title: str, servers: list[DnsServer]) -> None:
    """Печатает таблицу результатов: сначала доступные, затем недоступные."""
    alive = sorted((s for s in servers if s.ok), key=lambda s: s.best or 0)
    dead = sorted((s for s in servers if not s.ok), key=lambda s: s.name.lower())

    n_pass = max((len(s.times) for s in servers), default=PASSES)
    num_w, time_w, ok_w = 3, 8, 5
    name_w = min(max(max((len(s.name) for s in servers), default=14), 14), 48)
    addr_w = min(max(max((len(s.endpoint) for s in servers), default=8), 8), 62)

    def pcell(text: str, width: int, left: bool = False, code: str | None = None) -> str:
        s = pad(clip(text, width), width, left)
        return color(s, code) if code else s

    head = "  ".join(
        [
            pcell("#", num_w),
            pcell("провайдер", name_w, left=True),
            pcell("адрес", addr_w, left=True),
        ]
        + [pcell("проход%d" % (k + 1), time_w) for k in range(n_pass)]
        + [pcell("итог*", time_w), pcell("успех", ok_w)]
    )

    print("")
    print(title + "  (%d из %d доступно)" % (len(alive), len(servers)))
    print(head)
    print("-" * len(head))

    for i, s in enumerate(alive, 1):
        ok_all = s.ok == PASSES
        code = "32" if ok_all else None
        cells = [
            pcell(str(i), num_w),
            pcell(s.name, name_w, left=True),
            pcell(s.endpoint, addr_w, left=True),
        ]
        cells += [
            pcell(cell(s.times[k]) if k < len(s.times) else cell(None), time_w)
            for k in range(n_pass)
        ]
        cells += [
            pcell(str(s.best or 0), time_w, code=code),
            pcell("%d/%d" % (s.ok, PASSES), ok_w, code=code),
        ]
        print("  ".join(cells))

    for s in dead:
        cells = [
            pcell("-", num_w),
            pcell(s.name, name_w, left=True),
            pcell(s.endpoint, addr_w, left=True, code="31"),
        ]
        cells += [pcell(cell(None), time_w) for _ in range(n_pass)]
        cells += [
            pcell("-", time_w, code="31"),
            pcell("0/%d" % PASSES, ok_w, code="31"),
        ]
        print("  ".join(cells))


# ---------------------------------------------------------------------------
# Главная
# ---------------------------------------------------------------------------


def _parse_custom_doh_entry(entry: str) -> tuple[str, str]:
    """Разбирает одну запись --custom-doh: 'Имя|URL', 'Имя=URL' или голый URL."""
    for sep in ("|", "="):
        if sep in entry:
            name, _, url = entry.partition(sep)
            name, url = name.strip(), url.strip()
            if name and url:
                return (name, url)
            break
    url = entry.strip()
    return (url, url)


def _custom_doh_from_env() -> list[tuple[str, str]] | None:
    """Читает CUSTOM_DOH из DNS_CHECK_CUSTOM_DOH; None если переменная пуста."""
    raw = os.environ.get(CUSTOM_DOH_ENV_VAR, "").strip()
    if not raw:
        return None
    return [_parse_custom_doh_entry(e) for e in re.split(r"[;\n]+", raw) if e.strip()]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Разбирает флаги CLI; дефолты берутся из констант модуля."""
    parser = argparse.ArgumentParser(description="Проверка DNS-резолверов по KB AdGuard.")
    parser.add_argument(
        "--groups",
        default=None,
        metavar="STANDART,MALWARE",
        help=(
            "Группы через запятую (ключи: STANDART, CHILD, MALWARE, ADS). "
            "По умолчанию берётся CHECK_GROUPS; пустая строка = все группы с on=True."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT,
        help="Секунд на попытку (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--passes", type=int, default=PASSES, help="Проходов по списку (по умолчанию: %(default)s)."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=WORKERS,
        help="Параллельных запросов (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--custom-doh",
        action="append",
        default=None,
        metavar="Имя|URL",
        help=(
            "Дополнительный DoH-сервер (можно несколько раз). "
            "Перекрывает CUSTOM_DOH и DNS_CHECK_CUSTOM_DOH."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Главная: скачивает страницу KB, проверяет резолверы, печатает таблицы.

    Args:
        argv: аргументы командной строки (None = sys.argv).

    Raises:
        DnsCheckError: фатальная ошибка (нет инструментов, страница не скачалась,
            нечего проверять, неизвестная группа).
    """
    global CHECK_GROUPS, TIMEOUT, PASSES, WORKERS, CUSTOM_DOH
    args = _parse_args(argv)
    TIMEOUT = args.timeout
    PASSES = args.passes
    WORKERS = args.workers
    if args.groups is not None:
        CHECK_GROUPS = tuple(t.strip() for t in args.groups.split(",") if t.strip())
    if args.custom_doh is not None:
        CUSTOM_DOH = [_parse_custom_doh_entry(e) for e in args.custom_doh]
    else:
        from_env = _custom_doh_from_env()
        if from_env is not None:
            CUSTOM_DOH = from_env

    curl, dig = require_tools()
    html = fetch_page(curl)
    ipv4, doh = extract_endpoints(html)

    servers_v4, servers_doh = build_entries(ipv4, doh)
    servers = servers_v4 + servers_doh
    if not servers:
        raise DnsCheckError("ничего не собрано для проверки — страница изменилась?")

    if CHECK_GROUPS:
        resolved, bad = [], []
        for token in CHECK_GROUPS:
            r = resolve_group(token)
            if r is None:
                bad.append(token)
            else:
                resolved.append(r)
        if bad:
            raise DnsCheckError(
                "неизвестный ключ группы в CHECK_GROUPS: "
                + ", ".join(bad)
                + "\nдоступны: "
                + ", ".join(GROUP_KEYS)
            )
        enabled = ", ".join(g.name for g in GROUPS if g.name in resolved)
    else:
        enabled = ", ".join(g.name for g in GROUPS if g.on)
    print("страница: " + KB_URL)
    print("проверяемые группы: " + enabled)
    print("проверяем: IPv4 (%d записей), DoH (%d записей)" % (len(servers_v4), len(servers_doh)))
    print("")

    for p in range(1, PASSES + 1):
        run_pass(servers, curl, dig, p)
        print("")
        sys.stdout.flush()

    print_table("DNS, IPv4 (порт 53, UDP) — от лучшего к худшему", servers_v4)
    print_table("DNS-over-HTTPS — от лучшего к худшему", servers_doh)
    print("")
    print("* все задержки — миллисекунды (меньше = лучше)")
    print("* итог = лучший (минимальный) из успешных проходов — по нему сортировка")
    print("* успех = успешных проходов из %d; «-» = проход не удался" % PASSES)


if __name__ == "__main__":
    try:
        main()
    except DnsCheckError as err:
        sys.exit(str(err))
    except KeyboardInterrupt:
        print("\nпрервано")
        sys.exit(130)
