## Первичная настройка Linux

1. Обновить пакеты и ядро - перезагруть.

2. Дополнительные пакеты:
    * Mint: `sudo apt install git vim cmake build-essential libxkbfile-dev silversearcher-ag exuberant-ctags numlockx terminator tmux`
    * Manjaro: `sudo pacman -S --needed vim cmake wget the_silver_searcher ctags bash-completion noto-fonts terminator tmux`

3. Настройки:
    * через параметры
    * кнопки слева: Закрыть, Свернуть, Развернуть
    * иконки на панели: Терминал, Папки, Браузер
    * иконки Mint-x: `git clone https://github.com/linuxmint/mint-x-icons.git`
    
4. Miniconda3 в `/home/koljasha/soft/conda`
```
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
&& bash Miniconda3-latest-Linux-x86_64.sh
```

5. Node.js - Node Version Manager: `https://github.com/creationix/nvm`

6. Добавить в .bashrc
```
# only for Ubuntu and Mint...
# alias for apt
alias aptupdate="apt update && apt dist-upgrade --yes && apt autoremove --yes"

# alias for weather in Korolev
alias weather="curl http://wttr.in/Королев"

# alias for python virtual envorenment
alias venvactivate="source venv/bin/activate"
alias venvcreate="virtualenv venv && venvactivate"
```
выполнить `source ~/.bashrc`

7. Репозиторий настройки Vim - PowerLine
```
git clone https://github.com/koljasha/oh-my-vim.git && \
cd oh-my-vim && ./linux.sh && cd .. && \
vim -c PlugInstall

# PowerLine for Bash add to .bashrc (поправить версию Python):
powerline-daemon -q
POWERLINE_BASH_CONTINUATION=1
POWERLINE_BASH_SELECT=1
. /home/koljasha/soft/conda/lib/python3.7/site-packages/powerline/bindings/bash/powerline.sh
```
выполнить `source ~/.bashrc`

8. * для bash без powerline / серверов [Oh My Bash](https://github.com/Koljasha/oh-my-bash)
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

9. Настройка времени:
`%H:%M %A %x` или `%X %A %x`

10. Настройка Terminator:
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

11. Настройка git:
```
git config --global user.name "Koljasha" \
&& git config --global user.email "koljasha@mail.ru" \
&& git config --global core.editor vim \
&& git config --global merge.tool vimdiff \
&& git config --global push.default simple \
&& git config --global credential.helper store
```

12. bash_completion для Manjaro:
добавить в .bashrc:
```
[ -r /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion
```

13. *Fish Shell*: `sudo chsh -s /usr/bin/fish koljasha`
* do `fish_update_completions`
* install *omf*: `curl -L https://get.oh-my.fish | fish`
* Themes: *agnoster*, *shellder*: `omf install agnoster`
* `vim .config/fish/config.fish`:
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
# alias for apt
function aptupdate
        sudo apt update; and sudo apt dist-upgrade --yes; and sudo apt autoremove --yes;
end
#
###

# python virtualenv
#
function venvactivate
        source venv/bin/activate.fish
end

function venvcreate
        virtualenv venv; and venvactivate;
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

14. *tmux* (минимальная настройка) `~/.tmux.conf`:
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
