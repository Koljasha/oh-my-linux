#!/usr/bin/env python3
"""Мониторинг таблиц OpenCode Go (лимиты запросов и цены) и Zen (цены, устаревание).

Скрипт периодически (cron) проверяет:
https://opencode.ai/docs/en/go/
https://opencode.ai/docs/en/zen/
хранит снапшот в state.json и при изменениях
(появление/пропажа моделей, смена Free → платная, изменение лимитов, цен,
месячного лимита, устаревание) шлёт уведомление в Telegram.

Зависимости: pip install requests beautifulsoup4

Настройка: создать рядом со скриптом файл .env с двумя строками:
    TG_BOT_TOKEN=<токен бота от BotFather>
    TG_CHAT_ID=<id чата или канала, напр. -1001234567890>

Лог — один файл opencode_monitor.log. В конце каждого запуска проверяется число строк:
если больше LOG_MAX_LINES (10000), старые строки удаляются, остаются последние
LOG_KEEP_LINES (1000).

Пример cron (запуск каждые 4 часа); в cron.err попадает только stderr — ошибки
и необработанные краши, обычный лог пишется скриптом в opencode_monitor.log:
0 */4 * * * /usr/bin/python3 /opt/opencode-monitor/opencode_monitor.py 2>> /opt/opencode-monitor/cron.err
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import NotRequired, TypedDict

import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import Comment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOG_PATH = os.path.join(BASE_DIR, "opencode_monitor.log")

LOG_MAX_LINES = 10000
LOG_KEEP_LINES = 1000
HTTP_TIMEOUT = 30

DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) opencode-price-monitor/1.0"

PAGES = {
    "Go": "https://opencode.ai/docs/en/go/",
    "Zen": "https://opencode.ai/docs/en/zen/",
}

GO_HEADERS = {"Model", "requests per 5 hour"}
GO_PRICE_HEADERS = {"Model", "Cached Read", "Monthly limit"}
ZEN_HEADERS = {"Model", "Cached Read"}
DEPRECATED_HEADERS = {"Model", "Deprecation date"}

# Порядок источников в уведомлении и их подписи.
SOURCE_ORDER = ("Go", "GoPrices", "Zen")
SOURCE_NAMES = {"Go": "Go (запросы)", "GoPrices": "Go (цены)", "Zen": "Zen"}

FIELD_LABELS = {
    "Go": {"за 5 часов": "за 5 часов", "в неделю": "в неделю", "в месяц": "в месяц"},
    "GoPrices": {
        "вход": "Вход",
        "выход": "Выход",
        "cached_read": "Cached Read",
        "cached_write": "Cached Write",
        "monthly_limit": "Monthly limit",
    },
    "Zen": {
        "вход": "Вход",
        "выход": "Выход",
        "cached_read": "Cached Read",
        "cached_write": "Cached Write",
    },
}

ModelTable = dict[str, dict[str, str]]
TariffEvent = tuple[str, str, str]
PriceChange = tuple[str, list[tuple[str, str | None, str | None]]]
DeprecatedEvent = tuple[str, str | None, str | None]


class SourceData(TypedDict):
    """Свежие данные источника: модели и опционально таблица устаревания."""

    models: ModelTable
    deprecated: NotRequired[dict[str, str] | None]


class SourceSnapshot(TypedDict):
    """Запись состояния источника в state.json с меткой времени."""

    fetched_at: str
    models: ModelTable
    deprecated: NotRequired[dict[str, str] | None]


class SourceDiff(TypedDict):
    """Изменения источника между снапшотами по категориям."""

    removed: list[str]
    added: list[str]
    tariff: list[TariffEvent]
    prices: list[PriceChange]
    deprecated: list[DeprecatedEvent]


logger = logging.getLogger("opencode_monitor")


def load_env() -> dict[str, str]:
    """Читает секреты Telegram из файла .env рядом со скриптом.

    Returns:
        Словарь конфигурации; значения пустые, если .env отсутствует
        или переменная не задана.
    """
    cfg = {"TG_BOT_TOKEN": "", "TG_CHAT_ID": ""}
    if not os.path.exists(ENV_PATH):
        return cfg
    with open(ENV_PATH, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            line = re.sub(r"^export\s+", "", line)
            key, _, value = line.partition("=")
            value = re.sub(r"\s+#.*$", "", value)
            cfg[key.strip()] = value.strip().strip('"').strip("'")
    return cfg


def setup_logging() -> None:
    """Настраивает логгирование: INFO в файл, ERROR в stderr.

    Обычные записи идут только в opencode_monitor.log; stderr (cron.err)
    получает лишь ошибки и необработанные краши.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.ERROR)
    root.addHandler(sh)


