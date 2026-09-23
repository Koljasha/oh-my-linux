# Заметки по установке и настройке Linux

Актуальные персональные настройки хранятся в отдельном репозитории — [Koljasha/archlinux](https://github.com/Koljasha/archlinux).

## Оглавление

- [1. Рабочее окружение](#1-рабочее-окружение)
- [2. Miniconda и Node.js](#2-miniconda-и-nodejs)
- [3. Git](#3-git)
- [4. systemd](#4-systemd)
- [5. Samba](#5-samba)
- [6. Автообновление (apt и conda)](#6-автообновление-apt-и-conda)
- [7. Монтирование дисков](#7-монтирование-дисков)
- [8. chroot в другой Linux](#8-chroot-в-другой-linux)
- [9. Драйверы сети](#9-драйверы-сети)
- [10. Пользователи](#10-пользователи)
- [11. Rsync, fd, rg](#11-rsync-fd-rg)
- [12. Оболочки: fish, zsh, bash, fzf](#12-оболочки-fish-zsh-bash-fzf)
- [13. Горячие клавиши bash](#13-горячие-клавиши-bash)
- [14. Wine](#14-wine)
- [15. GRUB](#15-grub)
- [16. Скрипты Nemo (WireGuard)](#16-скрипты-nemo-wireguard)
- [17. Система и мелочи](#17-система-и-мелочи)
- [18. Сборка Python из исходников](#18-сборка-python-из-исходников)

---

## 1. Рабочее окружение

- Кнопки окна: Закрыть, Свернуть, Развернуть | Свернуть в заголовок, Меню.
- Формат времени: `%A %Y-%m-%d %H:%M:%S`.
- Plank для Xfce:
  - добавить в «Сеансы и запуск» → «Автозапуск»;
  - снять «Диспетчер окон (дополнительно)» → «Эффекты» → «Тени под сворачивающимися окнами».
- Иконки Mint-x:

```bash
git clone https://github.com/linuxmint/mint-x-icons.git
```

## 2. Miniconda и Node.js

Miniconda:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
&& bash Miniconda3-latest-Linux-x86_64.sh
```

Node.js:

- [Node Version Manager](https://github.com/nvm-sh/nvm)
- [Node Version Manager for Windows](https://github.com/coreybutler/nvm-windows)

## 3. Git

```bash
git config --global user.name "username" \
&& git config --global user.email "username@example.com" \
&& git config --global core.editor vim \
&& git config --global merge.tool vimdiff \
&& git config --global push.default simple \
&& git config --global credential.helper store
```

## 4. systemd

Обновить сервисы после правок юнитов:

```bash
sudo systemctl daemon-reload
```

## 5. Samba

`sudo vim /etc/samba/smb.conf`:

```ini
# Пример общей папки
[share]
  comment = share
  path = /home/username/share
  browseable = yes
  writable = yes
```

```bash
sudo systemctl restart smbd.service
```

Использование `smbclient`:

- показать доступные (без пароля): `smbclient -N -L \\\\<host|ip>\\`
- показать доступные (с паролем): `smbclient -U login%password -L \\\\<host|ip>\\`
- подключиться (без пароля): `smbclient -N \\\\<host|ip>\\<share>\\`
- подключиться (с паролем): `smbclient -U login%password \\\\<host|ip>\\<share>\\`
- выполнить (без пароля): `smbclient -N -c help \\\\<host|ip>\\<share>\\`
- выполнить (с паролем): `smbclient -U login%password -c help \\\\<host|ip>\\<share>\\`

## 6. Автообновление (apt и conda)

`sudo vim /etc/sudoers.d/apt`:

```text
# apt для пользователя без пароля
username ALL = (ALL) NOPASSWD: /usr/bin/apt
```

`crontab -e`:

```cron
0 */4 * * * sudo apt update && sudo apt dist-upgrade --yes && sudo apt autoremove --yes
10 */4 * * * /home/username/soft/conda/bin/conda update --all --yes
```

## 7. Монтирование дисков

Показать диски:

```bash
sudo blkid
lsblk -o "NAME,SIZE,LABEL,MOUNTPOINT,UUID"
```

Пример записей в `/etc/fstab`:

```text
# <file system>             <mount point>  <type>  <options>        <dump>  <pass>
UUID=7488d026-ea24-4c24-9618-3d54d0dee8db /              ext4    defaults,noatime 0 1
UUID=81174079-1ed8-4986-9269-b614e120856a none           swap    defaults          0 0
UUID="01D09BCBA9456C70"               /mnt/storage   ntfs    rw,relatime       0 0
```

Пример для Linux-разделов:

```text
# <file system> <dir> <type> <options> <dump> <pass>

# /dev/nvme0n1p1 LABEL=Arch
UUID=f3a3fdc6-ab9c-4633-9bfd-030766b079c1 / ext4 rw,relatime 0 1

# swapfile
/swapfile none swap defaults 0 0

# /dev/sda4 LABEL=Storage
UUID=c6ab23b5-1b6d-4c3f-8488-6efee0144e54 /mnt/storage/ ext4 rw,relatime 0 2
```

## 8. chroot в другой Linux

Нужен пакет [arch-install-scripts](https://www.thegeekdiary.com/arch-chroot-command-not-found/):

```bash
sudo mount /dev/sdaX /mnt
sudo arch-chroot /mnt
su - username
# выполнить действия
exit
exit
sudo umount /mnt
```

## 9. Драйверы сети

Если нет Wi-Fi-адаптера (чип Realtek 8821CE):

- репозиторий `tomaspinho/rtl8821ce` — архивный, использовать только как ориентир;
- актуальный вариант — пакет `rtl8821ce-dkms-git` из AUR: [rtl8821ce-dkms-git](https://aur.archlinux.org/packages/rtl8821ce-dkms-git).

Если нет Ethernet (чип Realtek 8168):

- [Archlinux](https://archlinux.org/packages/?q=r8168)
- [Manjaro](https://packages.manjaro.org/?query=8168)

## 10. Пользователи

`sudo vim /var/lib/AccountsService/users/USERNAME`:

- скрыть: `SystemAccount=true`
- показать: `SystemAccount=false`

## 11. Rsync, fd, rg

```bash
rsync -avP file server:folder/
rsync -avP --delete src/ dest/    # удалить лишние файлы в dest
fd -HI <search>                   # то же, что fd --hidden --no-ignore <search>
rg --hidden --no-ignore --ignore-case <search>
```

## 12. Оболочки: fish, zsh, bash, fzf

Комбинации fish (посмотреть все: `bind --all`):

- `alt + <-` — перемещение по истории папок (prevd)
- `alt + ->` — перемещение по истории папок (nextd)
- `alt + l` — команда ls
- `alt + p` — добавить `| less`
- `alt + w` — информация о команде (type)
- `alt + e` — запустить $EDITOR
- `alt + s` — добавить sudo

Fish:

```bash
sudo chsh -s /usr/bin/fish username
```

- [Install Fish](https://fishshell.com/docs/current/index.html#installation)
- [Install Oh My Fish](https://github.com/oh-my-fish/oh-my-fish/wiki#install)

Zsh:

```bash
sudo chsh -s /usr/bin/zsh username
```

- [Install Zsh](https://github.com/ohmyzsh/ohmyzsh/wiki/Installing-ZSH#how-to-install-zsh-on-many-platforms)
- [Install Oh My Zsh](https://github.com/ohmyzsh/ohmyzsh/wiki#welcome-to-oh-my-zsh)
- [Install zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions/blob/master/INSTALL.md#oh-my-zsh)
- [Install zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/INSTALL.md#with-a-plugin-manager)

`vim ~/.zshrc`:

```zsh
# Path to fzf (install with vim)
export PATH=$HOME/.vim/plugged/fzf/bin:$PATH
.........
ZSH_THEME="agnoster"
.........
zstyle ':omz:update' mode auto
.........
plugins=(git vi-mode
    dirhistory
    zsh-autosuggestions
    zsh-syntax-highlighting
    )
.........
source $ZSH/oh-my-zsh.sh

# Enable fzf (install with vim)
source $HOME/.vim/plugged/fzf/shell/key-bindings.zsh
source $HOME/.vim/plugged/fzf/shell/completion.zsh

# Disable right arrow key triggers autosuggestion completion after paste
# https://github.com/zsh-users/zsh-autosuggestions/issues/489
ZSH_AUTOSUGGEST_CLEAR_WIDGETS+=(bracketed-paste)

# Bindkeys
bindkey '\e.' insert-last-word

# User configuration
.........
```

Bash:

```bash
sudo chsh -s /bin/bash username
```

- [Install Oh My Bash](https://github.com/ohmybash/oh-my-bash#basic-installation)

`vim ~/.bashrc`:

```bash
# Path to fzf (install with vim)
export PATH=$HOME/.vim/plugged/fzf/bin:$PATH
.........
OSH_THEME="powerline"
.........
source "$OSH"/oh-my-bash.sh

# Enable fzf (install with vim)
source $HOME/.vim/plugged/fzf/shell/key-bindings.bash
source $HOME/.vim/plugged/fzf/shell/completion.bash
.........
```

FZF ([привязки клавиш](https://github.com/junegunn/fzf#key-bindings-for-command-line)):

- CTRL-T — вставить выбранные файлы и каталоги в командную строку
- CTRL-R — вставить выбранную команду из истории в командную строку
- ALT-C — перейти в выбранный каталог

## 13. Горячие клавиши bash

[Полезная шпаргалка](https://gist.github.com/1eedaegon/6372b024c3793fa4887190d01f6c21f9):

Перемещение и удаление:

- `Ctrl + b` — назад
- `Ctrl + f` — вперёд
- `Ctrl + h` — удалить символ перед курсором
- `Ctrl + d` — удалить символ под курсором
- `Ctrl + a` — в начало строки
- `Ctrl + e` — в конец строки
- `Meta (Alt) + b` — в начало слова
- `Meta (Alt) + f` — в конец слова
- `Ctrl + p` — предыдущая команда
- `Ctrl + n` — следующая команда

Вырезание и вставка (kill ring):

- `Ctrl + w` — вырезать слово перед курсором
- `Meta (Alt) + d` — вырезать слово под курсором
- `Ctrl + u` — вырезать от начала строки до курсора
- `Ctrl + k` — вырезать от курсора до конца строки
- `Ctrl + y` — вставить (yank)
- `Meta (Alt) + y` — перебрать буфер

## 14. Wine

Использование `WINEPREFIX`:

```bash
WINEPREFIX=~/tmp/prefix/ WINEARCH=win64 winecfg
WINEPREFIX=~/tmp/prefix/ winetricks dxvk
WINEPREFIX=~/tmp/prefix/ wine <game>.exe
```

## 15. GRUB

Отключить os-prober:

```bash
sudo chmod -x /etc/grub.d/30_os-prober
```

## 16. Скрипты Nemo (WireGuard)

Апплет Cinnamon «Меню скриптов», скрипт в `~/.local/share/nemo/scripts`:

```bash
#!/usr/bin/env bash

status=`sudo wg`

if [[ $status == "" ]]; then
    sudo wg-quick up wg0
    echo; echo "Wireguard Up"
    sleep 1
else
    sudo wg-quick down wg0
    echo; echo "Wireguard Down"
    sleep 1
fi
```

## 17. Система и мелочи

Запретить/разрешить `sudo systemctl reboot`:

```bash
sudo systemctl mask reboot.target    # запретить
sudo systemctl unmask reboot.target  # разрешить
```

Копирование в clipboard:

```bash
echo 'qwerty_xclip' | xclip -selection clipboard
echo 'qwerty_xsel' | xsel --clipboard
```

Информация о команде:

- `which` или `whereis` — расположение
- `type` — описание alias
- `command` — игнорирование alias

Снятие подсветки в `less`: `alt+u`.

Временная подмена системного времени:

```bash
sudo timedatectl set-ntp false                                             # отключаем автоматическое обновление
sudo date --set="$(date -d '-1 day' '+%Y-%m-%d') $(date '+%H:%M:%S')"       # ставим дату на -1 день
sudo timedatectl set-ntp true                                              # включаем обратно
```

Arch, работа с `*.pacnew`:

```bash
pacdiff -o
pacdiff
```

Запуск процесса в фоне:

```bash
nohup python server.py &
python server.py & disown
setsid python server.py
```

## 18. Сборка Python из исходников

Как собрать собственный Python из исходного кода, не трогая системный
(`/usr/bin/python` — не трогать).

### Шаги

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
