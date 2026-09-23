#!/usr/bin/env python3
"""Конвертер закладок между форматами Firefox и Chromium.

Поддерживает двунаправленную конверсию. Направление автоматически
определяется по структуре входного файла; его можно явно задать через
``--to``.

В Firefox три типа узлов: контейнер (папка), place (URL-закладка) и
separator (разделитель). В Chromium нет типа «разделитель», поэтому
разделители Firefox сохраняются как обычная URL-закладка, указывающая на
``javascript:void(0)`` и имеющая имя из длинной строки чёрточек. И имя,
и URL для замены разделителя можно переопределить через аргументы
командной строки. При обратной конверсии любой URL из списка известных
URL-разделителей снова превращается в настоящий разделитель Firefox.

Использование::

    ./converter.py <input.json> [-o output.json] [--to {firefox,chromium,auto}]

Пути вывода по умолчанию:

- Firefox на входе   ->  ``<каталог_входа>/Bookmarks-Chromium.json``
- Chromium на входе  ->  ``<каталог_входа>/Bookmarks-Firefox.json``
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# Псевдоним типа для распарсенного JSON-объекта. Использование ``Any`` для
# значений честно отражает динамическую природу JSON; сужение типа
# происходит на границе конверсии.
JsonDict = dict[str, Any]


# ===========================================================================
# Константы — конверсия времени
# ===========================================================================

# Микросекунды между эпохой Windows (1601-01-01) и эпохой Unix (1970-01-01).
# Chromium хранит время как микросекунды с 1601; Firefox — как микросекунды
# с 1970. Прибавление/вычитание этого смещения переводит между двумя
# представлениями.
EPOCH_OFFSET_US = 11_644_473_600_000_000


# ===========================================================================
# Константы — формат Chromium
# ===========================================================================

CHROMIUM_FORMAT_VERSION = 1

# Три фиксированных корневых слота Chromium в каноническом порядке.
CHROMIUM_ROOT_SLOTS: tuple[str, ...] = ("bookmark_bar", "other", "synced")

# Локализованные отображаемые имена корневых папок Chromium (ru).
CHROMIUM_ROOT_NAMES: dict[str, str] = {
    "bookmark_bar": "Панель закладок",
    "other": "Другие закладки",
    "synced": "Мобильные закладки",
}


# ===========================================================================
# Константы — формат Firefox
# ===========================================================================

# Идентификаторы типов узлов Firefox.
FIREFOX_TYPE_CONTAINER = "text/x-moz-place-container"
FIREFOX_TYPE_URL = "text/x-moz-place"
FIREFOX_TYPE_SEPARATOR = "text/x-moz-place-separator"

# Фиксированные GUID, которые Firefox ожидает на своих корневых папках.
FIREFOX_ROOT_GUIDS: dict[str, str] = {
    "placesRoot": "root________",
    "bookmarksMenuFolder": "menu________",
    "toolbarFolder": "toolbar_____",
    "unfiledBookmarksFolder": "unfiled_____",
    "mobileFolder": "mobile______",
}

# Обычные заголовки, которые Firefox использует для корневых папок в JSON-экспорте.
FIREFOX_ROOT_TITLES: dict[str, str] = {
    "bookmarksMenuFolder": "menu",
    "toolbarFolder": "toolbar",
    "unfiledBookmarksFolder": "unfiled",
    "mobileFolder": "mobile",
}

# Канонический порядок корневых папок Firefox в массиве children объекта placesRoot.
FIREFOX_ROOT_ORDER: tuple[str, ...] = (
    "bookmarksMenuFolder",
    "toolbarFolder",
    "unfiledBookmarksFolder",
    "mobileFolder",
)

# Позиция каждой корневой папки Firefox внутри массива children её родителя.
FIREFOX_ROOT_INDEX: dict[str, int] = {
    "bookmarksMenuFolder": 0,
    "toolbarFolder": 1,
    "unfiledBookmarksFolder": 2,
    "mobileFolder": 3,
}


# ===========================================================================
# Константы — соответствие корневых папок между форматами
# ===========================================================================

# Идентификатор корневой папки Firefox -> слот корневой папки Chromium.
# Папки ``menu`` и ``unfiled`` Firefox обе попадают в слот ``other`` Chromium,
# потому что у Chromium нет отдельного понятия «меню». На прямом пути сначала
# идут дети menu, затем дети unfiled, склеенные внутри ``other``.
FIREFOX_TO_CHROMIUM_ROOT: dict[str, str] = {
    "toolbarFolder": "bookmark_bar",
    "bookmarksMenuFolder": "other",
    "unfiledBookmarksFolder": "other",
    "mobileFolder": "synced",
}

# Слот корневой папки Chromium -> идентификатор корневой папки Firefox (обратный путь).
# ``other`` отображается на ``unfiledBookmarksFolder``, потому что папка
# «Другие закладки» Firefox семантически ближе всего к «Other Bookmarks» Chromium.
CHROMIUM_TO_FIREFOX_ROOT: dict[str, str] = {
    "bookmark_bar": "toolbarFolder",
    "other": "unfiledBookmarksFolder",
    "synced": "mobileFolder",
}


# ===========================================================================
# Константы — обработка разделителей
# ===========================================================================

# Замена по умолчанию для разделителей Firefox при выводе в Chromium.
DEFAULT_SEPARATOR_NAME = "——————————"
DEFAULT_SEPARATOR_URL = "javascript:void(0)"

# Список URL, которые на обратном пути мы считаем «заменителями разделителя»
# в Chromium-файле. Включает текущий и исторический дефолты, чтобы ранее
# сгенерированные Chromium-файлы корректно проходили обратную конверсию,
# даже если дефолт со временем изменился.
KNOWN_SEPARATOR_URLS: frozenset[str] = frozenset(
    {
        DEFAULT_SEPARATOR_URL,
        "chrome://newtab/",
    }
)


# ===========================================================================
# Исключения
# ===========================================================================


class ConversionError(Exception):
    """Возникает, когда узел закладок невозможно преобразовать между форматами."""


# ===========================================================================
# Конфигурация
# ===========================================================================


@dataclass(frozen=True)
class SeparatorConfig:
    """Пользовательская настройка замены для узлов-разделителей Firefox."""

    name: str = DEFAULT_SEPARATOR_NAME
    url: str = DEFAULT_SEPARATOR_URL


# ===========================================================================
# Генераторы идентификаторов
# ===========================================================================


class IdGenerator:
    """Последовательный генератор целочисленных идентификаторов.

    И Firefox, и Chromium назначают целочисленные ID обходом дерева в
    глубину (pre-order). Firefox хранит их как int, Chromium — как строки.
    Этот генератор отдаёт int; вызывающий код приводит тип при необходимости.
    """

    def __init__(self, start: int = 1) -> None:
        self._next = start

    def take(self) -> int:
        """Возвращает следующий целочисленный идентификатор."""
        current = self._next
        self._next += 1
        return current


class GuidGenerator(Protocol):
    """Генератор уникальных идентификаторов для узлов закладок."""

    def __next__(self) -> str:
        """Возвращает следующий идентификатор."""
        ...  # pragma: no cover - protocol


class FirefoxGuidGenerator:
    """Генератор GUID в стиле Firefox: 12 символов base64url.

    GUID Firefox — это 12 символов base64url от 9 случайных байт (72 бита).
    Корневые папки используют фиксированные специальные GUID, которые
    обрабатываются отдельно в конвертере.
    """

    def __next__(self) -> str:
        """Возвращает следующий GUID в стиле Firefox."""
        raw = secrets.token_bytes(9)
        # 9 байт -> ровно 12 символов base64, без паддинга.
        return base64.urlsafe_b64encode(raw).decode("ascii")[:12]


class ChromiumGuidGenerator:
    """Генератор GUID в стиле Chromium: строки UUID v4."""

    def __next__(self) -> str:
        """Возвращает следующий GUID в стиле Chromium."""
        return str(uuid.uuid4())


# ===========================================================================
# Конверсия времени
# ===========================================================================


class TimestampConverter:
    """Перевод между временными представлениями Firefox и Chromium."""

    @staticmethod
    def firefox_to_chromium(firefox_us: int) -> str:
        """Firefox (мкс с 1970) -> строка Chromium (мкс с 1601)."""
        if firefox_us <= 0:
            return "0"
        return str(firefox_us + EPOCH_OFFSET_US)

    @staticmethod
    def chromium_to_firefox(chromium_str: str) -> int:
        """Строка Chromium (мкс с 1601) -> int Firefox (мкс с 1970)."""
        try:
            chromium_us = int(chromium_str)
        except (TypeError, ValueError):
            return 0
        if chromium_us <= EPOCH_OFFSET_US:
            return 0
        return chromium_us - EPOCH_OFFSET_US


# ===========================================================================
# Вспомогательные функции
# ===========================================================================


def _as_int(value: Any) -> int:
    """Лучшее усилие по приведению произвольного значения к int; 0 при неудаче."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ===========================================================================