def trim_log() -> None:
    """Обрезает лог до последних LOG_KEEP_LINES строк, если строк больше LOG_MAX_LINES.

    При размере ниже порога ничего не делает; факт обрезки логируется.
    """
    if not os.path.exists(LOG_PATH):
        return
    try:
        with open(LOG_PATH, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > LOG_MAX_LINES:
            with open(LOG_PATH, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-LOG_KEEP_LINES:])
            logger.info("Лог обрезан: было %d строк, осталось %d", len(lines), LOG_KEEP_LINES)
    except OSError as err:
        logger.error("Не удалось обрезать лог: %s", err)


def fetch_html(url: str, timeout: int) -> str:
    """GET-запрос страницы с 3 попытками и экспоненциальной паузой.

    Args:
        url: адрес страницы.
        timeout: таймаут запроса в секундах.

    Returns:
        HTML-разметка страницы в кодировке UTF-8.

    Raises:
        RuntimeError: если все попытки неудачны.
    """
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as err:
            last_err = err
            logger.warning("Сеть: попытка %d/3 для %s не удалась: %s", attempt + 1, url, err)
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"Не удалось получить {url}: {last_err}")


def _normalize(value: str) -> str:
    """Схлопывает подряд идущие пробелы и обрезает строку."""
    return re.sub(r"\s+", " ", value).strip()


def _cell_text(cell: Tag) -> str:
    """Текст ячейки без устаревших и служебных вставок.

    Зачёркнутый текст (<del>, <s>, <strike>) — старое значение, отбрасывается;
    мелкий шрифт (<small>) — примечание к акции, тоже не входит в значение,
    чтобы имя модели и лимиты оставались стабильными. Без этого новая разметка
    акции (<del>6,500</del><br><strong>26,000</strong>) склеивалась бы в
    "6,500 26,000", а имя модели — в "... Flash 4x · Ends Sep 20".
    """
    chunks: list[str] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, Tag):
                if child.name in ("del", "s", "strike", "small"):
                    continue
                if child.name == "br":
                    chunks.append(" ")
                else:
                    walk(child)
            else:
                chunks.append(str(child))

    walk(cell)
    return _normalize("".join(chunks))


def _find_table(soup: BeautifulSoup, expected_headers: set[str]) -> Tag | None:
    """Ищет первую таблицу, чей заголовок содержит все ожидаемые колонки.

    Args:
        soup: распарсенный HTML страницы.
        expected_headers: подмножество имён колонок, идентифицирующих таблицу.

    Returns:
        Элемент таблицы или None, если таблица не найдена.
    """
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        cells = [_cell_text(c) for c in header_row.find_all(["th", "td"])]
        if set(expected_headers) <= set(cells):
            return table
    return None


def _table_rows(table: Tag) -> list[list[str]]:
    """Возвращает строки данных таблицы (без заголовка) как списки ячеек.

    Пропускаются пустые строки.
    """
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = [_cell_text(c) for c in tr.find_all(["td", "th"])]
        if cells and any(cells):
            rows.append(cells)
    return rows


def _header_indexes(table: Tag) -> list[str]:
    """Возвращает имена колонок таблицы (заголовок)."""
    header_row = table.find("tr")
    if header_row is None:
        return []
    return [_cell_text(c) for c in header_row.find_all(["th", "td"])]


def _column_indexes(headers: list[str], names: tuple[str, ...]) -> dict[str, int]:
    """Возвращает индексы ожидаемых колонок по именам заголовков.

    Args:
        headers: фактические имена колонок таблицы.
        names: ожидаемые имена колонок.

    Returns:
        Словарь {имя колонки: индекс}.

    Raises:
        RuntimeError: если ожидаемая колонка отсутствует (структура
            страницы изменилась).
    """
    indexes: dict[str, int] = {}
    for name in names:
        if name not in headers:
            raise RuntimeError(
                f"Не найдена колонка «{name}» (заголовки: {headers}) — "
                "структура страницы изменилась"
            )
        indexes[name] = headers.index(name)
    return indexes


