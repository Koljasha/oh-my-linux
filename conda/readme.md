### Работа с Python conda "боевой вариант"

#### установка conda (путь установки `~/.local/conda`)
* скачать c `https://repo.anaconda.com/miniconda/`
* переименовать в `miniconda.sh`
* `bash miniconda.sh -b -p ~/.local/conda 2>/dev/null`    -> установка
* `bash miniconda.sh -b -u -p ~/.local/conda 2>/dev/null`    -> обновление
* `echo "set PATH /home/$username/.local/conda/bin \$PATH" >> ~/.config/fish/config.fish`    -> добавить путь conda в $PATH (для fish)

#### основные команды conda
* `conda update --all --yes`    -> обновить все пакеты окружения (обычно мой alias : `conda.update`)
* `conda list`    -> все пакеты окружения
* `conda list -e > requirements.txt`    -> импорт списка всех пакетов для : `conda create --name <env> --file <this file>`
* `conda env list`    -> все окружения
* `conda create -n <env>`    -> создание окружения с текущей версией python
* `conda create -n <env> python=<ver>`    -> создание окружения conda с версией python <ver>
* `conda env remove -n <env>`    -> удалить окружение и все пакеты в нем
* `conda init fish`    -> активация fish для работы с окружениями conda
* `conda init --reverse fish`    -> деактивация fish для работы с окружениями conda
* `conda activate <env>`    -> активация окружения conda
* `conda deactivate`    -> деактивация окружения conda

#### боевой вариант работы с python (для меня)
