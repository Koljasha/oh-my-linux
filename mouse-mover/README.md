# Шевелитель мышки (Mouse Mover)

## 1. Установка системных зависимостей

### Debian / Ubuntu / Linux Mint

```bash
sudo apt-get update
sudo apt-get install python3 python3-venv python3-tk
```

### Arch Linux / Manjaro

```bash
sudo pacman -S python tk
```

### Fedora / RHEL / CentOS

```bash
sudo dnf install python3 python3-tkinter
```

### openSUSE

```bash
sudo zypper install python3 python3-tk
```

---

## 2. Создание виртуального окружения

```bash
mkdir -p ~/.local/share/mouse-mover
cd ~/.local/share/mouse-mover

python3 -m venv .venv
source .venv/bin/activate

pip install pyautogui
```

---

## 3. Установка скрипта

Положи `mouse-mover.py` в `~/.local/share/mouse-mover/`.

Проверь, что работает:

```bash
~/.local/share/mouse-mover/.venv/bin/python ~/.local/share/mouse-mover/mouse-mover.py
```

---

## 4. Установка как systemd-сервис

### 4.1 Скопировать сервис-файл

```bash
mkdir -p ~/.config/systemd/user
cp mouse-mover.service ~/.config/systemd/user/
```

### 4.2 Перезагрузить systemd

```bash
systemctl --user daemon-reload
```

### 4.3 Включить автозапуск (опционально)

```bash
systemctl --user enable mouse-mover.service
```

### 4.4 Управление сервисом

```bash
# Запуск
systemctl --user start mouse-mover.service

# Остановка
systemctl --user stop mouse-mover.service

# Статус
systemctl --user status mouse-mover.service

# Логи
journalctl --user -u mouse-mover.service -f
```

---

## 5. Интерактивный скрипт управления

```bash
./mouse-mover-ctl.sh
```

