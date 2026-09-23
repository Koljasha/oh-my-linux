#!/usr/bin/env python3
"""Запуск блокирующей функции из async-кода без простоя event loop.

Оборачивает обычную (синхронную) функцию так, чтобы её можно было
``await``-ить: вызов уезжает в отдельный поток через executor.
Удобно для ``time.sleep``, запросов через ``requests`` и других
долгих вызовов, у которых нет async-версии.
"""

import asyncio
from functools import partial, wraps


def async_wrap(func):
    """Обернуть блокирующую функцию для вызова через ``await``."""

    @wraps(func)
    async def run(*args, executor=None, **kwargs):
        loop = asyncio.get_running_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


if __name__ == "__main__":
    import time

    async_sleep = async_wrap(time.sleep)

    async def f(delay, text):
        print(f"Start {text}")
        await async_sleep(delay)
        print(f"Stop {text}")

    async def main():
        await asyncio.gather(f(0.3, "first"), f(0.4, "second"), f(0.1, "third"))

    asyncio.run(main())
