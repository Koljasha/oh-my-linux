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
** **
* merge to main|master
 ```
 git checkout main
 git merge _branch_
 ```
** **
* Удалить ветку локально:        git branch -d _branch_
* Удалить ветку удаленно:        git push --delete origin _branch_
* Переписать локальную:
```
git fetch
git reset --hard origin/<branch>
```
** **
* Смотрим количество _number_:   git log --oneline | wc -l
* Сшить коммиты:                 git rebase -i Head~_number_
```
* где первый pick, или reword
* далее fixup
```
** **
* Полное клонирование: `git clone --mirror URL`
* Архивация в один файл: `git bundle create файл.bundle --all` : `git clone файл.bundle новая_папка`

** **

* [Github Docs](https://docs.github.com/en/get-started/getting-started-with-git/managing-remote-repositories) - добавить удаленные репо
* показать: `git remote -v`
* изменить *основной | origin*: `git remote set-url origin https://koljasha@github.com/koljasha/new_example_repo.git`
 
* добавить: `git remote add gitlab https://koljasha@gitlab.com/koljasha/example_repo.git`
* изменить *дополнительный*: `git remote set-url gitlab https://koljasha@gitlab.com/koljasha/new_example_repo.git`
* удалить: `git remote rm gitlab`
* использовать: `git push gitlab`

** **

* [Gitleaks](https://github.com/gitleaks/gitleaks) - проверка на секреты
    * `gitleaks dir . -v`
    * `gitleaks git . -v`
    * если что-то нужно не учитывать `.gitleaks.toml` пример:
```
title = "Игнорируем Gitleaks"

[allowlist]
description = "Исключения для мультимедиа клавиш"
regexes = [
  '''XF86[A-Za-z]+''',      # Все XF86* клавиши
]
```

** **
* [Git filter-repo](https://github.com/newren/git-filter-repo) - удаление из коммитов
  * `--dry-run` - пробный запуск без изменений
  * `--debug` - подробный вывод

* [Git filter-repo](https://github.com/newren/git-filter-repo) - удалить токен-пароль
    * `git filter-repo --replace-text ../replacements.txt `, где `replacements.txt` пример:
```
'password': 'real_pass'==>'password': '[PASS]'
regex:base_token = '[A-Za-z0-9+/=]{10,}'==>base_token = '[TOKEN]'
```

* [Git filter-repo](https://github.com/newren/git-filter-repo) - удалить файл-каталог
    * `git filter-repo --path 'themes/' --path 'images/' --invert-paths`

* посмотреть самые большие файлы:
```
bash -c 'git rev-list --all --objects | \
  while read hash path; do
    size=$(git cat-file -s $hash 2>/dev/null || echo 0)
    if [ $size -gt 0 ]; then
      human_size=$(numfmt --to=iec-i --suffix=B --format="%9f" $size 2>/dev/null || echo "${size}B")
      echo "$human_size $hash $path"
    fi
  done | \
  sort -h -k1 | \
  tail -30'
```

* Далее обновить удаленный репозиторий (стирается)
    * `git remote add origin git@github.com:koljasha/repo.git`
    * `git remote -v`
    * `git push origin master --force`
    * `git push origin --force --all`

** **

