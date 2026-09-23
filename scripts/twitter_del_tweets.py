#!/usr/bin/env python
"""Удаление твитов аккаунта (скрипт под legacy Twitter API v1.1).

Использует ``GET statuses/user_timeline`` и ``POST statuses/destroy`` из
legacy Twitter API v1.1, который на текущих аккаунтах может быть недоступен.
Сохранён для справки; без доступа к v1.1 завершится ошибкой.

Учётные данные загружаются из модуля ``config`` (по умолчанию ``config.py``
рядом со скриптом). Создайте рядом со скриптом файл config.py по шаблону::

    consumer_key_TW = ""
    consumer_secret_TW = ""
    access_token_TW = ""
    access_token_secret_TW = ""

Этот файл НЕ коммитить. Вместо файла можно задать переменные окружения
``TW_CONSUMER_KEY`` / ``TW_CONSUMER_SECRET`` /
``TW_ACCESS_TOKEN`` / ``TW_ACCESS_TOKEN_SECRET``. Удаление по умолчанию
ВЫКЛЮЧЕНО: без флага ``--no-dry-run`` скрипт только показывает, что
*было бы* удалено.

Требуется:
    pip install requests requests_oauthlib
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from requests_oauthlib import OAuth1

TIMELINE_URL = "https://api.twitter.com/1.1/statuses/user_timeline.json"
DESTROY_URL_TEMPLATE = "https://api.twitter.com/1.1/statuses/destroy/{tweet_id}.json"
REQUEST_TIMEOUT = 30


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разобрать аргументы командной строки.

    Args:
        argv: Необязательный список аргументов для тестов. По умолчанию ``None``.

    Returns:
        Разобранный ``argparse.Namespace``.
    """
    parser = argparse.ArgumentParser(
        description="Показать (и при желании удалить) твиты через legacy Twitter API v1.1."
    )
    parser.add_argument(
        "--screen-name",
        default="Koljasha",
        help="Аккаунт, чьи твиты показать (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--config",
        default="config",
        help="Имя модуля config или путь к файлу с ключами Twitter (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Сколько твитов запросить за раз, 1-200 (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--keep",
        nargs="*",
        default=["1353734459456172036"],
        metavar="TWEET_ID",
        help="ID твитов, которые никогда не удалять (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Действительно удалить твиты. Без этого флага только показывает кандидатов.",
    )
    return parser.parse_args(argv)


def load_credentials(config_ref: str) -> dict[str, str]:
    """Загрузить OAuth-учётные данные Twitter из модуля config или пути к файлу.

    При отсутствии значения в модуле подставляется значение из
    переменных окружения ``TW_*``.

    Args:
        config_ref: Имя модуля (например, ``config``) или путь к ``.py``-файлу.

    Returns:
        Словарь с ключами ``consumer_key``, ``consumer_secret``,
        ``access_token`` и ``access_token_secret``.

    Raises:
        SystemExit: С кодом 2 и подсказкой (шаблон см. в начале файла),
            если учётные данные не найдены.
    """
    names = ("consumer_key_TW", "consumer_secret_TW", "access_token_TW", "access_token_secret_TW")
    env_map = {
        "consumer_key_TW": "TW_CONSUMER_KEY",
        "consumer_secret_TW": "TW_CONSUMER_SECRET",
        "access_token_TW": "TW_ACCESS_TOKEN",
        "access_token_secret_TW": "TW_ACCESS_TOKEN_SECRET",
    }
    values: dict[str, str] = {}
    try:
        if config_ref.endswith(".py") or os.path.sep in config_ref:
            spec = importlib.util.spec_from_file_location("tweet_config", config_ref)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load config from {config_ref!r}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(config_ref)
        for name in names:
            values[name] = str(getattr(module, name, "") or os.environ.get(env_map[name], ""))
    except ImportError:
        for name in names:
            values[name] = os.environ.get(env_map[name], "")
        if not all(values.values()):
            print(
                f"Ошибка: модуль конфигурации {config_ref!r} не найден, а переменные окружения неполные.\n"
                "Создайте рядом со скриптом локальный (вне git) config.py по шаблону в начале файла:\n"
                "  consumer_key_TW, consumer_secret_TW,\n"
                "  access_token_TW, access_token_secret_TW\n"
                "или задайте TW_CONSUMER_KEY / TW_CONSUMER_SECRET /\n"
                "TW_ACCESS_TOKEN / TW_ACCESS_TOKEN_SECRET.",
                file=sys.stderr,
            )
            raise SystemExit(2)
    missing = [n for n, v in values.items() if not v]
    if missing:
        print(
            f"Ошибка: отсутствуют учётные данные ({', '.join(missing)}). "
            "Заполните их в локальном config.py (шаблон см. в начале файла) "
            "или через переменные окружения TW_*. Не коммитьте настоящие секреты.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return {
        "consumer_key": values["consumer_key_TW"],
        "consumer_secret": values["consumer_secret_TW"],
        "access_token": values["access_token_TW"],
        "access_token_secret": values["access_token_secret_TW"],
    }


