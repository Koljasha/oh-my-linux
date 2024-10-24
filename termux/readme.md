## Настройка Termux
* [Shells](https://wiki.termux.com/wiki/Shells)
* [Remote Access](https://wiki.termux.com/wiki/Remote_Access)

#### Первоначальная настройка
* `termux-change-repo`
* `termux-setup-storage`

#### Обновление и установка пакетов
* `pkg upgrade`
* `pkg install fish openssh pass vim`

#### Настройка
* `chsh -s fish`
* `passwd`
* `vim ~/.config/fish/config.fish`
* `vim ~/.ssh/config`

#### Использование, как ssh-сервера
* `sshd` - запуск ssh-сервера
* `ssh USER@HOST -p 8022` - подключение с другой машины
* `pkill sshd` - остановка ssh-сервера