# Firefox -> Chromium
# ===========================================================================


class FirefoxToChromiumConverter:
    """Преобразует распарсенное дерево закладок Firefox в дерево Chromium."""

    def __init__(
        self,
        separator: SeparatorConfig,
        ids: IdGenerator | None = None,
        guids: ChromiumGuidGenerator | None = None,
    ) -> None:
        self._separator = separator
        self._ids = ids or IdGenerator()
        self._guids = guids or ChromiumGuidGenerator()

    def convert(self, firefox_root: JsonDict) -> JsonDict:
        """Собирает законченный документ закладок Chromium."""
        roots = self._convert_roots(firefox_root)
        # Chromium ожидает все три слота присутствующими, даже пустыми.
        for slot in CHROMIUM_ROOT_SLOTS:
            if slot not in roots:
                roots[slot] = self._empty_root(slot)
        return {
            "checksum": "",
            "roots": roots,
            "version": CHROMIUM_FORMAT_VERSION,
        }

    # -- Обработка корневого уровня --

    def _convert_roots(self, firefox_root: JsonDict) -> dict[str, JsonDict]:
        """Отображает корневые папки Firefox верхнего уровня на три слота Chromium."""
        slots: dict[str, JsonDict] = {}
        for child in firefox_root.get("children", []) or []:
            root_id = child.get("root")
            slot = FIREFOX_TO_CHROMIUM_ROOT.get(root_id)
            if slot is None:
                print(
                    f"предупреждение: неизвестная корневая папка Firefox {root_id!r}, пропускаем",
                    file=sys.stderr,
                )
                continue
            converted = self._convert_root_folder(child, slot)
            if slot == "other" and "other" in slots:
                # menu и unfiled оба отображаются на other: склеиваем их детей.
                slots["other"]["children"].extend(converted["children"])
            else:
                slots[slot] = converted
        return slots

    def _convert_root_folder(self, node: JsonDict, slot: str) -> JsonDict:
        """Конвертирует корневую папку Firefox в корневую папку Chromium."""
        folder_id = self._ids.take()
        children = [self._convert_node(child) for child in node.get("children", []) or []]
        return {
            "children": children,
            "date_added": TimestampConverter.firefox_to_chromium(_as_int(node.get("dateAdded"))),
            "date_last_used": "0",
            "guid": next(self._guids),
            "id": str(folder_id),
            "name": CHROMIUM_ROOT_NAMES.get(slot, node.get("title", "") or ""),
            "type": "folder",
        }

    def _empty_root(self, slot: str) -> JsonDict:
        """Создаёт пустую корневую папку Chromium для отсутствующего корня Firefox."""
        return {
            "children": [],
            "date_added": "0",
            "date_last_used": "0",
            "guid": next(self._guids),
            "id": str(self._ids.take()),
            "name": CHROMIUM_ROOT_NAMES[slot],
            "type": "folder",
        }

    # -- Диспетчеризация по узлам --

    def _convert_node(self, node: JsonDict) -> JsonDict:
        """Диспетчеризация узла Firefox по типу (separator/container/url)."""
        node_type = node.get("type")
        if node_type == FIREFOX_TYPE_SEPARATOR:
            return self._make_separator(node)
        if node_type == FIREFOX_TYPE_CONTAINER:
            return self._make_folder(node)
        if node_type == FIREFOX_TYPE_URL:
            return self._make_url(node)
        raise ConversionError(f"Неизвестный тип узла Firefox: {node_type!r}")

    def _make_separator(self, node: JsonDict) -> JsonDict:
        """Заменяет разделитель Firefox URL-закладкой Chromium."""
        return {
            "date_added": TimestampConverter.firefox_to_chromium(_as_int(node.get("dateAdded"))),
            "date_last_used": "0",
            "guid": next(self._guids),
            "id": str(self._ids.take()),
            "name": self._separator.name,
            "type": "url",
            "url": self._separator.url,
        }

    def _make_url(self, node: JsonDict) -> JsonDict:
        """Конвертирует узел-URL Firefox в узел-URL Chromium."""
        uri = node.get("uri")
        if not uri:
            raise ConversionError(
                f"У узла-URL Firefox отсутствует 'uri': guid={node.get('guid')!r}"
            )
        return {
            "date_added": TimestampConverter.firefox_to_chromium(_as_int(node.get("dateAdded"))),
            "date_last_used": "0",
            "guid": next(self._guids),
            "id": str(self._ids.take()),
            "name": node.get("title", "") or "",
            "type": "url",
            "url": uri,
        }

    def _make_folder(self, node: JsonDict) -> JsonDict:
        """Конвертирует узел-контейнер Firefox в папку Chromium."""
        folder_id = self._ids.take()
        children = [self._convert_node(child) for child in node.get("children", []) or []]
        return {
            "children": children,
            "date_added": TimestampConverter.firefox_to_chromium(_as_int(node.get("dateAdded"))),
            "date_last_used": "0",
            "guid": next(self._guids),
            "id": str(folder_id),
            "name": node.get("title", "") or "",
            "type": "folder",
        }


