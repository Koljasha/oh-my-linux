#!/usr/bin/env python3
"""Отчёт по OpenCode: таблица цен Zen и единая таблица лимитов/цен Go.

Источники: https://opencode.ai/docs/en/zen/ , https://opencode.ai/docs/en/go/
"""

import decimal
import re
import sys
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL_GO = "https://opencode.ai/docs/en/go/"
URL_ZEN = "https://opencode.ai/docs/en/zen/"

# Таблицы ищутся по шапке: берётся первая таблица, чьи колонки включают весь набор.
GO_REQUESTS_HEADERS = {
    "Model",
    "requests per 5 hour",
    "requests per week",
    "requests per month",
}
GO_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
ZEN_PRICING_HEADERS = {"Model", "Input", "Output", "Cached Read", "Cached Write"}
UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

GO_SORT_DESCENDING = True  # запросы Go: True — от большего к меньшему, False — наоборот

# Теги зачёркнутого текста (старое значение) и мелкого шрифта (примечание).
STRIKE_TAGS = frozenset({"del", "s", "strike"})
SMALL_TAGS = frozenset({"small"})


class HtmlTableParser(HTMLParser):
    """Парсит фрагмент HTML, содержащий одну таблицу, в список строк.

    Зачёркнутый текст (<del>, <s>, <strike>) — устаревшее значение, в ячейку
    не попадает. Мелкий шрифт (<small>) — примечание, выводится в скобках
    после основного текста, например "$60 (4x · Ends Sep 20)".
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: bool = False
        self._cell_text: list[str] = []
        self._cell_note: list[str] = []
        self._strike_depth = 0
        self._small_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        """Открывающий тег: начинает строку/ячейку, учитывает strike/small/br."""
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = True
            self._cell_text = []
            self._cell_note = []
            self._strike_depth = 0
            self._small_depth = 0
        elif tag in STRIKE_TAGS:
            self._strike_depth += 1
        elif tag in SMALL_TAGS:
            self._small_depth += 1
        elif tag == "br" and self._cell:
            self._append(" ")

    def handle_data(self, data: str):
        """Текстовые данные внутри ячейки (с учётом strike/small)."""
        if self._cell:
            self._append(data)

    def _append(self, data: str) -> None:
        """Добавляет текст в тело ячейки или в примечание (small), игнорит strike."""
        if self._strike_depth:
            return
        if self._small_depth:
            self._cell_note.append(data)
        else:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str):
        """Закрывающий тег: финализирует ячейку/строку, выходит из strike/small."""
        if tag in STRIKE_TAGS:
            self._strike_depth = max(0, self._strike_depth - 1)
        elif tag in SMALL_TAGS:
            self._small_depth = max(0, self._small_depth - 1)
        elif tag in ("td", "th") and self._cell and self._row is not None:
            text = " ".join(" ".join(self._cell_text).split())
            note = " ".join(" ".join(self._cell_note).split())
            if note:
                text = f"{text} ({note})".strip()
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

    def find_table(self, expected: set[str]) -> list[list[str]]:
        """Возвращает строки первой таблицы, чья шапка включает все колонки expected.

        Ожидаемые колонки — подмножество реальной шапки, поэтому дополнительные
        колонки (например, "Monthly limit") поиску не мешают.
        """
        for fragment in self._iter_tables(self._page):
            parser = HtmlTableParser()
            parser.feed(fragment)
            if parser.rows and expected <= set(parser.rows[0]):
                return parser.rows
        raise RuntimeError(
            f"Не найдена таблица с колонками {sorted(expected)} — структура страницы изменилась"
        )


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
        окружающие пробелы допускаются. Если в ячейке есть текст примечания
        (например, "26,000 (4x · Ends Sep 20)"), значение возвращается без
        изменений, чтобы не собрать число из посторонних цифр.
        """
        if not NumberFormatter._PLAIN_INT.match(value):
            return value
        digits = re.sub(r"[^\d]", "", value)
        return f"{int(digits):,}".replace(",", "\u2009")