def parse_go(soup: BeautifulSoup) -> ModelTable:
    """Парсит таблицу лимитов запросов Go.

    Returns:
        Словарь {модель: {"за 5 часов": ..., "в неделю": ..., "в месяц": ...}}.

    Raises:
        RuntimeError: таблица не найдена или пуста (структура страницы изменилась).
    """
    table = _find_table(soup, GO_HEADERS)
    if table is None:
        raise RuntimeError("Не найдена таблица запросов Go на странице")
    headers = _header_indexes(table)
    idx = _column_indexes(
        headers,
        (
            "Model",
            "requests per 5 hour",
            "requests per week",
            "requests per month",
        ),
    )
    models = {}
    for cells in _table_rows(table):
        if len(cells) <= max(idx.values()):
            continue
        models[cells[idx["Model"]]] = {
            "за 5 часов": cells[idx["requests per 5 hour"]],
            "в неделю": cells[idx["requests per week"]],
            "в месяц": cells[idx["requests per month"]],
        }
    if not models:
        raise RuntimeError("Таблица запросов Go пуста — возможно, изменилась структура страницы")
    return models


def parse_go_pricing(soup: BeautifulSoup) -> ModelTable:
    """Парсит таблицу цен Go (за 1M токенов и месяцной лимит).

    Returns:
        Словарь {модель: {вход, выход, cached_read, cached_write, monthly_limit}}.

    Raises:
        RuntimeError: таблица не найдена или пуста (структура страницы изменилась).
    """
    table = _find_table(soup, GO_PRICE_HEADERS)
    if table is None:
        raise RuntimeError("Не найдена таблица цен Go на странице")
    headers = _header_indexes(table)
    idx = _column_indexes(
        headers,
        (
            "Model",
            "Input",
            "Output",
            "Cached Read",
            "Cached Write",
            "Monthly limit",
        ),
    )
    models = {}
    for cells in _table_rows(table):
        if len(cells) <= max(idx.values()):
            continue
        models[cells[idx["Model"]]] = {
            "вход": cells[idx["Input"]],
            "выход": cells[idx["Output"]],
            "cached_read": cells[idx["Cached Read"]],
            "cached_write": cells[idx["Cached Write"]],
            "monthly_limit": cells[idx["Monthly limit"]],
        }
    if not models:
        raise RuntimeError("Таблица цен Go пуста — возможно, изменилась структура страницы")
    return models


def parse_zen(soup: BeautifulSoup) -> tuple[ModelTable, dict[str, str] | None]:
    """Парсит таблицу цен Zen и таблицу устаревания.

    Returns:
        Кортеж (модели, deprecated): модели — {модель: {вход, выход, cached_read,
        cached_write}}, deprecated — {модель: дата устаревания} либо None, если
        таблица устаревания отсутствует на странице.

    Raises:
        RuntimeError: таблица цен не найдена или пуста.
    """
    table = _find_table(soup, ZEN_HEADERS)
    if table is None:
        raise RuntimeError("Не найдена таблица цен Zen на странице")
    headers = _header_indexes(table)
    idx = _column_indexes(headers, ("Model", "Input", "Output", "Cached Read", "Cached Write"))
    models = {}
    for cells in _table_rows(table):
        if len(cells) <= max(idx.values()):
            continue
        models[cells[idx["Model"]]] = {
            "вход": cells[idx["Input"]],
            "выход": cells[idx["Output"]],
            "cached_read": cells[idx["Cached Read"]],
            "cached_write": cells[idx["Cached Write"]],
        }
    if not models:
        raise RuntimeError("Таблица цен Zen пуста — возможно, изменилась структура страницы")

    deprecated: dict[str, str] | None = None
    dtable = _find_table(soup, DEPRECATED_HEADERS)
    if dtable is not None:
        deprecated = {}
        dheaders = _header_indexes(dtable)
        didx = _column_indexes(dheaders, ("Model", "Deprecation date"))
        for cells in _table_rows(dtable):
            if len(cells) <= max(didx.values()):
                continue
            deprecated[cells[didx["Model"]]] = cells[didx["Deprecation date"]]
    return models, deprecated