# ===========================================================================
# Chromium -> Firefox
# ===========================================================================


class ChromiumToFirefoxConverter:
    """Преобразует распарсенное дерево закладок Chromium в дерево Firefox."""

    def __init__(
        self,
        separator: SeparatorConfig,
        ids: IdGenerator | None = None,
        guids: FirefoxGuidGenerator | None = None,
    ) -> None:
        self._separator = separator
        self._ids = ids or IdGenerator()
        self._guids = guids or FirefoxGuidGenerator()

    def convert(self, chromium_data: JsonDict) -> JsonDict:
        """Собирает законченный документ закладок Firefox."""
        # Резервируем id=1 для placesRoot первым, следуя соглашению самого
        # Firefox: у корневого узла всегда самый маленький ID.
        places_root_id = self._ids.take()
        roots_in = chromium_data.get("roots", {})
        # Отображаем каждый слот Chromium на идентификатор корневой папки
        # Firefox (только для слотов, в которых реально есть данные во входе).
        slot_to_firefox: dict[str, JsonDict] = {
            CHROMIUM_TO_FIREFOX_ROOT[slot]: roots_in[slot]
            for slot in CHROMIUM_ROOT_SLOTS
            if roots_in.get(slot)
        }
        # Всегда выводим все четыре корневые папки Firefox, даже пустые, чтобы
        # итоговый файл выглядел как настоящий экспорт Firefox.
        children: list[JsonDict] = [
            self._convert_root_folder(firefox_root_id, slot_to_firefox.get(firefox_root_id))
            for firefox_root_id in FIREFOX_ROOT_ORDER
        ]
        return self._build_places_root(children, places_root_id)

    # -- Обработка корневого уровня --

    def _build_places_root(
        self,
        children: list[JsonDict],
        places_root_id: int,
    ) -> JsonDict:
        """Собирает корневой узел верхнего уровня Firefox (placesRoot)."""
        return {
            "guid": FIREFOX_ROOT_GUIDS["placesRoot"],
            "title": "",
            "index": 0,
            "dateAdded": 0,
            "lastModified": 0,
            "id": places_root_id,
            "typeCode": 2,
            "type": FIREFOX_TYPE_CONTAINER,
            "root": "placesRoot",
            "children": children,
        }

    def _convert_root_folder(
        self,
        firefox_root_id: str,
        node: JsonDict | None,
    ) -> JsonDict:
        """Конвертирует корневую папку Chromium в корневую папку Firefox.

        Если ``node`` равен None (в Chromium не было данных для этого слота),
        выдаём пустую корневую папку Firefox без ключа ``children``, что
        соответствует формату экспорта самого Firefox для пустых корней.
        """
        node_id = self._ids.take()
        date_added = self._extract_date_added(node)
        result: JsonDict = {
            "guid": FIREFOX_ROOT_GUIDS[firefox_root_id],
            "title": FIREFOX_ROOT_TITLES[firefox_root_id],
            "index": FIREFOX_ROOT_INDEX[firefox_root_id],
            "dateAdded": date_added,
            "lastModified": date_added,
            "id": node_id,
            "typeCode": 2,
            "type": FIREFOX_TYPE_CONTAINER,
            "root": firefox_root_id,
        }
        if node is not None:
            children = [
                self._convert_node(child, i)
                for i, child in enumerate(node.get("children", []) or [])
            ]
            if children:
                result["children"] = children
        return result

    # -- Диспетчеризация по узлам --

    def _convert_node(self, node: JsonDict, index: int) -> JsonDict:
        """Диспетчеризация узла Chromium по типу (url/folder)."""
        node_type = node.get("type")
        if node_type == "url":
            if self._looks_like_separator(node):
                return self._make_separator(node, index)
            return self._make_url(node, index)
        if node_type == "folder":
            return self._make_container(node, index)
        raise ConversionError(f"Неизвестный тип узла Chromium: {node_type!r}")

    def _looks_like_separator(self, node: JsonDict) -> bool:
        """Определяет URL-закладку Chromium, заменяющую разделитель Firefox."""
        url = node.get("url", "")
        return url in KNOWN_SEPARATOR_URLS or url == self._separator.url

    def _make_separator(self, node: JsonDict, index: int) -> JsonDict:
        """Конвертирует заменитель разделителя Chromium обратно в разделитель Firefox."""
        date_added = self._extract_date_added(node)
        return {
            "guid": next(self._guids),
            "title": "",
            "index": index,
            "dateAdded": date_added,
            "lastModified": date_added,
            "id": self._ids.take(),
            "typeCode": 3,
            "type": FIREFOX_TYPE_SEPARATOR,
        }

    def _make_url(self, node: JsonDict, index: int) -> JsonDict:
        """Конвертирует узел-URL Chromium в узел-URL Firefox."""
        url = node.get("url")
        if not url:
            raise ConversionError(
                f"У узла-URL Chromium отсутствует 'url': guid={node.get('guid')!r}"
            )
        date_added = self._extract_date_added(node)
        return {
            "guid": next(self._guids),
            "title": node.get("name", "") or "",
            "index": index,
            "dateAdded": date_added,
            "lastModified": date_added,
            "id": self._ids.take(),
            "typeCode": 1,
            "type": FIREFOX_TYPE_URL,
            "uri": url,
        }

    def _make_container(self, node: JsonDict, index: int) -> JsonDict:
        """Конвертирует узел-папку Chromium в узел-контейнер Firefox."""
        date_added = self._extract_date_added(node)
        result: JsonDict = {
            "guid": next(self._guids),
            "title": node.get("name", "") or "",
            "index": index,
            "dateAdded": date_added,
            "lastModified": date_added,
            "id": self._ids.take(),
            "typeCode": 2,
            "type": FIREFOX_TYPE_CONTAINER,
        }
        children = [
            self._convert_node(child, i) for i, child in enumerate(node.get("children", []) or [])
        ]
        if children:
            result["children"] = children
        return result

    def _extract_date_added(self, node: JsonDict | None) -> int:
        """Достаёт и конвертирует значение ``date_added`` Chromium; 0 при отсутствии."""
        if node is None:
            return 0
        return TimestampConverter.chromium_to_firefox(str(node.get("date_added", "0") or "0"))


