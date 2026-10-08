#!/usr/bin/env python3
"""Отчёт по OpenCode: таблица цен Zen и единая таблица лимитов/цен Go.

Источники: https://opencode.ai/docs/en/zen/ , https://opencode.ai/docs/en/go/
"""

import decimal
import os
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL_GO = "https://opencode.ai/docs/en/go/"
URL_ZEN = "https://opencode.ai/docs/en/zen/"

# Таблицы ищутся по шапке: собираются все таблицы, чьи колонки включают весь
# набор. На странице Go ожидается по две такие таблицы каждого типа: первая
# относится к плану Go, вторая — к Go Plus.
GO_REQUESTS_HEADERS = {
    "Model",
    "Requests per 5 hours",
    "Requests per week",
    "Requests per month",
}
GO_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
ZEN_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
# Таблица тарифов («$10/month», «$40/month») — для заголовка секции Go.
PLAN_HEADERS = {"Plan", "Price"}
PLAN_MONTH_SUFFIX = "/month"
PLAN_MONTH_LABEL = "/мес"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

GO_SORT_DESCENDING = (
    True  # запросы плана Go в месяц: True — от большего к меньшему, False — наоборот
)

# Цвета единой таблицы Go (ANSI): лимиты Go — приглушённый yellow (dim,
# чтобы не был броским), все остальные колонки кроме Model — светло-серый.
# Model — без цвета.
RESET = "\033[0m"
OTHER_COLOR = "\033[90m"
GO_LIMIT_COLOR = "\033[2;33m"
# Точное совпадение имён из combined_header(). "Monthly limit" — колонка цен
# плана Go; "Monthly limit (Go Plus)" красится как "остальная" (серая).
GO_LIMIT_HEADERS = frozenset({"Go: 5 hours", "Go: week", "Go: month", "Monthly limit"})


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


