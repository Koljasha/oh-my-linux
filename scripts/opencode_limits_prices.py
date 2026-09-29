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
UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

GO_SORT_DESCENDING = (
    True  # запросы плана Go в месяц: True — от большего к меньшему, False — наоборот
)

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
    """Данные таблиц запросов (Go и Go Plus) и цен, логика их сопоставления.

    Первая таблица запросов относится к плану Go, вторая — к Go Plus. Цены
    берутся из первой (Go) таблицы цен: они совпадают у обоих планов.
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
        descending: bool = True,
    ):
        self.go_requests_header = go_requests_table[0]
        self.plus_requests_header = plus_requests_table[0]
        self.pricing_header = pricing_table[0]
        self._output_idx = self.pricing_header.index("Output")
        self._month_idx = self.go_requests_header.index(self._REQUESTS_MONTH)
        self._go_requests = go_requests_table[1:]
        self._plus_requests = plus_requests_table[1:]
        self._pricing = pricing_table[1:]
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
        """Шапка единой таблицы: запросы по периодам (Go, Go Plus), затем цены."""
        return [
            "Model",
            "Go: 5 hours",
            "Go Plus: 5 hours",
            "Go: week",
            "Go Plus: week",
            "Go: month",
            "Go Plus: month",
            *self.pricing_header[1:],
        ]

    def combined_rows(self) -> list[list[str]]:
        """Строки единой таблицы в порядке, заданном _ordered_keys().

        Колонки запросов группируются по периодам: для каждого периода
        сначала значения плана Go, затем Go Plus. Колонки запросов
        повторяются для каждой строки цен одной модели. Модель без строк цен
        получает "-" в колонках цен; модель без строки запросов в одном из
        планов — "-" в колонках этого плана.
        """
        go_empty = ["-"] * (len(self.go_requests_header) - 1)
        plus_empty = ["-"] * (len(self.plus_requests_header) - 1)
        pricing_empty = ["-"] * (len(self.pricing_header) - 1)

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
            price_rows = sorted(self._pricing_by_name.get(key, []), key=self._price_value)
            if price_rows:
                for price_row in price_rows:
                    result.append([price_row[0], *period_vals, *price_row[1:]])
            else:
                source = go_row if go_row is not None else plus_row
                name = source[0] if source is not None else "-"
                result.append([name, *period_vals, *pricing_empty])
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

    def __init__(self, go_page: str, zen_page: str):
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
            GO_SORT_DESCENDING,
        )
        self._zen = ZenPricing(zen_parser.find_table(ZEN_PRICING_HEADERS))

    def _separators(self) -> list[str]:
        """Разделители колонок: групповой между запросами и ценами."""
        header = self._limits.combined_header()
        separators = [self.COLUMN_SEPARATOR] * (len(header) - 1)
        separators[len(header) - len(self._limits.pricing_header)] = self.GROUP_SEPARATOR
        return separators

    def _render_go(self) -> str:
        """Возвращает единую таблицу Go и Go Plus с заголовком."""
        table = TableRenderer.render(
            self._limits.combined_header(),
            self._limits.combined_rows(),
            separators=self._separators(),
        )
        order = "по убыванию" if GO_SORT_DESCENDING else "по возрастанию"
        title = (
            "Go и Go Plus: лимиты запросов и цены за 1M токенов"
            f" ({order} запросов в месяц, план Go):"
        )
        return f"{title}\n{table}"

    def _render_zen(self) -> str:
        """Возвращает таблицу цен Zen с заголовком."""
        title = "Zen: цены за 1M токенов (сначала бесплатные, затем по алфавиту):"
        return f"{title}\n{TableRenderer.render(self._zen.header, self._zen.sorted_rows())}"

    def render(self) -> str:
        """Возвращает полный отчёт: таблица Zen, затем единая таблица Go и Go Plus."""
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
