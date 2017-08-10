## Git - основные команды и настройки

* Имя:                           git config --global user.name "Koljasha"
* E-mail:                        git config --global user.email "koljasha@mail.ru"
* Редактор:                      git config --global core.editor vim
* Утилита сравнения:             git config --global merge.tool vimdiff
* Push только эту ветку:         git config --global push.default simple
* Сохранить пароль:              git config --global credential.helper store
* Сбросить сохранение пароля:    git config --global --unset credential.helper
** **
* Создать:                       git init
** **
* Скачать:                       git clone https://github.com/.....
* Скачать только 1 ветку:        git clone --branch _branch_ https://github.com/.....
* Слить:                         git pull
* Залить:                        git push
* Залить/перезалить:             git push --force
** **
* Статус:                        git status
* Добавить:                      git add .... (from status)
* Добавить все:                  git add -A 	or  git add .
* Отменить:                      git checkout -- .... (from status)
* Добавить и закоммитить:        git commit -a
* Закоммитить:                   git commit -m "Text commit"
* Изменения:                     git diff
** **
* Лог:                           git log
* Лог в 1 строку:                git log --oneline
* Показать коммит:               git show _number_commit_
** **
* Откатить:                      git reset --hard _number_commit_
* Откатить, сохранить коммит:    git reset --soft _number_commit_
** **
* Обновить неотслеживаемые файлы:
```
git rm -r --cached .
git add .
git commit -m "fixed untracked files"
```
** **
* Ветки локально:                git branch
* Ветки все:                     git branch -a
* Создать ветку:                 git checkout -b _branch_
* Сменить ветку:                 git checkout _branch_
* Удалить ветку локально:        git branch -D _branch_
* Удалить ветку удаленно:        git push --delete origin _branch_
* Переписать локальную:
```
git fetch
git reset --hard origin/<branch>
```
** **
* Сшить коммиты:                 git rebase -i Head~_number_
```
* где первый pick, или reword
* далее fixup
```
** **
