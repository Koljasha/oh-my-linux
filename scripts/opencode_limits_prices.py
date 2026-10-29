#!/usr/bin/env python3
"""Отчёт по OpenCode: таблица цен Console Models (бывш. Zen)
и таблицы лимитов/цен планов Go, Go Plus и Go Teams.

Однофайловый скрипт осознанно НЕ разбивается на модули, даже при превышении
условного потолка ~600 строк: это одна утилита «вытащить и показать таблицы»,
разрез по модулям только усложнит копирование/деплой файла на хост с cron.
Хостом изменения при доработках остаётся копия в /tmp/opencode или правка по
частям через edit.

Источники: https://opencode.ai/v2/docs/console/models/ , https://opencode.ai/v2/docs/console/go/
"""

import decimal
import os
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL_GO = "https://opencode.ai/v2/docs/console/go/"
URL_MODELS = "https://opencode.ai/v2/docs/console/models/"
URL_ZEN = URL_MODELS  # алиас для совместимости: страница Zen переехала на Console Models

# Таблицы ищутся по шапке: собираются все таблицы, чьи колонки включают весь
# набор. На странице Go таблицы разложены по вкладкам планов — панелям с
# aria-labelledby="go-requests|pricing-tab-<ключ плана>"; PageParser связывает
# маркер вкладки со следующей за ним таблицей.
GO_REQUESTS_HEADERS = {
    "Model",
    "Requests per 5 hours",
    "Requests per week",
    "Requests per month",
}
GO_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
ZEN_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
# Ключи вкладок планов на странице Go в порядке следования на сайте.
GO_PLAN_KEYS = ("go", "go-plus", "go-teams")
# Полные названия планов (как в таблице тарифов и в заголовках) и короткие
# подписи для шапки колонок, чтобы таблица умещалась на одном окне.
GO_PLAN_FULL = {"go": "Go", "go-plus": "Go Plus", "go-teams": "Go Teams"}
GO_PLAN_SHORT = {"go": "Go", "go-plus": "Plus", "go-teams": "Teams"}
PLAN_NAMES = ("Go", "Go Plus", "Go Teams")

# Таблица тарифов («$10/month») — для заголовка секции Go.
PLAN_HEADERS = {"Plan", "Price"}
PLAN_MONTH_SUFFIX = "/month"
PLAN_MONTH_LABEL = "/мес"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

GO_SORT_DESCENDING = True  # запросы плана Go в месяц: True — убывание, False — возрастание

# Цвета таблиц Go (ANSI): лимиты базового плана (Go) — приглушённый yellow
# (dim, чтобы не был броским), все остальные колонки кроме Model — светло-серый.
# Model — без цвета.
RESET = "\033[0m"
OTHER_COLOR = "\033[90m"
GO_LIMIT_COLOR = "\033[2;33m"


def colors_enabled(force: bool = False) -> bool:
    """True, если можно красить вывод ANSI.

    NO_COLOR/TERM=dumb или вывод не в терминал (pipe/файл) — без цвета,
    чтобы не мусорить escape-кодами. force (--color) перебивает проверку tty.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if force:
        return True
    return sys.stdout.isatty()


# Теги зачёркнутого текста (старое значение) и мелкого шрифта (служебное).
STRIKE_TAGS = frozenset({"del", "s", "strike"})
SMALL_TAGS = frozenset({"small"})


class HtmlTableParser(HTMLParser):
    """Парсит фрагмент HTML, содержащий одну таблицу, в список строк.

    Зачёркнутый текст (<del>, <s>, <strike>) — устаревшее значение, в ячейку
    не попадает. Мелкий шрифт (<small>) — служебная пометка (например,
    «limited time» при промо-лимите «Unlimited»), в значение тоже не
    попадает: таблица остаётся узкой и стабильной (монитор такие пометки
    также игнорирует).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: bool = False
        self._cell_text: list[str] = []
        self._strike_depth = 0
        self._small_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        """Открывающий тег: начинает строку/ячейку, учитывает strike/small/br."""
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = True
            self._cell_text = []
            self._strike_depth = 0
            self._small_depth = 0
        elif tag in STRIKE_TAGS:
            self._strike_depth += 1
        elif tag in SMALL_TAGS:
            self._small_depth += 1
        elif tag == "br" and self._cell:
            self._append(" ")

    def handle_data(self, data: str):
        """Текстовые данные внутри ячейки (strike и small пропускаются)."""
        if self._cell:
            self._append(data)

    def _append(self, data: str) -> None:
        """Добавляет текст в ячейку, игнорируя strike и small."""
        if self._strike_depth or self._small_depth:
            return
        self._cell_text.append(data)

    def handle_endtag(self, tag: str):
        """Закрывающий тег: финализирует ячейку/строку, выходит из strike/small."""
        if tag in STRIKE_TAGS:
            self._strike_depth = max(0, self._strike_depth - 1)
        elif tag in SMALL_TAGS:
            self._small_depth = max(0, self._small_depth - 1)
        elif tag in ("td", "th") and self._cell and self._row is not None:
            text = " ".join(" ".join(self._cell_text).split())
            self._row.append(text)
            self._cell = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


