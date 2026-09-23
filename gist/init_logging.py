#!/usr/bin/env python3
"""Быстрая настройка logging: вывод в консоль, в файл или в оба места."""

import logging
from pathlib import Path

# Папка для лог-файлов — рядом с этим скриптом.
BASE_DIR = Path(__file__).resolve().parent


def init_logging(mode="stream"):
    """Настроить корневой логгер.

    :param mode: ``'stream'`` — только консоль,
        ``'file'`` — только файл ``logs/<имя модуля>.log``,
        ``'both'`` — консоль и файл одновременно.
    """
    handlers = [logging.StreamHandler()]

    if mode in ("file", "both"):
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        handlers.append(logging.FileHandler(logs_dir / f"{__name__}.log", encoding="utf-8"))

    if mode == "file":
        handlers = handlers[1:]

    logging.basicConfig(
        format="%(levelname)s|%(asctime)s|%(message)s",
        level=logging.DEBUG,
        handlers=handlers,
    )


if __name__ == "__main__":
    init_logging()
    logging.getLogger(__name__).debug("...logging...")
