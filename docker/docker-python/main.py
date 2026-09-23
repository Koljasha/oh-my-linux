#!/usr/bin/env python3

import os
from datetime import datetime

# Получаем информацию о скрипте
script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
script_name = os.path.basename(__file__)

# Создаем директорию для логов, если она не существует
logs_dir = os.path.join(script_dir, 'logs')
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, f"{script_name}.log")

# Получаем текущую дату и время
current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Формируем сообщение
message = f"{script_name} | {current_date}"

# Выводим сообщение в файл и консоль
print(message)
with open(log_file, 'a') as f:
    f.write(message + '\n')