# ===========================================================================
# Статистика по узлам
# ===========================================================================


@dataclass
class NodeStats:
    """Подсчёт типов узлов закладок в распарсенном дереве."""

    urls: int = 0
    folders: int = 0
    separators: int = 0

    def __str__(self) -> str:
        return f"{self.urls} URL, {self.folders} папок, {self.separators} разделителей"


class FirefoxNodeCounter:
    """Обходит дерево закладок Firefox и считает узлы по типам."""

    def count(self, root: JsonDict) -> NodeStats:
        """Считает узлы в дереве Firefox, начиная с корневых детей."""
        stats = NodeStats()
        for child in root.get("children", []) or []:
            self._walk(child, stats)
        return stats

    def _walk(self, node: JsonDict, stats: NodeStats) -> None:
        """Рекурсивно учитывает узел Firefox и его детей в статистике."""
        node_type = node.get("type")
        if node_type == FIREFOX_TYPE_URL:
            stats.urls += 1
        elif node_type == FIREFOX_TYPE_SEPARATOR:
            stats.separators += 1
        elif node_type == FIREFOX_TYPE_CONTAINER:
            stats.folders += 1
            for child in node.get("children", []) or []:
                self._walk(child, stats)


class ChromiumNodeCounter:
    """Обходит дерево закладок Chromium и считает узлы по типам."""

    def count(self, data: JsonDict) -> NodeStats:
        """Считает узлы во всех корневых слотах Chromium."""
        stats = NodeStats()
        for slot in CHROMIUM_ROOT_SLOTS:
            slot_node = data.get("roots", {}).get(slot)
            if not slot_node:
                continue
            stats.folders += 1  # сама корневая папка
            for child in slot_node.get("children", []) or []:
                self._walk(child, stats)
        return stats

    def _walk(self, node: JsonDict, stats: NodeStats) -> None:
        """Рекурсивно учитывает узел Chromium и его детей в статистике."""
        node_type = node.get("type")
        if node_type == "url":
            # В Chromium нет типа «разделитель»; для целей статистики считаем
            # известные URL-разделители как разделители.
            if node.get("url") in KNOWN_SEPARATOR_URLS:
                stats.separators += 1
            else:
                stats.urls += 1
        elif node_type == "folder":
            stats.folders += 1
            for child in node.get("children", []) or []:
                self._walk(child, stats)


