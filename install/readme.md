## Заметки о Linux
### ->->-> look [Arch Linux Installer](https://github.com/Koljasha/archlinux_installer) for current settings <-<-<-
***

1. Настройки:
    * кнопки: Закрыть, Свернуть, Развернуть    |    Свернуть в заголовок, Меню
    * Настройка времени: `%A %Y-%m-%d %H:%M:%S`
    * Plank дополнительно для Xfce
      * добавить "Сеансы и запуск" -> "Автозапуск"
      * снять "Диспетчер окон (дополнительно)" -> "Эффекты" -> "Тени под сворачивающимися окнами"
    * иконки Mint-x: `git clone https://github.com/linuxmint/mint-x-icons.git`

2. Miniconda
```
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
&& bash Miniconda3-latest-Linux-x86_64.sh
```

3. Node.js - Node Version Manager (nvm): 
  * [Node Version Manager](https://github.com/nvm-sh/nvm)
  * [Node Version Manager for Windows](https://github.com/coreybutler/nvm-windows)

4. Git:
```
git config --global user.name "Koljasha" \
&& git config --global user.email "koljasha@mail.ru" \
&& git config --global core.editor vim \
&& git config --global merge.tool vimdiff \
&& git config --global push.default simple \
&& git config --global credential.helper store
```

5. Обновить сервисы systemd
  * `sudo systemctl daemon-reload`

6. Samba share:
  * `sudo vim /etc/samba/smb.conf`
```
# Koljasha share
[Koljasha]
  comment = Koljasha share
  path = /home/koljasha/share
  browseable = yes
  writable = yes
```
  * `sudo systemctl restart smbd.service`
  * используем `smbclient`:
    * показать доступные (без пароля) `smbclient -N -L \\\\<host|ip>\\`
    * показать доступные (с паролем) `smbclient -U login%password -L \\\\<host|ip>\\`
    * подключиться (без пароля) `smbclient -N \\\\<host|ip>\\<share>\\`
    * подключиться (с паролем) `smbclient -U login%password \\\\<host|ip>\\<share>\\`
    * выполнить (без пароля) `smbclient -N -c help \\\\<host|ip>\\<share>\\`
    * выполнить (с паролем) `smbclient -U login%password -c help \\\\<host|ip>\\<share>\\`

7. apt & conda update in cron:
  * `sudo vim /etc/sudoers.d/apt`
```
# apt for Koljasha without password

koljasha ALL = (ALL) NOPASSWD: /usr/local/bin/apt
```
  * `crontab -e`
```
0 */4 * * * sudo apt update && sudo apt dist-upgrade --yes && sudo apt autoremove --yes
10 */4 * * * /home/koljasha/soft/conda/bin/conda update --all --yes
```

8. mount ntfs disk on boot:
  * show disks: `sudo blkid` or `lsblk -o "NAME,SIZE,LABEL,MOUNTPOINT,UUID"`
  * write UUID to `/etc/fstab`, for example:
```
# <file system>             <mount point>  <type>  <options>  <dump>  <pass>
UUID=7488d026-ea24-4c24-9618-3d54d0dee8db /              ext4    defaults,noatime 0 1
UUID=81174079-1ed8-4986-9269-b614e120856a	none	swap	defaults	0	0
UUID="01D09BCBA9456C70"	/run/mount/storage	ntfs	rw,notail,relatime	0	0
```

9. mount disk on boot:
  * show disks: `sudo blkid` or `lsblk -o "NAME,SIZE,LABEL,MOUNTPOINT,UUID"`
  * write UUID to `/etc/fstab`, for example:
```
# <file system> <dir> <type> <options> <dump> <pass>

# /dev/nvme0n1p1 LABEL=Arch
UUID=f3a3fdc6-ab9c-4633-9bfd-030766b079c1	/         	ext4      	rw,relatime	0 1

# swapfile
/swapfile	none	swap	defaults	0 0

# /dev/sda4 LABAL=Storage
UUID=c6ab23b5-1b6d-4c3f-8488-6efee0144e54	/run/mount/storage/	ext4	rw,relatime	0 2
```

10. chroot in other linux (для корректной работы нужен пакет: [arch-install-scripts](https://www.thegeekdiary.com/arch-chroot-command-not-found/))
  * `sudo mount /dev/sdaX /mnt`
  * `sudo arch-chroot /mnt`
  * `su - username`
  * *do something*
  * `exit` and `exit`
  * `sudo umount /mnt`

11. Если нет wifi-адаптера
  * [rtl8821ce](https://github.com/tomaspinho/rtl8821ce)
  * [rtl8821ce-dkms-git](https://aur.archlinux.org/packages/rtl8821ce-dkms-git)

12. Если нет ethernet
  * [Archlinux](https://archlinux.org/packages/?q=r8168)
  * [Manjaro](https://packages.manjaro.org/?query=8168)

13. Скрыть/Показать пользователя
  * `sudo vim /var/lib/AccountsService/users/USERNAME`
  * Скрыть: `SystemAccount=true`
  * Показать: `SystemAccount=false`

14. Использование Rsync, Fd, Rg
  * `rsync -av file server:folder/`
  * `rsync -av --delete src/ dest/`    # delete extraneous files from dest dirs
  * `fd -HI <search>` or `fd --hidden --no-ignore <search>`
  * `rg --hidden --no-ignore --ignore-case <search>`

15. Некоторые комбинации fish(`bind --all`):
  * `alt + <-`   - перемещение по истории папок (prevd)
  * `alt + ->`   - перемещение по истории папок (nextd)
  * `alt + l`   - команда ls
  * `alt + p`   - добавить | less
  * `alt + w`   - информация о команде (type)
  * `alt + e`   - запустить $EDITOR
  * `alt + s`   - добавить sudo

16. [Useful bash keymap](https://gist.github.com/1eedaegon/6372b024c3793fa4887190d01f6c21f9)

  * Move and delete cursor
    - `Ctrl + b`: move cursor backward
    - `Ctrl + f`: move cursor forward
    - `Ctrl + h`: delete character on before cursor
    - `Ctrl + d`: delete character on current cursor
    - `Ctrl + a`: move cursor to begin of the line
    - `Ctrl + e`: move cursor to end of the line
    - `Meta(Alt or Option) + b`: move cursor to begin of a word
    - `Meta(Alt or Option) + f`: move cursor to end of a word
    - `Ctrl + p`: load previous command
    - `Ctrl + n`: load next command

  * Cut and save word on buffer(kill ring - deque)
    - `Ctrl + w`: cut word on before cursor
    - `Meta(Alt or Option) + d`: cut word on current cursor
    - `Ctrl + u`: cut word from beginning to before cursor
    - `Ctrl + k`: cut word from current cursor to end
    - `Ctrl + y`: paste word (yank)
    - `Meta(Alt or Option) + y`: Pass over to buffer

17. Использование `WINEPREFIX`
  * `WINEPREFIX=~/tmp/prefix/ WINEARCH=win64 winecfg`
  * `WINEPREFIX=~/tmp/prefix/ winetricks dxvk`
  * `WINEPREFIX=~/tmp/prefix/ wine <game>.exe`
  * example `.desktop` file:
  ```
[Desktop Entry]
Name=The Binding of Isaac - Rebirth
Exec=env WINEPREFIX="/run/mount/storage/local/wineprefixes/Isaac" /usr/bin/wine C:\\\\ProgramData\\\\Microsoft\\\\Windows\\\\Start\\ Menu\\\\Programs\\\\R.G.\\ Mechanics\\\\The\\ Binding\\ of\\ Isaac\\ -\\ Rebirth\\\\Играть\\ The\\ Binding\\ of\\ Isaac\\ -\\ Rebirth.lnk
Type=Application
StartupNotify=true
Path=/run/mount/storage/local/wineprefixes/Isaac/dosdevices/c:/Program Files (x86)/R.G. Mechanics/The Binding of Isaac - Rebirth
Icon=A444_isaac-ng.0
StartupWMClass=isaac-ng.exe
  ```
18. Отключить os-prober для GRUB: `sudo chmod -x /etc/grub.d/30_os-prober`

19. Cinnamon апплет *Меню скриптов* `~/.local/share/nemo/scripts`:
```
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

20. **Fish Shell** : `sudo chsh -s /usr/bin/fish koljasha`
* [Install Fish](https://fishshell.com/docs/current/index.html#installation)
* [Install Oh My Fish](https://github.com/oh-my-fish/oh-my-fish/wiki#install)
* [Koljasha settings](https://github.com/Koljasha/archlinux/blob/master/packages#L707)

21. **Zsh Shell** : `sudo chsh -s /usr/bin/zsh koljasha`
* [Install Zsh](https://github.com/ohmyzsh/ohmyzsh/wiki/Installing-ZSH#how-to-install-zsh-on-many-platforms)
* [Install Oh My Zsh](https://github.com/ohmyzsh/ohmyzsh/wiki#welcome-to-oh-my-zsh)
* [Install zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions/blob/master/INSTALL.md#oh-my-zsh)
* [Install zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/INSTALL.md#with-a-plugin-manager)
* `vim .zshrc`:
```
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

# Bindkeys
bindkey '\e.' insert-last-word

# User configuration
.........
```

22. **Bash Shell** : `sudo chsh -s /usr/bin/bash koljasha`
* [Install Oh My Bash](https://github.com/ohmybash/oh-my-bash#basic-installation)
* `vim .bashrc`:
```
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

23. **Enable | Disable** `sudo systemctl reboot` command:
* disable: `sudo systemctl mask reboot.target`
* enable: `sudo systemctl unmask reboot.target`

24. Copy to clipboard
* `echo 'qwerty_xclip' | xclip -selection clipboard`
* `echo 'qwerty_xsel' | xsel --clipboard`
