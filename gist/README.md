# Gist

Короткие сниппеты и шаблоны: копируй к себе и правь под задачу. В отличие от
[scripts](../scripts/README.md) это не готовые утилиты, а заготовки на 5–30 строк.

| Файл | Что внутри |
|---|---|
| [`color_echo.sh`](color_echo.sh) | Цветной вывод в bash через ANSI-коды + таблица цветов |
| [`download_blob.sh`](download_blob.sh) | Скачивание HLS-потока (.m3u8) через ffmpeg без перекодирования |
| [`pip_upgrade_packages.sh`](pip_upgrade_packages.sh) | Обновление всех устаревших pip-пакетов, по одному за вызов |
| [`async_wrap.py`](async_wrap.py) | `await` для блокирующих функций через executor |
| [`decorator.py`](decorator.py) | Шаблон декоратора с `functools.wraps` |
| [`init_logging.py`](init_logging.py) | Настройка logging: консоль / файл / оба сразу |
| [`dsa_keys_patch.py`](dsa_keys_patch.py) | Патч для старых DSA-ключей (paramiko + старые cryptography) |

С date-арифметикой в bash и расшифровкой паролей DBeaver — наоборот:
они уже живут в основных разделах, сюда не дублировались:

- date `+N days` / `-N min` — в [handbook, раздел 17](../handbook/README.md#17-система-и-мелочи);
- `credentials-config.json` — в [encryption, раздел 6](../encryption/README.md#6-dbeaver-расшифровка-credentials-configjson).

## Проверки

```bash
ruff check gist/*.py
ty check gist/*.py
shellcheck -x gist/*.sh
shfmt -d -i 4 gist/*.sh
```

## Лицензия

MIT, см. [../LICENSE](../LICENSE).
