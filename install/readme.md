## Первичная настройка Linux

1. Обновить пакеты и ядро - перезагруть.

2. Дополнительные пакеты:
    * Mint: `sudo apt install wget git vim cmake bash-completion numlockx terminator tmux htop screenfetch x11vnc highlight lxappearance pcmanfm`
    * Mint: `sudo apt install silversearcher-ag exuberant-ctags build-essential libxkbfile-dev mint-meta-codecs checkinstall grub2-theme-mint`
    
    * Manjaro: `sudo pacman -S --needed wget git vim cmake bash-completion numlockx terminator tmux htop screenfetch x11vnc highlight lxappearance pcmanfm`
    * Manjaro: `sudo pacman -S --needed the_silver_searcher ctags noto-fonts ranger`

3. Настройки:
    * через параметры
    * кнопки: Закрыть, Свернуть, Развернуть    |    Свернуть в заголовок, Меню
    * иконки на панели: Папки, Терминал, Браузер
    * install plank
      * добавить "Сеансы и запуск" -> "Автозапуск"
      * снять "Диспетчер окон (дополнительно)" -> "Эффекты" -> "Тени под сворачивающимися окнами"
    * иконки Mint-x: `git clone https://github.com/linuxmint/mint-x-icons.git`
    
4. Miniconda3 в `/home/koljasha/soft/conda`
```
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
&& bash Miniconda3-latest-Linux-x86_64.sh
```

