#!/usr/bin/env python
"""Разбор игр со скидками со страниц поиска магазина Steam.

Запрашивает страницы ``store.steampowered.com/search``, извлекает названия
со скидками и сохраняет их в ``steam.csv`` (разделитель ``|``).

Требуется:
    pip install requests beautifulsoup4 lxml
"""

import argparse
import csv
import os
import webbrowser
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://store.steampowered.com/search/"
CSV_PATH = "steam.csv"
CSV_FIELDNAMES = ["title", "link", "discount", "full_price", "discount_price"]
REQUEST_TIMEOUT = 30
HEADERS = {"User-Agent": "scripts-steam-discount/1.0 (+https://github.com/)"}


def get_html(url: str, params: dict[str, Any]) -> str:
    """Запросить страницу и вернуть её HTML-текст.

    Args:
        url: URL страницы.
        params: Параметры запроса.

    Returns:
        Тело ответа текстом.

    Raises:
        requests.RequestException: При сетевых или HTTP-ошибках с кодом не 2xx.
    """
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    return response.text


def paginator(url: str, params: dict[str, Any]) -> int:
    """Вернуть общее число страниц результатов поиска.

    Args:
        url: URL поиска.
        params: Параметры запроса.

    Returns:
        Число страниц (минимум 1).

    Raises:
        requests.RequestException: При сетевых или HTTP-ошибках.
        ValueError: Если число страниц не удаётся разобрать.
    """
    data = get_html(url, params)
    bs = BeautifulSoup(data, "lxml")
    pags = bs.select(".search_pagination_right > a")
    if len(pags) < 2:
        return 1
    return int(pags[-2].text.strip())


def discount(url: str, params: dict[str, Any]) -> list[dict[str, str]]:
    """Извлечь игры со скидкой с одной страницы результатов поиска.

    Args:
        url: URL поиска.
        params: Параметры запроса.

    Returns:
        Список словарей с ключами из :data:`CSV_FIELDNAMES`.
        Записи без бейджа скидки пропускаются.

    Raises:
        requests.RequestException: При сетевых или HTTP-ошибках.
    """
    data = get_html(url, params)
    bs = BeautifulSoup(data, "lxml")
    games = bs.select(".responsive_search_name_combined")

    sale: list[dict[str, str]] = []
    for game in games:
        title_el = game.select(".title")
        if not title_el:
            continue
        title = title_el[0].text.strip()
        parent = game.parent
        href = parent.get("href") if parent is not None else None
        if not href or not isinstance(href, str):
            continue
        link = href.split("?")[0]
        discount_el = game.select(".search_discount > span")
        if not discount_el:
            continue
        discount_text = discount_el[0].text.strip()
        price_el = game.select(".search_price")
        if not price_el:
            continue
        price = price_el[0].text.strip().split(".")
        if len(price) < 2:
            continue
        sale.append(
            {
                "title": title,
                "link": link,
                "discount": discount_text,
                "full_price": price[0],
                "discount_price": price[1],
            }
        )
    return sale


def steam() -> None:
    """Разобрать все страницы поиска и дописать результаты в CSV-файл."""
    # specials = 1 скрыл бы скидки 100%; вместо этого разбираем весь магазин.
    params: dict[str, Any] = {
        # 'specials': 1,
        "ignore_preferences": 1,
        "count": 100,
    }

    try:
        params["page"] = 1
        pag = paginator(BASE_URL, params)
    except (requests.RequestException, ValueError) as e:
        print(f"Exception: {e}")
        return

    print("Paginator:", pag)

    for page in range(1, pag + 1):
        params["page"] = page
        try:
            discounts = discount(BASE_URL, params)
        except requests.RequestException as e:
            print(f"Exception: {e}")
            return
        write_csv(discounts)
        print(f"Page: {page} / {pag}")


def write_csv(data: list[dict[str, str]], path: str = CSV_PATH) -> None:
    """Дописать строки игр в CSV-файл.

    Args:
        data: Строки с ключами из :data:`CSV_FIELDNAMES`.
        path: Путь к CSV-файлу назначения.
    """
    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES, delimiter="|")
        for line in data:
            writer.writerow(line)


def init_csv(path: str = CSV_PATH) -> None:
    """Создать новый CSV-файл со строкой заголовка.

    Args:
        path: Путь к CSV-файлу назначения. Если файл существует, сначала удаляется.
    """
    if os.path.exists(path):
        os.remove(path)
    with open(path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES, delimiter="|")
        writer.writeheader()


def read_csv(show_in_browser: bool = False, path: str = CSV_PATH) -> None:
    """Напечатать (или открыть) игры со скидкой 100% (-100%) из CSV-файла.

    Args:
        show_in_browser: Открывать совпавшие ссылки в браузере вместо печати.
        path: Путь к исходному CSV-файлу.
    """
    try:
        with open(path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter="|")
            for row in reader:
                if row.get("discount") == "-100%":
                    if show_in_browser:
                        webbrowser.open_new_tab(row.get("link", ""))
                    else:
                        print(row.get("title"), "\t|\t", row.get("link"))
    except (OSError, csv.Error) as e:
        print(f"Exception: {e}")
        return


def main() -> None:
    """Разобрать аргументы CLI и выполнить действия разбора/показа."""
    parser = argparse.ArgumentParser(
        description="Искать скидки в магазине Steam",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-p", "--parse", action="store_true", help="Разобрать магазин Steam и записать steam.csv"
    )
    parser.add_argument(
        "-s",
        "--show",
        default=0,
        type=int,
        choices=range(3),
        help="0 - ничего не показывать;\n1 - показать игры со скидкой 100%% из steam.csv в скрипте;\n2 - показать игры со скидкой 100%% из steam.csv в браузере",
    )
    args = parser.parse_args()

    if args.parse is False and args.show == 0:
        parser.print_help()
        return

    if args.parse is True:
        init_csv()

        steam()

        print("---------------")
        if args.show == 2:
            read_csv(True)
        elif args.show == 1:
            read_csv(False)
        print("---------------")

    else:
        if args.show == 2:
            read_csv(True)
        elif args.show == 1:
            read_csv(False)


if __name__ == "__main__":
    main()