def diff_models(
    prev: ModelTable, curr: ModelTable, free_tariff: bool = False
) -> tuple[list[str], list[str], list[TariffEvent], list[PriceChange]]:
    """Сравнивает два снапшота моделей.

    Пара «X Free» и «X» распознаётся как смена тарифа (одно событие), а не как
    пропажа и появление. Дубли имён (варианты лимитов токенов, например
    «Claude Sonnet 4.5 (≤ 200K tokens)» и «(> 200K tokens)») — отдельные модели.

    Args:
        prev: прежний снапшот моделей.
        curr: текущий снапшот моделей.
        free_tariff: распознавать ли смену тарифа «Free» (имеет смысл только
            для Zen).

    Returns:
        Кортеж (пропали, появились, смены тарифа, изменения цен).
    """
    prev_keys, curr_keys = set(prev), set(curr)
    removed = prev_keys - curr_keys
    added = curr_keys - prev_keys
    tariff = []

    if free_tariff:
        for name in list(removed):
            if name.endswith(" Free"):
                base = name[: -len(" Free")]
                if base in added:
                    tariff.append((name, base, "платной"))
                    removed.discard(name)
                    added.discard(base)

        for name in list(added):
            if name.endswith(" Free"):
                base = name[: -len(" Free")]
                if base in removed:
                    tariff.append((base, name, "бесплатной"))
                    added.discard(name)
                    removed.discard(base)

    price_changes = []
    for name in prev_keys & curr_keys:
        if prev[name] != curr[name]:
            fields = [
                (k, prev[name].get(k), curr[name].get(k))
                for k in set(prev[name]) | set(curr[name])
                if prev[name].get(k) != curr[name].get(k)
            ]
            price_changes.append((name, fields))

    return sorted(removed), sorted(added), sorted(tariff), price_changes


def build_message(changes: dict[str, SourceDiff], now_str: str) -> str:
    """Собирает текст уведомления для Telegram.

    Args:
        changes: обнаруженные изменения по источникам Go/GoPrices/Zen.
        now_str: дата и время в человекочитаемом формате.

    Returns:
        Текст сообщения, обрезанный до 4000 символов (лимит Telegram).
    """
    out = [f"📡 OpenCode-монитор — изменения ({now_str})", ""]

    order = [s for s in SOURCE_ORDER if s in changes]
    removed = [f"{SOURCE_NAMES[s]}: {n}" for s in order for n in changes[s]["removed"]]
    added = [f"{SOURCE_NAMES[s]}: {n}" for s in order for n in changes[s]["added"]]
    tariff = [
        f"{SOURCE_NAMES[s]}: {old} → {new} (стала {label})"
        for s in order
        for (old, new, label) in changes[s]["tariff"]
    ]
    prices = []
    for s in order:
        for name, fields in changes[s]["prices"]:
            bits = [
                f"{FIELD_LABELS[s][k]}: "
                f"{old if old is not None else '(нет)'} → "
                f"{new if new is not None else '(нет)'}"
                for k, old, new in fields
            ]
            prices.append(f"{SOURCE_NAMES[s]}: {name} — {', '.join(bits)}")
    dep_events = []
    for name, new_date, old_date in changes.get("Zen", {}).get("deprecated", []):
        if new_date is None:
            dep_events.append(f"Zen: {name} — исключена из списка устаревания (было: {old_date})")
        else:
            tail = f"{new_date}" if old_date is None else f"{new_date} (было: {old_date})"
            dep_events.append(f"Zen: {name} — дата устаревания {tail}")

    def add(title: str, items: list[str]) -> None:
        """Добавляет секцию с заголовком и строками, если строки есть."""
        if items:
            out.append(title)
            out.extend(f"  {x}" for x in items)
            out.append("")

    add("❌ Пропали:", removed)
    add("🆕 Появились:", added)
    add("🔄 Смена тарифа:", tariff)
    add("💰 Изменены цены:", prices)
    add("⏳ Устаревание:", dep_events)

    while out and out[-1] == "":
        out.pop()
    text = "\n".join(out)
    if len(text) > 4000:
        text = text[:3950] + "\n✂️ ...(обрезано, слишком много изменений)"
    return text


