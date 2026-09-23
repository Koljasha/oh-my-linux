#!/usr/bin/env python
"""Случайно двигать курсор мыши против определения простоя/AFK.

Каждые ``interval`` секунд двигает курсор в случайную точку внутри
прямоугольной области до прерывания по Ctrl+C.

Требуется:
    pip install pyautogui
"""

import argparse
import random
import time


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разобрать аргументы командной строки.

    Args:
        argv: Необязательный список аргументов для тестов. По умолчанию ``None``
            (используется ``sys.argv``).

    Returns:
        Разобранный ``argparse.Namespace`` с атрибутами ``interval``, ``min_xy``
        и ``max_xy``.

    При неверных аргументах завершается с кодом 2 и печатает usage.
    """
    parser = argparse.ArgumentParser(
        description="Периодически двигать мышь в случайные координаты.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Секунд между движениями (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--min-xy",
        nargs=2,
        type=int,
        default=[100, 100],
        metavar=("MIN_X", "MIN_Y"),
        help="Левый верхний угол области (по умолчанию: %(default)s).",
    )
    parser.add_argument(
        "--max-xy",
        nargs=2,
        type=int,
        default=[1000, 1000],
        metavar=("MAX_X", "MAX_Y"),
        help="Правый нижний угол области (по умолчанию: %(default)s).",
    )
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval должен быть положительным.")
    min_x, min_y = args.min_xy
    max_x, max_y = args.max_xy
    if min_x > max_x or min_y > max_y:
        parser.error("--min-xy не должен превышать --max-xy.")
    return args


def main(argv: list[str] | None = None) -> None:
    """Запустить цикл движения мыши до прерывания.

    Args:
        argv: Необязательный список аргументов, передаваемый в :func:`parse_args`.

    При неверных аргументах завершается с кодом 2 (через ``argparse``).
    """
    args = parse_args(argv)
    min_x, min_y = args.min_xy
    max_x, max_y = args.max_xy

    # Импорт здесь, чтобы импорт модуля, --help и проверка аргументов работали без дисплея (headless).
    import pyautogui

    pyautogui.FAILSAFE = True
    print(
        f"Двигаю мышь каждые {args.interval} с в x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]. Ctrl+C для остановки."
    )
    try:
        while True:
            pyautogui.moveTo(random.randint(min_x, max_x), random.randint(min_y, max_y))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