def fetch_tweets(auth: OAuth1, screen_name: str, count: int) -> list[dict[str, Any]]:
    """Получить недавние твиты из ленты пользователя.

    Args:
        auth: Обёртка OAuth1 с учётными данными.
        screen_name: Аккаунт для запроса.
        count: Сколько твитов получить (1-200).

    Returns:
        Список объектов твитов.

    Raises:
        requests.RequestException: При сетевых или HTTP-ошибках.
        ValueError: Если API вернуло тело с ошибкой.
        TypeError: Если API вернуло тело неожиданного типа.
    """
    params = {"screen_name": screen_name, "count": count}
    response = requests.get(TIMELINE_URL, params=params, auth=auth, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and "errors" in payload:
        raise ValueError(f"Twitter API error: {payload['errors']}")
    if not isinstance(payload, list):
        raise TypeError(f"Unexpected API response: {payload!r}")
    return payload


def destroy_tweet(auth: OAuth1, tweet_id: str) -> dict[str, Any]:
    """Удалить один твит по ID.

    Args:
        auth: Обёртка OAuth1 с учётными данными.
        tweet_id: ID твита для удаления.

    Returns:
        Разобранный ответ API.

    Raises:
        requests.RequestException: При сетевых или HTTP-ошибках.
    """
    url = DESTROY_URL_TEMPLATE.format(tweet_id=tweet_id)
    response = requests.post(url, auth=auth, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def main(argv=None) -> None:
    """Показать кандидатов на удаление и удалить их, если не dry-run.

    Args:
        argv: Необязательный список аргументов, передаваемый в :func:`parse_args`.
    """
    args = parse_args(argv)
    creds = load_credentials(args.config)
    try:
        # Импорт здесь, чтобы --help и ошибки конфигурации работали без установленной зависимости.
        from requests_oauthlib import OAuth1
    except ImportError:
        print(
            "Ошибка: пакет 'requests_oauthlib' не установлен. Выполните: pip install requests requests_oauthlib",
            file=sys.stderr,
        )
        raise SystemExit(2)
    auth = OAuth1(
        creds["consumer_key"],
        creds["consumer_secret"],
        creds["access_token"],
        creds["access_token_secret"],
    )

    try:
        tweets = fetch_tweets(auth, args.screen_name, args.count)
    except (requests.RequestException, ValueError, TypeError) as e:
        print(f"Ошибка получения твитов: {e}", file=sys.stderr)
        raise SystemExit(1)

    keep = set(args.keep or [])
    for_del: list[str] = []
    for count, tweet in enumerate(tweets):
        try:
            tweet_id = tweet["id_str"]
            text = tweet.get("text", "")
        except (KeyError, TypeError) as e:
            print(f"Предупреждение: пропуск повреждённого твита #{count}: {e}", file=sys.stderr)
            continue
        print(count, " : ", tweet_id)
        print(text)
        print("=====")
        for_del.append(tweet_id)

    print("=========================")

    for tweet_id in for_del:
        if tweet_id not in keep:
            if args.dry_run:
                print(f"Будет удалён: {tweet_id} (dry-run, для удаления передайте --no-dry-run)")
                continue
            print(f"Удаляю: {tweet_id}")
            try:
                destroy_tweet(auth, tweet_id)
            except requests.RequestException as e:
                print(f"Ошибка удаления {tweet_id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