class PageFetcher:
    """Скачивает страницу документации OpenCode."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        """Скачивает страницу по URL и возвращает её HTML как строку."""
        req = Request(url, headers=UA)
        with urlopen(req, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")


class PageParser:
    """Находит в HTML-странице таблицы по составу колонок шапки."""

    _TABLE_TAG = re.compile(r"<(/?)table\b[^>]*>", re.IGNORECASE)
    # Панель вкладки плана: div с aria-labelledby="go-<тип>-tab-<ключ плана>",
    # сразу за ним идёт таблица этого плана.
    _PLAN_PANEL = re.compile(
        r'aria-labelledby="go-(requests|pricing)-tab-([a-z-]+)"', re.IGNORECASE
    )

    def __init__(self, page: str):
        self._page = page

    def _iter_table_spans(self, page: str):
        """Отдаёт (start, end) сбалансированных таблиц верхнего уровня.

        Глубина тегов <table>/</table> отслеживается, поэтому фрагмент не
        обрывается на </table>, встретившемся внутри ячейки. Вложенные таблицы
        не поддерживаются: попытка сообщить о них вызывающим кодом приводит к
        RuntimeError вместо тихой неверной нарезки.
        """
        depth = 0
        start = -1
        for match in self._TABLE_TAG.finditer(page):
            if not match.group(1):
                if depth == 0:
                    start = match.start()
                else:
                    raise RuntimeError(
                        "Вложенная таблица <table> не поддерживается"
                        " — структура страницы изменилась"
                    )
                depth += 1
            elif depth:
                depth -= 1
                if depth == 0:
                    yield start, match.end()

    def _iter_tables(self, page: str):
        """Отдаёт сбалансированные таблицы верхнего уровня из HTML-страницы."""
        for start, end in self._iter_table_spans(page):
            yield page[start:end]

    def find_tables(self, expected: set[str]) -> list[list[list[str]]]:
        """Возвращает все таблицы, чья шапка включает все колонки expected.

        Ожидаемые колонки — подмножество реальной шапки, поэтому дополнительные
        колонки (например, "Monthly limit") поиску не мешают.
        """
        tables = []
        for fragment in self._iter_tables(self._page):
            parser = HtmlTableParser()
            parser.feed(fragment)
            if parser.rows and expected <= set(parser.rows[0]):
                tables.append(parser.rows)
        return tables

    def find_table(self, expected: set[str]) -> list[list[str]]:
        """Возвращает строки первой таблицы, чья шапка включает колонки expected."""
        tables = self.find_tables(expected)
        if not tables:
            raise RuntimeError(
                f"Не найдена таблица с колонками {sorted(expected)} — структура страницы изменилась"
            )
        return tables[0]

    def find_plan_tables(self, expected: set[str]) -> dict[tuple[str, str], list[list[str]]]:
        """Таблицы вкладок планов: {(тип, ключ плана): строки таблицы}.

        Каждый маркер вкладки (go-requests-tab-*, go-pricing-tab-*) относится
        к ближайшей следующей за ним таблице; таблицы без подходящей шапки
        молча пропускаются — отсутствие вкладки поймает проверка в отчёте.
        """
        markers = [
            (m.start(), m.group(1), m.group(2)) for m in self._PLAN_PANEL.finditer(self._page)
        ]
        spans = list(self._iter_table_spans(self._page))
        found: dict[tuple[str, str], list[list[str]]] = {}
        for index, (pos, kind, plan) in enumerate(markers):
            following = [(s, e) for s, e in spans if s > pos]
            boundary = markers[index + 1][0] if index + 1 < len(markers) else None
            candidates = [(s, e) for s, e in following if boundary is None or s < boundary]
            if not candidates:
                continue
            start, end = candidates[0]
            parser = HtmlTableParser()
            parser.feed(self._page[start:end])
            if parser.rows and expected <= set(parser.rows[0]):
                found[(kind, plan)] = parser.rows
        return found


class ModelNameMapper:
    """Сопоставляет имена моделей из разных таблиц.

    В таблице запросов имя простое ("GPT 5.6 Luna"), а в таблице цен оно может
    быть расширено суффиксом в скобках ("GPT 5.6 Luna (≤ 272K tokens)") или
    отличаться разделителями ("MiMo-V2.5" vs "MiMo V2.5").
    """

    _SUFFIX = re.compile(r"\s*\([^)]*\)")

    @classmethod
    def base_name(cls, name: str) -> str:
        """Имя без суффикса в скобках: "GPT 5.6 Luna (≤ 272K tokens)" → "GPT 5.6 Luna"."""
        return cls._SUFFIX.sub("", name).strip()

    @classmethod
    def normalize(cls, name: str) -> str:
        """Нормализованный ключ для сравнения: только буквы и цифры в нижнем регистре."""
        return re.sub(r"[^a-z0-9]", "", cls.base_name(name).lower())


class NumberFormatter:
    """Форматирует строки чисел с разделителем тысяч."""

    _PLAIN_INT = re.compile(r"^\s*(?:\d+|\d{1,3}(?:[ \u2009\u00a0,]\d{3})+)\s*$")

    @staticmethod
    def with_thousands(value: str) -> str:
        """Форматирует число, только если вся ячейка — целое число.

        Разделители тысяч (запятая, пробел, узкий/неразрывный пробел) и
        окружающие пробелы допускаются. Если в ячейке есть посторонний текст
        (например, склеенное "26,000 26,000"), значение возвращается без
        изменений, чтобы не собрать число из чужих цифр.
        """
        if not NumberFormatter._PLAIN_INT.match(value):
            return value
        digits = re.sub(r"[^\d]", "", value)
        return f"{int(digits):,}".replace(",", "\u2009")


class TableRenderer:
    """Форматирует таблицу в текст с выровненными колонками и разделителем.

    separators — список строк длиной n-1, задающий разделитель между каждой
    парой соседних колонок (позволяет вставить, например, " || " между
    группами колонок). column_colors — список длиной n: ANSI-код цвета для
    каждой колонки или ""/None — без цвета. Цвет оборачивается поверх уже
    выровненной ячейки, поэтому ширина колонок не разъезжается.
    """

    @staticmethod
    def render(
        header: list[str],
        rows: list[list[str]],
        separators: list[str] | None = None,
        column_colors: list[str] | None = None,
    ) -> str:
        n = len(header)
        for index, row in enumerate([header, *rows]):
            if len(row) != n:
                role = "шапка" if index == 0 else f"строка #{index}"
                raise RuntimeError(
                    f"{role} таблицы содержит {len(row)} колонок, ожидалось {n}: {row!r}"
                )
        if separators is None:
            separators = [" | "] * (n - 1)
        if column_colors is None:
            column_colors = [""] * n
        table = [header] + rows
        widths = [max(len(str(row[i])) for row in table) for i in range(n)]

        def paint(cell: str, color: str | None) -> str:
            return f"{color}{cell}{RESET}" if color else cell

        def join_row(cells: list[str]) -> str:
            return cells[0] + "".join(sep + cell for sep, cell in zip(separators, cells[1:]))

        padded = [[str(cell).ljust(widths[i]) for i, cell in enumerate(row)] for row in table]
        colored = [[paint(cell, column_colors[i]) for i, cell in enumerate(row)] for row in padded]
        sep_line = join_row([paint("-" * w, column_colors[i]) for i, w in enumerate(widths)])
        return "\n".join([join_row(colored[0]), sep_line, *(join_row(r) for r in colored[1:])])


class GoLimits:
    """Данные таблиц запросов и цен трёх планов: Go, Go Plus, Go Teams.

    Таблицы передаются словарями по ключам вкладок (go / go-plus / go-teams).
    Цены и окна токенов у планов совпадают, различаются месячные лимиты и
    число запросов. Вывод разбит на две таблицы: «лимиты» (запросы трёх
    планов + кратности к Go) и «цены» (цены за 1M токенов + месячный лимит
    каждого плана). Порядок строк у обеих таблиц общий, задаётся _ordered_keys()
    и зависит только от содержимого строк запросов/цен.
    """

    # Колонки запросов в исходной таблице планов.
    _REQUEST_COLS = (
        "Requests per 5 hours",
        "Requests per week",
        "Requests per month",
    )
    # Базовый план: сортировка, кратности и имя строк по умолчанию берутся из него.
    _BASE_PLAN = "go"
    # Колонка месячного лимита в таблице цен каждого плана.
    _MONTHLY = "Monthly limit"

    def __init__(
        self,
        requests_tables: dict[str, list[list[str]]],
        pricing_tables: dict[str, list[list[str]]],
        descending: bool = True,
    ):
        missing = [
            plan
            for plan in GO_PLAN_KEYS
            if plan not in requests_tables or plan not in pricing_tables
        ]
        if missing:
            raise RuntimeError(
                "Нет таблиц запросов/цен для планов «" + ", ".join(missing) + "»"
                " — структура страницы изменилась"
            )
        self._descending = descending
        self._request_header = requests_tables[self._BASE_PLAN][0]
        self._pricing_header = pricing_tables[self._BASE_PLAN][0]
        self._output_idx = self._pricing_header.index("Output")
        self._request_idx: dict[str, dict[str, int]] = {}
        self._requests: dict[str, list[list[str]]] = {}
        self._requests_by_name: dict[str, dict[str, list[str]]] = {}
        for plan in GO_PLAN_KEYS:
            header = requests_tables[plan][0]
            self._request_idx[plan] = {name: header.index(name) for name in self._REQUEST_COLS}
            rows = requests_tables[plan][1:]
            self._requests[plan] = rows
            self._requests_by_name[plan] = self._index_by_name(rows, GO_PLAN_FULL[plan])
        self._pricing = pricing_tables[self._BASE_PLAN][1:]
        self._monthly_idx = {
            plan: pricing_tables[plan][0].index(self._MONTHLY) for plan in GO_PLAN_KEYS
        }
        # Месячный лимит плана ищется по нормализованному имени строки цен.
        # Нормализация снимает суффикс в скобках, поэтому несколько строк одной
        # модели (окна токенов, «(50% off)») дают один ключ — побеждает последняя
        # строка таблицы; сегодня у этих строк месячный лимит одинаковый, при
        # расходящихся лимитах понадобится точное сопоставление по имени.
        self._monthly_by_name: dict[str, dict[str, str]] = {
            plan: {
                ModelNameMapper.normalize(row[0]): row[self._monthly_idx[plan]]
                for row in pricing_tables[plan][1:]
            }
            for plan in GO_PLAN_KEYS
        }
        self._pricing_by_name: dict[str, list[list[str]]] = {}
        for row in self._pricing:
            self._pricing_by_name.setdefault(ModelNameMapper.normalize(row[0]), []).append(row)

    @staticmethod
    def _index_by_name(rows: list[list[str]], plan: str) -> dict[str, list[str]]:
        """Индексирует строки запросов по нормализованному имени модели.

        Совпадение двух моделей внутри одного плана делает сопоставление
        неоднозначным — это признак изменившейся структуры страницы.
        """
        indexed: dict[str, list[str]] = {}
        counts: dict[str, int] = {}
        for row in rows:
            key = ModelNameMapper.normalize(row[0])
            counts[key] = counts.get(key, 0) + 1
            indexed[key] = row
        duplicates = sorted(key for key, count in counts.items() if count > 1)
        if duplicates:
            raise RuntimeError(
                f"В таблице запросов ({plan}) несколько моделей совпадают после"
                f" нормализации ({', '.join(duplicates)}) — сопоставление"
                " с ценами неоднозначно, структура страницы изменилась"
            )
        return indexed

    _UNLIMITED = re.compile(r"\bunlimited\b", re.IGNORECASE)

    _FIRST_NUMBER = re.compile(r"\d[\d \u2009\u00a0,]*\d|\d")

    def _number_of(self, cell: str) -> int | None:
        """Первое число ячейки (разделители тысяч допустимы), иначе None.

        Берётся именно первое число, а не все цифры ячейки: примечание вроде
        «31,580 (50% off)» иначе склеилось бы в 315 850.
        """
        match = self._FIRST_NUMBER.search(cell)
        if match is None:
            return None
        return int(re.sub(r"[^\d]", "", match.group(0)))

    def _month_value(self, row: list[str], month_idx: int) -> tuple[int, int]:
        """Ключ сортировки по числу запросов в месяц.

        Числовые значения сравниваются по величине. «Unlimited» числа не
        имеет и трактуется как неограниченное число запросов: при сортировке
        по убыванию такие модели идут первыми, при возрастании — последними.
        """
        try:
            cell = row[month_idx]
        except IndexError:
            raise RuntimeError(
                f"Не удалось прочитать количество запросов в месяц в строке: {row!r}"
            )
        if self._UNLIMITED.search(cell):
            return (1, 0)
        month = self._number_of(cell)
        if month is None:
            raise RuntimeError(
                f"Не удалось прочитать количество запросов в месяц в строке: {row!r}"
            )
        return (0, month)

    def _ratio(self, go_cell: str, other_cell: str) -> str:
        """Кратность месячных запросов плана к Go («3x»).

        Число берётся из ячеек обоих планов; «Unlimited» или нечисловая ячейка
        (включая пустую) даёт «-» — кратность не определена. Нецелые значения
        округляются до одного знака («2.5x»).
        """
        go = self._month_value_only(go_cell)
        other = self._month_value_only(other_cell)
        if go is None or other is None or go == 0:
            return "-"
        ratio = other / go
        if abs(ratio - round(ratio)) < 1e-9:
            return f"{round(ratio)}x"
        return f"{ratio:.1f}x"

    def _month_value_only(self, cell: str) -> int | None:
        """Число месячных запросов из ячейки; «Unlimited»/нечисловое → None."""
        if self._UNLIMITED.search(cell):
            return None
        return self._number_of(cell)

    _FREE = re.compile(r"\bfree\b", re.IGNORECASE)

    def _price_value(self, row: list[str]) -> decimal.Decimal:
        """Числовое значение цены из колонки Output строки таблицы цен.

        Берётся первое числовое слово ячейки (регулярное выражение
        "\\d[\\d.]*"), поэтому примечание вроде "$0.60 (x2)" не искажает цену.
        Бесплатная модель («Free», без числа) получает 0 — она дешевле любой
        платной и в отсортированном списке идёт первой.
        """
        try:
            cell = row[self._output_idx]
        except IndexError:
            raise RuntimeError(f"Не удалось прочитать цену Output в строке: {row!r}")
        match = re.search(r"\d[\d.]*", cell)
        if match is None:
            if self._FREE.search(cell):
                return decimal.Decimal(0)
            raise RuntimeError(f"Не удалось прочитать цену Output в строке: {row!r}")
        try:
            return decimal.Decimal(match.group(0))
        except decimal.InvalidOperation:
            raise RuntimeError(f"Не удалось прочитать цену Output в строке: {row!r}")

    def _sorted_requests(self) -> list[list[str]]:
        """Строки запросов базового плана, отсортированные по запросам в месяц.

        Направление задаётся параметром descending: True — убывание,
        False — возрастание.
        """
        month_idx = self._request_idx[self._BASE_PLAN][self._REQUEST_COLS[2]]
        return sorted(
            self._requests[self._BASE_PLAN],
            key=lambda row: self._month_value(row, month_idx),
            reverse=self._descending,
        )

    def _ordered_keys(self) -> list[str]:
        """Порядок моделей таблиц Go (един для таблиц лимитов и цен).

        Сначала модели базового плана по запросам в месяц с учётом направления
        сортировки, затем модели остальных планов, найденные только в них,
        затем строки цен без строк запросов — несовпадающие строки обоих типов
        идут в конце.
        """
        keys = [ModelNameMapper.normalize(row[0]) for row in self._sorted_requests()]
        seen = set(keys)
        for plan in GO_PLAN_KEYS[1:]:
            new = sorted(set(self._requests_by_name[plan]) - seen)
            keys += new
            seen.update(new)
        new = sorted(set(self._pricing_by_name) - seen)
        keys += new
        seen.update(new)
        return keys

    def _fmt(self, value: str) -> str:
        """Отображение значения: «Unlimited» → «∞» (экономит 8 колонок
        ширины), целые числа — с разделителем тысяч.
        """
        if self._UNLIMITED.search(value):
            return "∞"
        return NumberFormatter.with_thousands(value)

    def _requests_name(self, key: str) -> str | None:
        """Имя модели из строк запросов планов (в порядке следования планов)."""
        for plan in GO_PLAN_KEYS:
            row = self._requests_by_name[plan].get(key)
            if row is not None:
                return row[0]
        return None

    def limits_header(self) -> list[str]:
        """Шапка таблицы лимитов: окна запросов и кратности к Go.

        Обычная Go — все три окна (5 ч / неделя / месяц), как и раньше,
        ничего из данных не убираем (см. задачу). В Go Plus и Go Teams шапка
        не дробится (экономия ширины), для них — только месячные запросы.
        """
        header = ["Model", "Go: 5 ч", "нед", "мес"]
        header += [GO_PLAN_SHORT[plan] for plan in GO_PLAN_KEYS[1:]]
        header += [f"{GO_PLAN_SHORT[plan]}/Go" for plan in GO_PLAN_KEYS[1:]]
        return header

    def limits_colors(self) -> list[str]:
        """Цвета колонок таблицы лимитов: лимит базового плана — dim yellow."""
        colors = ["", GO_LIMIT_COLOR, GO_LIMIT_COLOR, GO_LIMIT_COLOR]
        colors += [OTHER_COLOR] * (len(GO_PLAN_KEYS) - 1)
        colors += [OTHER_COLOR] * (len(GO_PLAN_KEYS) - 1)
        return colors

    def limits_rows(self) -> list[list[str]]:
        """Строки таблицы лимитов в порядке _ordered_keys().

        Для обычной Go — все три окна; для Go Plus и Go Teams — месяц.
        Модель без строк запросов в каком-то плане получает «-» в колонках
        этого плана; кратность также «-», пока нет строк обоих планов.
        """
        month = self._REQUEST_COLS[2]
        rows: list[list[str]] = []
        for key in self._ordered_keys():
            cells = []
            for plan in GO_PLAN_KEYS:
                row = self._requests_by_name[plan].get(key)
                idx = self._request_idx[plan]
                if row is None:
                    cells.extend(["-"] * (3 if plan == self._BASE_PLAN else 1))
                    continue
                if plan == self._BASE_PLAN:
                    cells.extend(self._fmt(row[idx[name]]) for name in self._REQUEST_COLS)
                else:
                    cells.append(self._fmt(row[idx[month]]))
            ratios = []
            for plan in GO_PLAN_KEYS[1:]:
                go_row = self._requests_by_name[self._BASE_PLAN].get(key)
                other_row = self._requests_by_name[plan].get(key)
                ratios.append(
                    "-"
                    if go_row is None or other_row is None
                    else self._ratio(
                        go_row[self._request_idx[self._BASE_PLAN][month]],
                        other_row[self._request_idx[plan][month]],
                    )
                )
            requests_name = self._requests_name(key)
            if requests_name is not None:
                name = requests_name
            else:
                # Модели без строк запросов — имя из самого дешёвого окна цен.
                pricing = self._pricing_by_name.get(key)
                name = min(pricing, key=self._price_value)[0] if pricing else "-"
            rows.append([name, *cells, *ratios])
        return rows

    def pricing_header(self) -> list[str]:
        """Шапка таблицы цен: цены за 1M токенов + месячный лимит планов.

        Колонка «Monthly limit» таблицы каждого плана переименована в
        «Лимит <план>» и поднята в конец шапки.
        """
        prices = [name for name in self._pricing_header[1:] if name != self._MONTHLY]
        return ["Model", *prices, *(f"Лимит {GO_PLAN_FULL[plan]}" for plan in GO_PLAN_KEYS)]

    def pricing_colors(self) -> list[str]:
        """Цвета колонок таблицы цен: месячный лимит базового плана — dim yellow."""
        prices = len(self._pricing_header) - 2  # без Model и Monthly limit
        colors = [""] + [OTHER_COLOR] * prices
        colors += [
            GO_LIMIT_COLOR if plan == self._BASE_PLAN else OTHER_COLOR for plan in GO_PLAN_KEYS
        ]
        return colors

    def pricing_rows(self) -> list[list[str]]:
        """Строки таблицы цен в порядке _ordered_keys().

        Каждая строка цен (окно токенов, промо) — отдельная строка. Месячный
        лимит берётся из собственной таблицы базового плана, а для остальных
        планов — по нормализованному имени строки; без совпадения — «-».
        """
        rows: list[list[str]] = []
        for key in self._ordered_keys():
            price_rows = sorted(self._pricing_by_name.get(key, []), key=self._price_value)
            for price_row in price_rows:
                name = price_row[0]
                limits = []
                for plan in GO_PLAN_KEYS:
                    if plan == self._BASE_PLAN:
                        limits.append(self._fmt(price_row[self._monthly_idx[plan]]))
                    else:
                        limits.append(
                            self._fmt(
                                self._monthly_by_name[plan].get(
                                    ModelNameMapper.normalize(name), "-"
                                )
                            )
                        )
                # Колонки цен без Monthly limit — он уходит в колонки «Лимит …».
                body = [
                    price_row[i]
                    for i in range(1, len(price_row))
                    if i != self._monthly_idx[self._BASE_PLAN]
                ]
                rows.append([name, *body, *limits])
        return rows


class ZenPricing:
    """Данные таблицы цен Console Models (бывш. Zen), отсортированные по названию модели.

    Бесплатные модели выводятся сверху, затем остальные. Строки одной модели
    (разные окна контекста) остаются рядом и в исходном порядке благодаря
    стабильной сортировке по нормализованному имени.
    """

    def __init__(self, pricing_table: list[list[str]]):
        self.header = pricing_table[0]
        self._rows = pricing_table[1:]
        self._input_idx = self.header.index("Input")

    def _is_free(self, row: list[str]) -> bool:
        """Проверяет, бесплатна ли модель (колонка Input равна 'free')."""
        return row[self._input_idx].strip().lower() == "free"

    def sorted_rows(self) -> list[list[str]]:
        """Free-модели сверху, затем остальные; внутри групп — по имени модели."""
        return sorted(
            self._rows,
            key=lambda row: (
                0 if self._is_free(row) else 1,
                ModelNameMapper.normalize(row[0]),
            ),
        )


class OpenCodeReport:
    """Собирает итоговый отчёт: таблица цен Models, затем таблицы лимитов
    и цен планов Go (Go, Go Plus, Go Teams)."""

    COLUMN_SEPARATOR = " | "
    GROUP_SEPARATOR = " || "

    def __init__(self, go_page: str, zen_page: str, use_color: bool = False):
        go_parser = PageParser(go_page)
        zen_parser = PageParser(zen_page)
        requests_tables = go_parser.find_plan_tables(GO_REQUESTS_HEADERS)
        pricing_tables = go_parser.find_plan_tables(GO_PRICING_HEADERS)
        for kind, tables, expected in (
            ("requests", requests_tables, GO_REQUESTS_HEADERS),
            ("pricing", pricing_tables, GO_PRICING_HEADERS),
        ):
            found = {plan for k, plan in tables if k == kind}
            if found != set(GO_PLAN_KEYS):
                raise RuntimeError(
                    f"Ожидались таблицы {sorted(expected)} по вкладкам планов"
                    f" {', '.join(GO_PLAN_KEYS)}, найдено: {', '.join(sorted(found)) or 'ничего'}"
                    " — структура страницы изменилась"
                )
        self._limits = GoLimits(
            {plan: requests_tables[("requests", plan)] for plan in GO_PLAN_KEYS},
            {plan: pricing_tables[("pricing", plan)] for plan in GO_PLAN_KEYS},
            GO_SORT_DESCENDING,
        )
        self._plan_prices = self._plan_prices_from(go_parser)
        self._zen = ZenPricing(zen_parser.find_table(ZEN_PRICING_HEADERS))
        self._use_color = use_color

    @staticmethod
    def _plan_prices_from(go_parser: PageParser) -> dict[str, str]:
        """Читает цены тарифов из таблицы «Plan | Price | Included usage».

        Возвращает {"Go": "$10/мес", ...} — подписи для заголовка секции Go.
        Отсутствие таблицы или одного из планов — это изменившаяся структура
        страницы, ошибка сообщается вызывающему коду.
        """
        rows = go_parser.find_table(PLAN_HEADERS)
        prices = {row[0].strip(): row[1].strip() for row in rows[1:] if len(row) >= 2}
        missing = [plan for plan in PLAN_NAMES if plan not in prices]
        if missing or set(prices) - set(PLAN_NAMES):
            raise RuntimeError(
                "В таблице тарифов лишние или недостающие планы («"
                + ", ".join(missing or sorted(set(prices) - set(PLAN_NAMES)))
                + "») — структура страницы изменилась"
            )
        return {
            plan: prices[plan].replace(PLAN_MONTH_SUFFIX, PLAN_MONTH_LABEL) for plan in PLAN_NAMES
        }

    def _limits_separators(self) -> list[str]:
        """Разделители таблицы лимитов: групповой после окон Go и перед кратностями."""
        n = len(self._limits.limits_header())
        separators = [self.COLUMN_SEPARATOR] * (n - 1)
        # Граница после группы окон Go (3 колонки — все _REQUEST_COLS).
        separators[len(self._limits._REQUEST_COLS)] = self.GROUP_SEPARATOR
        # Граница перед первой колонкой кратности (их len(GO_PLAN_KEYS) - 1).
        separators[n - (len(GO_PLAN_KEYS) - 1) - 1] = self.GROUP_SEPARATOR
        return separators

    def _pricing_separators(self) -> list[str]:
        """Разделители таблицы цен: групповой перед колонками месячных лимитов."""
        n = len(self._limits.pricing_header())
        separators = [self.COLUMN_SEPARATOR] * (n - 1)
        separators[n - len(GO_PLAN_KEYS) - 1] = self.GROUP_SEPARATOR
        return separators

    def _render_limits(self) -> str:
        """Возвращает таблицу лимитов запросов трёх планов с заголовком."""
        header = self._limits.limits_header()
        colors = self._limits.limits_colors() if self._use_color else None
        table = TableRenderer.render(
            header,
            self._limits.limits_rows(),
            separators=self._limits_separators(),
            column_colors=colors,
        )
        plans = ", ".join(f"{name} ({self._plan_prices[name]})" for name in PLAN_NAMES)
        title = (
            f"Go-планы: {plans}:\n"
            "лимиты запросов (по убыванию, план Go; у Go — все окна"
            " 5 ч / неделя / месяц, у Plus и Teams — месяц):"
        )
        return f"{title}\n{table}"

    def _render_go_pricing(self) -> str:
        """Возвращает таблицу цен и месячных лимитов планов с заголовком."""
        header = self._limits.pricing_header()
        colors = self._limits.pricing_colors() if self._use_color else None
        table = TableRenderer.render(
            header,
            self._limits.pricing_rows(),
            separators=self._pricing_separators(),
            column_colors=colors,
        )
        return f"Go-планы: цены за 1M токенов и месячные лимиты (порядок строк — таблица лимитов ниже):\n{table}"

    def _render_zen(self) -> str:
        """Возвращает таблицу цен Models с заголовком."""
        title = "Console Models (бывш. Zen): цены за 1M токенов (сначала бесплатные, затем по алфавиту):"
        column_colors = (
            ["" if name == "Model" else OTHER_COLOR for name in self._zen.header]
            if self._use_color
            else None
        )
        return f"{title}\n{TableRenderer.render(self._zen.header, self._zen.sorted_rows(), column_colors=column_colors)}"

    def render(self) -> str:
        """Возвращает полный отчёт: таблица Models, затем цены и лимиты планов Go.

        Порядок секций: Models (Zen) → цены планов Go → лимиты запросов планов.
        """
        return f"{self._render_zen()}\n\n{self._render_go_pricing()}\n\n{self._render_limits()}"


def main() -> int:
    """Скачивает страницы Go/Models, печатает отчёт; 0 — успех, 1 — ошибка."""
    try:
        force_color = "--color" in sys.argv or "--color=always" in sys.argv
        no_color = "--no-color" in sys.argv or "--no-colour" in sys.argv
        use_color = colors_enabled(force=force_color) and not no_color
        fetcher = PageFetcher()
        go_page = fetcher.fetch(URL_GO)
        zen_page = fetcher.fetch(URL_ZEN)
        print(OpenCodeReport(go_page, zen_page, use_color=use_color).render())
        return 0
    except Exception as exc:  # noqa: BLE001 — CLI-обёртка: сбой сети или разбора → код 1
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