def send_tg(cfg: dict[str, str], text: str) -> None:
    """Отправляет текст в Telegram через sendMessage.

    Если токен или chat_id не заданы, отправка пропускается с предупреждением.
    Ошибки сети логируются, но не роняют скрипт.
    """
    token = cfg.get("TG_BOT_TOKEN", "").strip()
    chat = cfg.get("TG_CHAT_ID", "").strip()
    if not token or not chat:
        logger.warning("TG не настроен (TG_BOT_TOKEN/TG_CHAT_ID пустые) — уведомление пропущено")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat, "text": text}, timeout=30)
        resp.raise_for_status()
        logger.info("TG: уведомление отправлено (%d символов)", len(text))
    except requests.RequestException as err:
        safe_msg = str(err).replace(token, "<TG_TOKEN>")
        logger.error(
            "TG: не удалось отправить уведомление (%s): %s",
            type(err).__name__,
            safe_msg,
        )


def _state_shape_error(data: dict) -> str | None:
    """Проверяет форму снапшота state.json.

    Каждый источник должен быть объектом; его «models» (если есть) — объектом;
    его «deprecated» (если есть) — объектом либо null, а значения deprecated —
    строками.

    Returns:
        Описание первой найденной проблемы или None, если структура корректна.
    """
    for source, value in data.items():
        if not isinstance(value, dict):
            return f"источник {source!r} не является объектом ({type(value).__name__})"
        if "models" in value and not isinstance(value["models"], dict):
            return (
                f"models источника {source!r} не является объектом "
                f"({type(value['models']).__name__})"
            )
        if "deprecated" in value and value["deprecated"] is not None:
            deprecated = value["deprecated"]
            if not isinstance(deprecated, dict):
                return (
                    f"deprecated источника {source!r} не является объектом "
                    f"({type(deprecated).__name__})"
                )
            for name, date in deprecated.items():
                if not isinstance(name, str) or not isinstance(date, str):
                    return (
                        f"deprecated источника {source!r} содержит нестроковое "
                        f"значение для {name!r}"
                    )
    return None


def load_state() -> dict[str, SourceSnapshot] | None:
    """Читает снапшот из state.json.

    Returns:
        Словарь состояния или None, если файл отсутствует либо повреждён
        (в этом случае будет повторная инициализация).
    """
    if not os.path.exists(STATE_PATH):
        return None
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as err:
        logger.error("state.json повреждён (%s) — будет повторная инициализация", err)
        return None
    if not isinstance(data, dict):
        logger.error(
            "state.json имеет неверную структуру (%s) — будет повторная инициализация",
            type(data).__name__,
        )
        return None
    shape_error = _state_shape_error(data)
    if shape_error is not None:
        logger.error(
            "state.json имеет неверную структуру (%s) — будет повторная инициализация",
            shape_error,
        )
        return None
    return data


