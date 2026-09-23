# Сборка Python из исходников

Как собрать собственный Python из исходного кода, не трогая системный
(`/usr/bin/python` — не трогать).

## Шаги

1. Скачать исходники со страницы загрузок:
   `https://www.python.org/downloads/` (пример: 3.12+).
2. Установить зависимости для сборки (см. руководство разработчика
   Python, раздел про установку зависимостей:
   `https://devguide.python.org/getting-started/setup-building/#install-dependencies`).
3. Сконфигурировать с оптимизациями и отдельным префиксом, чтобы
   не пересекаться с системным Python:

```bash
./configure --enable-optimizations --prefix="$HOME/bin/python-3.12"
```

4. Собрать и установить:

```bash
make
make install
```

После этого собранный интерпретатор живёт в `$HOME/bin/python-3.12`
и системному Python не мешает.
