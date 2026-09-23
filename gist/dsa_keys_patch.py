#!/usr/bin/env python3
"""Патч для подключения по старым DSA-ключам (paramiko + cryptography).

Старые 1024-битные DSA-ключи paramiko отклоняет: внутренняя проверка
параметров в ``cryptography`` пропускает только строго определённые
размеры. Патч ослабляет проверку — применять до первого подключения.

Актуально для старых версий ``cryptography`` (где существует
``dsa._check_dsa_parameters``). В новых версиях этой функции нет —
тогда патч не нужен, скрипт предупредит и ничего не сделает.
"""

import warnings

from cryptography.hazmat.primitives.asymmetric import dsa


def _override_check_dsa_parameters(parameters):
    """Ослабленная проверка параметров DSA (пропускает старые ключи)."""
    if parameters.q.bit_length() not in [160, 256]:
        raise ValueError("q must be exactly 160 or 256 bits long")
    if not (1 < parameters.g < parameters.p):
        raise ValueError("g, p don't satisfy 1 < g < p.")


if hasattr(dsa, "_check_dsa_parameters"):
    dsa._check_dsa_parameters = _override_check_dsa_parameters
else:
    warnings.warn(
        "dsa._check_dsa_parameters отсутствует в этой версии cryptography — "
        "патч не применён (возможно, он уже не нужен)."
    )