5. Node.js - Node Version Manager (nvm): 
* [Node Version Manager](https://github.com/nvm-sh/nvm)
* [Node Version Manager for Windows](https://github.com/coreybutler/nvm-windows)

6. [Oh My Vim](https://github.com/Koljasha/oh-my-vim) - репозиторий настройки Vim - установка Powerline
```
git clone https://github.com/koljasha/oh-my-vim.git && \
cd oh-my-vim && ./linux.sh && cd .. && \
vim -c PlugInstall
```
* использование [Powerline](#powerline)

7. Bash Shell `vim ~/.bashrc`:
```
# linux ll command
alias ll="ls -lah"

# only for Ubuntu and Mint...
# alias aptupdate="apt update && apt dist-upgrade --yes && apt autoremove --yes"

# alias for conda
alias condaupdate="conda update --all --yes"

# alias for python virtual envorenment
alias venvactivate="source venv/bin/activate"
alias venvcreate="python -m venv venv && venvactivate && pip install wheel"

# alias for weather in Korolev
alias weather="curl http://wttr.in/Королев"
```
* внешний вид:
   * [Oh My Bash by Koljasha with Git](#ohmybash)
   * [Powerline](#powerline)
   * [Oh My Bash](https://github.com/ohmybash/oh-my-bash):
      * `sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmybash/oh-my-bash/master/tools/install.sh)"`
      * in ~/.bashrc: `OSH_THEME="agnoster"`

8. <a name='ohmybash'>[Oh My Bash by Koljasha](https://github.com/Koljasha/oh-my-bash) - минималистичный bash без Powerline для серверов</a>
```
git clone https://github.com/Koljasha/oh-my-bash.git ~/.bash && \
echo >> ~/.bashrc && \
echo '# >>> Oh My Bash (git)' >> ~/.bashrc && \
echo 'export GITAWAREPROMPT=~/.bash/' >> ~/.bashrc && \
echo 'source "${GITAWAREPROMPT}/main.sh"' >> ~/.bashrc && \
echo '# <<< Oh My Bash (git)' >> ~/.bashrc && \
echo >> ~/.bashrc && \
source ~/.bashrc
```

9. bash_completion для Manjaro:
добавить в .bashrc:
```
[ -r /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion
```

10. Настройка времени:
`%H:%M %A %x` или `%X %A %x`

11. Настройка Terminator:
* Общий:
  * В фокусе фон: #0087AF
  * Шрифт: Noto Sans Regular 10
* Профили:
  * Общий - Шрифт: Monospace Regular 10
  * Фон - Прозрачный: 0,90
  * Прокрутка - Обратная прокрутка: 5000
* Комбинации клавиш:
  * close_term:   Shift+Ctrl+Q
  * close_window: Выключено
  * help: Выключено
```
# ~/.config/terminator/config
[global_config]
  enabled_plugins = LaunchpadCodeURLHandler, APTURLHandler, LaunchpadBugURLHandler
  title_font = Noto Sans 10
  title_transmit_bg_color = "#0087af"
  title_use_system_font = False
[keybindings]
  close_term = <Primary><Shift>q
  close_window = None
  help = None
[layouts]
  [[default]]
    [[[child1]]]
      parent = window0
      type = Terminal
    [[[window0]]]
      parent = ""
      type = Window
[plugins]
[profiles]
  [[default]]
    background_darkness = 0.9
    background_image = None
    background_type = transparent
    font = Monospace 10
    scrollback_lines = 5000
    use_system_font = False
```

12. Настройка git:
```
git config --global user.name "Koljasha" \
&& git config --global user.email "koljasha@mail.ru" \
&& git config --global core.editor vim \
&& git config --global merge.tool vimdiff \
&& git config --global push.default simple \
&& git config --global credential.helper store
```

13. *Zsh Shell*: `sudo chsh -s /bin/zsh koljasha`
* run zsh - choose *0*
* `vim ~/.zshrc`:
```
# Keep 1000 lines of history within the shell and save it to ~/.zsh_history:
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.zsh_history

# Use modern completion system
autoload -Uz compinit
compinit
zstyle ':completion:*' menu select

# linux ll command
alias ll="ls -lah"

# only for Ubuntu and Mint...
# alias aptupdate="apt update && apt dist-upgrade --yes && apt autoremove --yes"

# alias for conda
alias condaupdate="conda update --all --yes"

# alias for python virtual envorenment
alias venvactivate="source venv/bin/activate"
alias venvcreate="python -m venv venv && venvactivate && pip install wheel"
```
* [zsh-autosuggestions without Oh My Zsh](https://github.com/zsh-users/zsh-autosuggestions):
   * `git clone https://github.com/zsh-users/zsh-autosuggestions ~/.zsh/zsh-autosuggestions`
   * `vim ~/.zshrc`:
   ```
   # plugin zsh-autosuggestions
   source ~/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh
   bindkey ';5C' vi-forward-word
   bindkey ';5D' vi-backward-word
   ```
 * [zsh-syntax-highlighting without Oh My Zsh](https://github.com/zsh-users/zsh-syntax-highlighting):
   * `git clone https://github.com/zsh-users/zsh-syntax-highlighting ~/.zsh/zsh-syntax-highlighting`
   * `vim ~/.zshrc`:
   ```
   # plugin zsh-syntax-highlighting
   source ~/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
   ```
* внешний вид:
   * [Powerline](#powerline)
   * [Powerlevel9k](https://github.com/Powerlevel9k/powerlevel9k):
      * `git clone https://github.com/Powerlevel9k/powerlevel9k ~/.zsh/powerlevel9k`
      * `vim ~/.zshrc`:
      ```
      # theme powerlevel9k
      source ~/.zsh/powerlevel9k/powerlevel9k.zsh-theme
      POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(virtualenv context dir vcs)
      ```
   * [Oh My Zsh](https://github.com/robbyrussell/oh-my-zsh):
      * `sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"`
      * in ~/.zshrc: `ZSH_THEME="agnoster"`
      * [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions/blob/master/INSTALL.md#oh-my-zsh)
      * [zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/INSTALL.md#oh-my-zsh)
      * [Powerlevel9k](https://github.com/Powerlevel9k/powerlevel9k/wiki/Install-Instructions#option-2-install-for-oh-my-zsh)

14. *Fish Shell*: `sudo chsh -s /usr/bin/fish koljasha`
* do `fish_update_completions`
* `vim ~/.config/fish/config.fish`:
```
#
# Koljasha settings
#

set PATH /home/koljasha/soft/conda/bin $PATH
set fish_greeting

# aliases

# linux ll command
#
function ll --description 'List contents of directory using long format'
        ls -lah $argv
end
#
###

# only for Ubuntu and Mint...
#
# function aptupdate
#         sudo apt update; and sudo apt dist-upgrade --yes; and sudo apt autoremove --yes;
# end
#
###

# alias for conda
#
function condaupdate
         conda update --all --yes
end
#
###

# python virtualenv
#
function venvactivate
         source venv/bin/activate.fish
end

function venvcreate
         python -m venv venv; and venvactivate; and pip install wheel
end
#
###

# ssh connection
#
function sshkoljasha
    ssh -i ~/.ssh/{key}.pem {login}@{domain}
end
#
###

# vpn connection
#
# openvpn.ovpn -> koljasha.conf in /etc/openvpn/client
# #######
# vpn connection without password
# sudo vim /etc/sudoers.d/vpnkoljasha
#
# koljasha ALL = NOPASSWD:/bin/systemctl start openvpn-client@*, /bin/systemctl stop openvpn-client@*, /bin/systemctl status openvpn-client@*
#
# #######
#
function vpnstart
    sudo systemctl start openvpn-client@koljasha
end

function vpnstatus
    sudo systemctl status openvpn-client@koljasha
end

function vpnstop
    sudo systemctl stop openvpn-client@koljasha
end
#
###


```
* или создавать по аналогии: `vim ~/.config/fish/functions/ll.fish`:
```
function ll --description 'List contents of directory using long format'
        ls -lah $argv
end
```
* внешний вид:
   * [Powerline](#powerline)
   * [Oh My Fish](https://github.com/oh-my-fish/oh-my-fish)
      * `curl -L https://get.oh-my.fish | fish`
      * themes: *agnoster*, *shellder*: `omf install agnoster`

15. *tmux* (минимальная настройка) `~/.tmux.conf`:
```
set -g default-terminal "screen-256color"       # Терминал
set -g xterm-keys on
set -g prefix C-a                               # Leader key - Префикс
set -g history-limit 10000                      # История
set -g base-index 1                             # Начальный индекс
set -g pane-base-index 1
set -g mode-keys vi                             # Режим Vi для копирования
set -g set-titles on                            # Отображение тайтла
set -g display-time 1500                        # Время отображения сообщений
set -g display-panes-time 1500

# Мышь версия tmux => 2.1
set -g mouse on
# set -g mouse-utf8 on
bind-key m set -g mouse off\; display-message "Set option: mouse -> off"
bind-key M set -g mouse on\; display-message "Set option: mouse -> on"

# Мышь версия tmux < 2.1
# set -g mode-mouse on
# bind-key m set -g mode-mouse off
# bind-key M set -g mode-mouse on
```
* внешний вид:
   * [Powerline](#powerline)
   * [Oh My Tmux](https://github.com/gpakosz/.tmux)

16. <a name="powerline"> Powerline для Vim, Bash, Fish, Tmux: </a>
* vim (~/.vimrc - установлено из [Oh My Vim](https://github.com/Koljasha/oh-my-vim)):
```
# PowerLine for Vim add to ~/.vimrc:
set rtp+=/home/koljasha/soft/conda/lib/python3.8/site-packages/powerline/bindings/vim
```
* bash (~/.bashrc):
```
# PowerLine for Bash add to ~/.bashrc:
# sometimes need uncomment next line
# powerline-daemon -q
POWERLINE_BASH_CONTINUATION=1
POWERLINE_BASH_SELECT=1
source /home/koljasha/soft/conda/lib/python3.8/site-packages/powerline/bindings/bash/powerline.sh
```
* zsh (~/.zshrc):
```
# PowerLine for Zsh add to ~/.zshrc:
source /home/koljasha/soft/conda/lib/python3.8/site-packages/powerline/bindings/zsh/powerline.zsh
```
* fish (~/.config/fish/config.fish):
```
# PowerLine for Fish add to ~/.config/fish/config.fish:
set fish_function_path $fish_function_path "/home/koljasha/soft/conda/lib/python3.8/site-packages/powerline/bindings/fish"
powerline-setup
```
* tmux (~/.tmux.conf)
```
# PowerLine for Tmux add to ~/.tmux.conf
# sometimes need uncomment next line
# run-shell "powerline-daemon -q"
source "/home/koljasha/soft/conda/lib/python3.8/site-packages/powerline/bindings/tmux/powerline.conf"
```

17. Server x11vnc:
* `sudo vim /lib/systemd/system/x11vnc.service`
```
[Unit]
Description="x11vnc server"
Requires=multi-user.target
After=multi-user.target

[Service]
ExecStart=/usr/bin/x11vnc -auth guess -loop -forever -shared -rfbport 5900 -o /var/log/x11vnc.log
ExecStop=/usr/bin/killall x11vnc

[Install]
WantedBy=multi-user.target
```
* `sudo systemctl daemon-reload`
* `sudo systemctl status x11vnc.service`
* `sudo systemctl start x11vnc.service`
* `sudo systemctl enable x11vnc.service`
* `sudo systemctl status x11vnc.service`

18. Ranger File Manager
* `pip install ranger-fm` (Manjaro from repo)
* `ranger --copy-config=all`
* [~/.config/ranger/rc.conf](https://github.com/Koljasha/Linux/tree/master/ranger)
* https://github.com/cdump/ranger-devicons2:
   * `git clone https://github.com/cdump/ranger-devicons2 ~/.config/ranger/plugins/devicons2`
   * add `default_linemode devicons2` to `~/.config/ranger/rc.conf`
* auto `cd` : https://github.com/ranger/ranger/tree/master/examples
* syntax highlighting in ranger preview from package: *highlight*