def color_for_header(name: str) -> str:
    """Цвет колонки Go-таблицы по имени шапки; "" — без цвета."""
    if name in GO_LIMIT_HEADERS:
        return GO_LIMIT_COLOR
    if name == "Model":
        return ""
    return OTHER_COLOR


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

    def __init__(self, page: str):
        self._page = page

    def _iter_tables(self, page: str):
        """Отдаёт сбалансированные таблицы верхнего уровня из HTML-страницы.

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
                    yield page[start : match.end()]

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
        column_colors: list[str | None] | None = None,
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
    """Данные таблиц запросов (Go и Go Plus) и цен, логика их сопоставления.

    Первая таблица запросов относится к плану Go, вторая — к Go Plus. Цены
    берутся из Go-таблицы цен (у обоих планов совпадают), а Monthly limit —
    из Go- и Go Plus-таблиц: у планов он различается.
    """

    # Подписи колонок запросов в единой таблице: план + окно лимита.
    _REQUESTS_5H = "Requests per 5 hours"
    _REQUESTS_WEEK = "Requests per week"
    _REQUESTS_MONTH = "Requests per month"

    def __init__(
        self,
        go_requests_table: list[list[str]],
        plus_requests_table: list[list[str]],
        pricing_table: list[list[str]],
        plus_pricing_table: list[list[str]],
        descending: bool = True,
    ):
        self.go_requests_header = go_requests_table[0]
        self.plus_requests_header = plus_requests_table[0]
        self.pricing_header = pricing_table[0]
        self._output_idx = self.pricing_header.index("Output")
        self._month_idx = self.go_requests_header.index(self._REQUESTS_MONTH)
        self._plus_month_idx = self.plus_requests_header.index(self._REQUESTS_MONTH)
        self._go_requests = go_requests_table[1:]
        self._plus_requests = plus_requests_table[1:]
        self._pricing = pricing_table[1:]
        self._plus_pricing_header = plus_pricing_table[0]
        self._plus_monthly_idx = self._plus_pricing_header.index("Monthly limit")
        # Monthly limit у планов различается (Go $60 → Go Plus $180), поэтому
        # для строки цен с точным именем («GPT 6 Luna (≤ 272K tokens)») смотрим
        # значение именно из Go Plus-таблицы по тому же имени.
        self._plus_monthly_by_name: dict[str, str] = {}
        for row in plus_pricing_table[1:]:
            if len(row) > self._plus_monthly_idx:
                self._plus_monthly_by_name[ModelNameMapper.normalize(row[0])] = row[
                    self._plus_monthly_idx
                ]
        self._descending = descending
        self._go_by_name = self._index_by_name(self._go_requests, "Go")
        self._plus_by_name = self._index_by_name(self._plus_requests, "Go Plus")
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
        digits = re.sub(r"[^\d]", "", cell)
        if not digits:
            raise RuntimeError(
                f"Не удалось прочитать количество запросов в месяц в строке: {row!r}"
            )
        return (0, int(digits))

    def _ratio(self, go_cell: str, plus_cell: str) -> str:
        """Кратность месячных запросов Go Plus к Go («3x»).

        Число берётся из ячеек обеих планов; «Unlimited» или нечисловая ячейка
        (включая пустую) даёт «-» — кратность не определена. Нецелые значения
        округляются до одного знака («2.5x»).
        """
        go = self._month_value_only(go_cell)
        plus = self._month_value_only(plus_cell)
        if go is None or plus is None or go == 0:
            return "-"
        ratio = plus / go
        if abs(ratio - round(ratio)) < 1e-9:
            return f"{round(ratio)}x"
        return f"{ratio:.1f}x"

    def _month_value_only(self, cell: str) -> int | None:
        """Число месячных запросов из ячейки; «Unlimited»/нечисловое → None."""
        if self._UNLIMITED.search(cell):
            return None
        digits = re.sub(r"[^\d]", "", cell)
        return int(digits) if digits else None

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

    def sorted_requests(self) -> list[list[str]]:
        """Строки запросов плана Go, отсортированные по запросам в месяц.

        Направление задаётся параметром descending: True — убывание,
        False — возрастание.
        """
        return sorted(
            self._go_requests,
            key=lambda row: self._month_value(row, self._month_idx),
            reverse=self._descending,
        )

    def _ordered_keys(self) -> list[str]:
        """Порядок моделей единой таблицы.

        Сначала модели плана Go по запросам в месяц с учётом направления
        сортировки, затем модели, найденные только в Go Plus, затем строки
        цен без строк запросов — несовпадающие строки обоих типов идут в конце.
        """
        keys = [ModelNameMapper.normalize(row[0]) for row in self.sorted_requests()]
        keys += sorted(key for key in self._plus_by_name if key not in self._go_by_name)
        keys += sorted(
            key
            for key in self._pricing_by_name
            if key not in self._go_by_name and key not in self._plus_by_name
        )
        seen: set[str] = set()
        unique: list[str] = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique.append(key)
        return unique

    def combined_header(self) -> list[str]:
        """Шапка единой таблицы: запросы по периодам (Go, Go Plus), кратность, цены."""
        return [
            "Model",
            "Go: 5 hours",
            "Go Plus: 5 hours",
            "Go: week",
            "Go Plus: week",
            "Go: month",
            "Go Plus: month",
            "Кратность",
            *self.pricing_header[1:],
            self._plus_pricing_header[self._plus_monthly_idx] + " (Go Plus)",
        ]

    def combined_rows(self) -> list[list[str]]:
        """Строки единой таблицы в порядке, заданном _ordered_keys().

        Колонки запросов группируются по периодам: для каждого периода
        сначала значения плана Go, затем Go Plus. Колонки запросов
        повторяются для каждой строки цен одной модели. Monthly limit Go Plus
        ищется по точному имени строки цен (имя с суффиксом окна токенов).
        Модель без строк цен получает "-" в колонках цен; модель без строки
        запросов в одном из планов — "-" в колонках этого плана.
        """
        go_empty = ["-"] * (len(self.go_requests_header) - 1)
        plus_empty = ["-"] * (len(self.plus_requests_header) - 1)
        pricing_empty = ["-"] * (len(self.pricing_header) - 1) + ["-"]

        result: list[list[str]] = []
        for key in self._ordered_keys():
            go_row = self._go_by_name.get(key)
            plus_row = self._plus_by_name.get(key)
            go_vals = (
                [NumberFormatter.with_thousands(c) for c in go_row[1:]] if go_row else go_empty
            )
            plus_vals = (
                [NumberFormatter.with_thousands(c) for c in plus_row[1:]]
                if plus_row
                else plus_empty
            )
            # По периодам: 5 часов (Go, Go Plus), неделя (Go, Go Plus), месяц.
            period_vals = [
                go_vals[0],
                plus_vals[0],
                go_vals[1],
                plus_vals[1],
                go_vals[2],
                plus_vals[2],
            ]
            go_requests = self._go_by_name.get(key)
            plus_requests = self._plus_by_name.get(key)
            ratio = (
                "-"
                if go_requests is None or plus_requests is None
                else self._ratio(go_requests[self._month_idx], plus_requests[self._plus_month_idx])
            )
            price_rows = sorted(self._pricing_by_name.get(key, []), key=self._price_value)
            if price_rows:
                for price_row in price_rows:
                    plus_monthly = self._plus_monthly_by_name.get(
                        ModelNameMapper.normalize(price_row[0]), "-"
                    )
                    result.append([price_row[0], *period_vals, ratio, *price_row[1:], plus_monthly])
            else:
                source = go_row if go_row is not None else plus_row
                name = source[0] if source is not None else "-"
                result.append([name, *period_vals, ratio, *pricing_empty])
        return result


class ZenPricing:
    """Данные таблицы цен Zen, отсортированные по названию модели.

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
    """Собирает итоговый отчёт: таблица цен Zen, затем единая таблица Go и Go Plus."""

    COLUMN_SEPARATOR = " | "
    GROUP_SEPARATOR = " || "

    def __init__(self, go_page: str, zen_page: str, use_color: bool = False):
        go_parser = PageParser(go_page)
        zen_parser = PageParser(zen_page)
        requests_tables = go_parser.find_tables(GO_REQUESTS_HEADERS)
        pricing_tables = go_parser.find_tables(GO_PRICING_HEADERS)
        if len(requests_tables) != 2 or len(pricing_tables) != 2:
            raise RuntimeError(
                "Ожидались по две таблицы запросов и цен Go"
                f" (найдено {len(requests_tables)} и {len(pricing_tables)})"
                " — структура страницы изменилась"
            )
        self._limits = GoLimits(
            requests_tables[0],
            requests_tables[1],
            pricing_tables[0],
            pricing_tables[1],
            GO_SORT_DESCENDING,
        )
        self._plan_prices = self._plan_prices_from(go_parser)
        self._zen = ZenPricing(zen_parser.find_table(ZEN_PRICING_HEADERS))
        self._use_color = use_color

    @staticmethod
    def _plan_prices_from(go_parser: PageParser) -> dict[str, str]:
        """Читает цены тарифов из таблицы «Plan | Price | Included usage».

        Возвращает {"Go": "$10/мес", "Go Plus": "$40/мес"} — подписи для
        заголовка секции Go. Отсутствие таблицы или одного из планов — это
        изменившаяся структура страницы, ошибка сообщается вызывающему коду.
        """
        rows = go_parser.find_table(PLAN_HEADERS)
        prices = {row[0].strip(): row[1].strip() for row in rows[1:] if len(row) >= 2}
        missing = [plan for plan in ("Go", "Go Plus") if plan not in prices]
        if missing:
            raise RuntimeError(
                "В таблице тарифов не хватает планов «" + ", ".join(missing) + "»"
                " — структура страницы изменилась"
            )
        return {
            plan: prices[plan].replace(PLAN_MONTH_SUFFIX, PLAN_MONTH_LABEL)
            for plan in ("Go", "Go Plus")
        }

    def _separators(self) -> list[str]:
        """Разделители колонок: групповой между запросами и ценами."""
        header = self._limits.combined_header()
        separators = [self.COLUMN_SEPARATOR] * (len(header) - 1)
        # Ценовая группа = колонки цен Go (len(pricing_header) - 1) плюс
        # Monthly limit (Go Plus); разделитель стоит перед её первой колонкой.
        price_columns = len(self._limits.pricing_header)
        separators[len(header) - price_columns - 1] = self.GROUP_SEPARATOR
        return separators

    def _render_go(self) -> str:
        """Возвращает единую таблицу Go и Go Plus с заголовком."""
        header = self._limits.combined_header()
        column_colors = [color_for_header(name) for name in header] if self._use_color else None
        table = TableRenderer.render(
            header,
            self._limits.combined_rows(),
            separators=self._separators(),
            column_colors=column_colors,
        )
        order = "по убыванию" if GO_SORT_DESCENDING else "по возрастанию"
        title = (
            f"Go ({self._plan_prices['Go']}) и Go Plus ({self._plan_prices['Go Plus']}):"
            " лимиты запросов и цены за 1M токенов"
            f" ({order} запросов в месяц, план Go):"
        )
        return f"{title}\n{table}"

    def _render_zen(self) -> str:
        """Возвращает таблицу цен Zen с заголовком."""
        title = "Zen: цены за 1M токенов (сначала бесплатные, затем по алфавиту):"
        column_colors = (
            ["" if name == "Model" else OTHER_COLOR for name in self._zen.header]
            if self._use_color
            else None
        )
        return f"{title}\n{TableRenderer.render(self._zen.header, self._zen.sorted_rows(), column_colors=column_colors)}"

    def render(self) -> str:
        """Возвращает полный отчёт: таблица Zen, затем единая таблица Go и Go Plus."""
        return f"{self._render_zen()}\n\n{self._render_go()}"


def main() -> int:
    """Скачивает страницы Go/Zen, печатает отчёт; 0 — успех, 1 — ошибка."""
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