def save_state(state: dict[str, SourceSnapshot]) -> None:
    """Записывает снапшот состояния в state.json (атомарно).

    Данные пишутся во временный файл в том же каталоге и затем атомарно
    подменяют state.json через os.replace.
    """
    tmp_path = os.path.join(BASE_DIR, f".state.{os.getpid()}.{int(time.time() * 1000)}.tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, STATE_PATH)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def main() -> int:
    """Основной цикл: загрузка страниц, сравнение со снапшотом, лог и TG.

    При первом запуске (нет state.json) сохраняет снапшот без уведомлений.

    Returns:
        Код выхода: 0 — успех; 1 — фатальная ошибка (отрабатывается в __main__).
    """
    cfg = load_env()
    setup_logging()

    fresh: dict[str, SourceData] = {}
    for source, url in PAGES.items():
        html = fetch_html(url, HTTP_TIMEOUT)
        soup = BeautifulSoup(html, "html.parser")
        if source == "Go":
            fresh["Go"] = {"models": parse_go(soup)}
            fresh["GoPrices"] = {"models": parse_go_pricing(soup)}
        else:
            models, deprecated = parse_zen(soup)
            fresh["Zen"] = {"models": models, "deprecated": deprecated}

    now = datetime.now().astimezone()
    now_iso = now.isoformat(timespec="seconds")
    now_human = now.strftime("%Y-%m-%d %H:%M:%S")
    prev = load_state()

    if prev is None:
        state: dict[str, SourceSnapshot] = {
            s: {"fetched_at": now_iso, **data} for s, data in fresh.items()
        }
        save_state(state)
        for s, data in fresh.items():
            dep = len(data.get("deprecated") or {})
            suffix = f", {dep} записей устаревания" if dep else ""
            logger.info("Инициализация %s: %d моделей%s", s, len(data["models"]), suffix)
        logger.info("Первый запуск: снапшот сохранён в state.json, изменений нет")
        return 0

    changes: dict[str, SourceDiff] = {}
    total = 0
    for s in SOURCE_ORDER:
        if s not in fresh:
            continue
        if s not in prev:
            logger.info(
                "%s: начинаем отслеживать таблицу (%d записей), событий нет",
                s,
                len(fresh[s]["models"]),
            )
            changes[s] = {
                "removed": [],
                "added": [],
                "tariff": [],
                "prices": [],
                "deprecated": [],
            }
            continue
        old = prev[s].get("models", {})
        removed, added, tariff, prices = diff_models(
            old, fresh[s]["models"], free_tariff=(s == "Zen")
        )
        changes[s] = {
            "removed": removed,
            "added": added,
            "tariff": tariff,
            "prices": prices,
            "deprecated": [],
        }
        total += len(removed) + len(added) + len(tariff) + len(prices)
        for n in removed:
            logger.info("%s: модель пропала: %s", s, n)
        for n in added:
            logger.info("%s: модель появилась: %s", s, n)
        for old_n, new_n, label in tariff:
            logger.info("%s: смена тарифа: %s → %s (%s)", s, old_n, new_n, label)
        for name, fields in prices:
            logger.info("%s: изменены цены: %s", s, name)

    dep_events: list[DeprecatedEvent] = []
    old_dep = prev.get("Zen", {}).get("deprecated")
    new_dep = fresh["Zen"].get("deprecated")
    if new_dep is None:
        logger.warning(
            "Zen: таблица устаревания не найдена — сохраняю прежний список (%d записей)",
            len(old_dep or {}),
        )
    elif old_dep is None:
        logger.info("Zen: начинаем отслеживать таблицу устаревания (%d записей)", len(new_dep))
    else:
        for name in sorted(set(new_dep) - set(old_dep)):
            dep_events.append((name, new_dep[name], None))
            logger.info(
                "Zen: модель добавлена в список устаревающих: %s (%s)",
                name,
                new_dep[name],
            )
        for name in sorted(set(new_dep) & set(old_dep)):
            if new_dep[name] != old_dep[name]:
                dep_events.append((name, new_dep[name], old_dep[name]))
                logger.info(
                    "Zen: изменена дата устаревания %s: %s → %s",
                    name,
                    old_dep[name],
                    new_dep[name],
                )
        for name in sorted(set(old_dep) - set(new_dep)):
            dep_events.append((name, None, old_dep[name]))
            logger.info(
                "Zen: модель исключена из списка устаревания: %s (было: %s)",
                name,
                old_dep[name],
            )
    changes["Zen"]["deprecated"] = dep_events
    total += len(dep_events)

    state: dict[str, SourceSnapshot] = {s: {"fetched_at": now_iso, **fresh[s]} for s in fresh}
    if fresh["Zen"].get("deprecated") is None:
        state["Zen"]["deprecated"] = old_dep
    save_state(state)

    if total == 0:
        logger.info("Нет изменений")
        return 0

    logger.info("Найдено изменений: %d", total)
    send_tg(cfg, build_message(changes, now_human))
    return 0


if __name__ == "__main__":
    code = 0
    try:
        code = main()
    except Exception as err:
        logging.getLogger("opencode_monitor").exception("Фатальная ошибка: %s", err)
        code = 1
    trim_log()
    sys.exit(code)