class TableRenderer:
    """Форматирует таблицу в текст с выровненными колонками и разделителем.

    separators — список строк длиной n-1, задающий разделитель между каждой
    парой соседних колонок (позволяет вставить, например, " || " между
    группами колонок).
    """

    @staticmethod
    def render(
        header: list[str], rows: list[list[str]], separators: list[str] | None = None
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
        table = [header] + rows
        widths = [max(len(str(row[i])) for row in table) for i in range(n)]

        def join_row(cells: list[str]) -> str:
            return cells[0] + "".join(sep + cell for sep, cell in zip(separators, cells[1:]))

        padded = [[str(cell).ljust(widths[i]) for i, cell in enumerate(row)] for row in table]
        sep_line = join_row(["-" * w for w in widths])
        return "\n".join([join_row(padded[0]), sep_line, *(join_row(r) for r in padded[1:])])


class GoLimits:
    """Данные обеих таблиц и логика их сортировки и сопоставления."""

    def __init__(
        self,
        requests_table: list[list[str]],
        pricing_table: list[list[str]],
        descending: bool = True,
    ):
        self.requests_header = requests_table[0]
        self.pricing_header = pricing_table[0]
        self._output_idx = self.pricing_header.index("Output")
        self._month_idx = self.requests_header.index("requests per month")
        self._requests = requests_table[1:]
        self._pricing = pricing_table[1:]
        self._descending = descending

    _UNLIMITED = re.compile(r"\bunlimited\b", re.IGNORECASE)

    def _month_value(self, row: list[str]) -> tuple[int, int]:
        """Ключ сортировки по числу запросов в месяц.

        Числовые значения сравниваются по величине. «Unlimited» числа не
        имеет и трактуется как неограниченное число запросов: при сортировке
        по убыванию такие модели идут первыми, при возрастании — последними.
        """
        try:
            cell = row[self._month_idx]
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
        """Строки запросов, отсортированные по запросам в месяц.

        Направление задаётся параметром descending: True — убывание,
        False — возрастание.
        """
        return sorted(self._requests, key=self._month_value, reverse=self._descending)

    def sorted_model_names(self) -> list[str]:
        """Имена моделей в порядке отсортированных запросов."""
        return [row[0] for row in self.sorted_requests()]

    def combined_header(self) -> list[str]:
        """Шапка единой таблицы: колонки запросов, затем колонки цен."""
        return [*self.requests_header, *self.pricing_header[1:]]

    def combined_rows(self) -> list[list[str]]:
        """Строки единой таблицы в порядке, заданном sorted_model_names().

        Колонки запросов повторяются для каждой строки цен одной модели.
        Модель без строк цен получает "-" в колонках цен; строка цен без
        соответствия в запросах выводится в конце с "-" в колонках запросов.
        """
        counts: dict[str, int] = {}
        for row in self._requests:
            key = ModelNameMapper.normalize(row[0])
            counts[key] = counts.get(key, 0) + 1
        duplicates = sorted(key for key, count in counts.items() if count > 1)
        if duplicates:
            raise RuntimeError(
                "В таблице запросов несколько моделей совпадают после"
                f" нормализации ({', '.join(duplicates)}) — сопоставление"
                " с ценами неоднозначно, структура страницы изменилась"
            )

        grouped: dict[str, list[list[str]]] = {}
        for row in self._pricing:
            grouped.setdefault(ModelNameMapper.normalize(row[0]), []).append(row)

        requests_by_name = {row[0]: row for row in self._requests}
        pricing_empty = ["-"] * (len(self.pricing_header) - 1)
        requests_empty = ["-"] * (len(self.requests_header) - 1)

        result: list[list[str]] = []
        for model in self.sorted_model_names():
            req_row = requests_by_name[model]
            req_vals = [NumberFormatter.with_thousands(c) for c in req_row[1:]]
            price_rows = sorted(
                grouped.pop(ModelNameMapper.normalize(model), []), key=self._price_value
            )
            if price_rows:
                for price_row in price_rows:
                    result.append([price_row[0], *req_vals, *price_row[1:]])
            else:
                result.append([model, *req_vals, *pricing_empty])

        for price_rows in grouped.values():
            for price_row in sorted(price_rows, key=self._price_value):
                result.append([price_row[0], *requests_empty, *price_row[1:]])
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
    """Собирает итоговый отчёт: таблица цен Zen, затем единая таблица Go."""

    COLUMN_SEPARATOR = " | "
    GROUP_SEPARATOR = " || "

    def __init__(self, go_page: str, zen_page: str):
        go_parser = PageParser(go_page)
        zen_parser = PageParser(zen_page)
        requests_table = go_parser.find_table(GO_REQUESTS_HEADERS)
        pricing_table = go_parser.find_table(GO_PRICING_HEADERS)
        self._limits = GoLimits(requests_table, pricing_table, GO_SORT_DESCENDING)
        self._zen = ZenPricing(zen_parser.find_table(ZEN_PRICING_HEADERS))

    def _separators(self) -> list[str]:
        """Разделители колонок: групповой между лимитами и ценами."""
        header = self._limits.combined_header()
        separators = [self.COLUMN_SEPARATOR] * (len(header) - 1)
        separators[len(self._limits.requests_header) - 1] = self.GROUP_SEPARATOR
        return separators

    def _render_go(self) -> str:
        """Возвращает единую таблицу Go с заголовком."""
        table = TableRenderer.render(
            self._limits.combined_header(),
            self._limits.combined_rows(),
            separators=self._separators(),
        )
        order = "по убыванию" if GO_SORT_DESCENDING else "по возрастанию"
        title = f"Go: лимиты запросов и цены за 1M токенов ({order} запросов в месяц):"
        return f"{title}\n{table}"

    def _render_zen(self) -> str:
        """Возвращает таблицу цен Zen с заголовком."""
        title = "Zen: цены за 1M токенов (сначала бесплатные, затем по алфавиту):"
        return f"{title}\n{TableRenderer.render(self._zen.header, self._zen.sorted_rows())}"

    def render(self) -> str:
        """Возвращает полный отчёт: таблица Zen, затем единая таблица Go."""
        return f"{self._render_zen()}\n\n{self._render_go()}"


def main() -> int:
    """Скачивает страницы Go/Zen, печатает отчёт; 0 — успех, 1 — ошибка."""
    try:
        fetcher = PageFetcher()
        go_page = fetcher.fetch(URL_GO)
        zen_page = fetcher.fetch(URL_ZEN)
        print(OpenCodeReport(go_page, zen_page).render())
        return 0
    except Exception as exc:  # noqa: BLE001 — CLI-обёртка: сбой сети или разбора → код 1
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