# ===========================================================================
# Определение направления конверсии
# ===========================================================================


class DirectionDetector:
    """Определяет входной формат распарсенного документа закладок."""

    @staticmethod
    def detect(data: JsonDict) -> str:
        """Возвращает входной формат (``'firefox'`` или ``'chromium'``).

        Выбрасывает ``ConversionError``, если вход не соответствует ни одной
        из схем.
        """
        if not isinstance(data, dict):
            raise ConversionError("входной файл не является JSON-объектом")
        if "roots" in data and "version" in data:
            return "chromium"
        if data.get("type") == FIREFOX_TYPE_CONTAINER and "root" in data:
            return "firefox"
        raise ConversionError(
            "не удалось определить формат входного файла: ключи верхнего "
            "уровня не соответствуют ни Firefox (ожидался "
            "type=text/x-moz-place-container), ни Chromium (ожидалось "
            "roots+version)"
        )

    @staticmethod
    def target_for(input_format: str) -> str:
        """Возвращает выходной формат, обратный входному."""
        if input_format == "firefox":
            return "chromium"
        if input_format == "chromium":
            return "firefox"
        raise ConversionError(f"неизвестный входной формат: {input_format!r}")

    @staticmethod
    def label(input_format: str, output_format: str) -> str:
        """Возвращает человекочитаемую метку направления, например 'Firefox -> Chromium'."""
        names = {
            "firefox": "Firefox",
            "chromium": "Chromium",
        }
        src = names.get(input_format, input_format)
        dst = names.get(output_format, output_format)
        return f"{src} -> {dst}"


