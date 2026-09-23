#!/usr/bin/env python3
"""Шаблон декоратора с сохранением имени и докстринга функции."""

import functools


def decorator(func):
    """Шаблон: выполнить свой код до и после вызова функции."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Действие до вызова
        value = func(*args, **kwargs)
        # Действие после вызова
        return value

    return wrapper


if __name__ == "__main__":

    @decorator
    def add(a, b):
        """Складывает два числа."""
        return a + b

    print(add(2, 3))  # 5