# ===========================================================================
# CLI-приложение
# ===========================================================================


class BookmarkConverterApp:
    """Точка входа командной строки для конверсии закладок."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self._args = self._parse_args(argv)

    def run(self) -> int:
        """Выполняет конверсию. Возвращает код завершения процесса."""
        if not self._args.input.is_file():
            print(
                f"ошибка: входной файл не найден: {self._args.input}",
                file=sys.stderr,
            )
            return 2

        try:
            data = self._load_input(self._args.input)
        except ConversionError as exc:
            print(f"ошибка: {exc}", file=sys.stderr)
            return 1

        try:
            input_format = DirectionDetector.detect(data)
            output_format = self._resolve_output_format(data, self._args.to)
        except ConversionError as exc:
            print(f"ошибка: {exc}", file=sys.stderr)
            return 1

        separator = SeparatorConfig(
            name=self._args.separator_name,
            url=self._args.separator_url,
        )
        output_path = self._resolve_output_path(output_format)

        try:
            stats = self._convert(data, output_format, output_path, separator)
        except ConversionError as exc:
            print(f"ошибка: {exc}", file=sys.stderr)
            return 1

        direction_label = DirectionDetector.label(input_format, output_format)
        print(f"[{direction_label}] Сконвертировано: {stats} -> {output_path}")
        return 0

    # -- Разбор аргументов --

    @staticmethod
    def _parse_args(argv: list[str] | None) -> argparse.Namespace:
        """Разбирает аргументы командной строки и возвращает Namespace."""
        parser = argparse.ArgumentParser(
            description=(
                "Конвертер закладок между форматами Firefox и Chromium. "
                "Направление определяется автоматически; можно переопределить через --to."
            ),
        )
        parser.add_argument(
            "input",
            type=Path,
            help="Путь ко входному JSON-файлу закладок.",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=None,
            help=(
                "Путь вывода. По умолчанию: <каталог_входа>/Bookmarks-Chromium.json "
                "(Firefox на входе) или <каталог_входа>/Bookmarks-Firefox.json "
                "(Chromium на входе)."
            ),
        )
        parser.add_argument(
            "--to",
            choices=("auto", "firefox", "chromium"),
            default="auto",
            help="Выходной формат (по умолчанию: автоопределение по входу).",
        )
        parser.add_argument(
            "--separator-name",
            default=DEFAULT_SEPARATOR_NAME,
            help=(
                f"Имя закладки, заменяющей разделитель Firefox в выводе "
                f'Chromium (по умолчанию: "{DEFAULT_SEPARATOR_NAME}").'
            ),
        )
        parser.add_argument(
            "--separator-url",
            default=DEFAULT_SEPARATOR_URL,
            help=(
                f"URL, заменяющий разделитель Firefox в выводе Chromium "
                f'(по умолчанию: "{DEFAULT_SEPARATOR_URL}").'
            ),
        )
        return parser.parse_args(argv)

    # -- Вспомогательные методы ввода-вывода --

    @staticmethod
    def _load_input(path: Path) -> JsonDict:
        """Читает и парсит входной JSON-файл.

        Raises:
            ConversionError: если файл не является корректным JSON.
        """
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ConversionError(f"некорректный JSON в {path}: {exc}") from exc
        except OSError as exc:
            raise ConversionError(f"не удалось прочитать {path}: {exc}") from exc

    @staticmethod
    def _resolve_output_format(data: JsonDict, requested: str) -> str:
        """Определяет выходной формат по запрошенному значению или автоопределению.

        ``requested`` — значение ``--to``: ``'auto'`` или явное имя формата.
        Возвращаемое значение всегда является *выходным* форматом.

        Выбрасывает ``ConversionError``, если запрошенный выходной формат
        совпадает с определённым входным (конверсия в тот же формат).
        """
        input_format = DirectionDetector.detect(data)
        if requested == "auto":
            return DirectionDetector.target_for(input_format)
        if requested == input_format:
            raise ConversionError(
                f"входной файл уже в формате {input_format!r}; конверсия в тот же формат невозможна"
            )
        return requested

    def _resolve_output_path(self, output_format: str) -> Path:
        """Возвращает путь вывода: явный --output либо дефолт по формату."""
        if self._args.output is not None:
            return self._args.output
        suffix = "-Chromium" if output_format == "chromium" else "-Firefox"
        return self._args.input.parent / f"Bookmarks{suffix}.json"

    # -- Диспетчеризация конверсии --

    def _convert(
        self,
        data: JsonDict,
        output_format: str,
        output_path: Path,
        separator: SeparatorConfig,
    ) -> NodeStats:
        """Диспетчеризация конверсии по выходному формату."""
        if output_format == "chromium":
            return self._convert_firefox_to_chromium(data, output_path, separator)
        if output_format == "firefox":
            return self._convert_chromium_to_firefox(data, output_path, separator)
        raise ConversionError(f"неизвестный выходной формат: {output_format!r}")

    @staticmethod
    def _convert_firefox_to_chromium(
        data: JsonDict,
        output_path: Path,
        separator: SeparatorConfig,
    ) -> NodeStats:
        """Конвертирует Firefox -> Chromium, пишет файл, возвращает статистику входа."""
        converter = FirefoxToChromiumConverter(separator)
        result = converter.convert(data)
        BookmarkConverterApp._write_output(output_path, result)
        return FirefoxNodeCounter().count(data)

    @staticmethod
    def _convert_chromium_to_firefox(
        data: JsonDict,
        output_path: Path,
        separator: SeparatorConfig,
    ) -> NodeStats:
        """Конвертирует Chromium -> Firefox, пишет файл, возвращает статистику входа."""
        converter = ChromiumToFirefoxConverter(separator)
        result = converter.convert(data)
        BookmarkConverterApp._write_output(output_path, result)
        return ChromiumNodeCounter().count(data)

    @staticmethod
    def _write_output(path: Path, data: JsonDict) -> None:
        """Записывает документ закладок в файл (UTF-8, отступ 3 пробела)."""
        # Отступ в 3 пробела повторяет стиль собственного писателя Chromium и
        # даёт человекочитаемый, удобный для diff вывод для обоих целевых форматов.
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=3, ensure_ascii=False)
            f.write("\n")


# ===========================================================================
# Точка входа
# ===========================================================================


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI: выполняет конверсию, возвращает код завершения."""
    return BookmarkConverterApp(argv).run()


if __name__ == "__main__":
    sys.exit(main())
