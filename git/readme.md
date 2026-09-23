# Git — шпаргалка: основные команды и настройки

## Настройка

* Имя:                          `git config --global user.name "User"`
* E-mail:                       `git config --global user.email "user@example.com"`
* Редактор:                     `git config --global core.editor vim`
* Утилита сравнения:            `git config --global merge.tool vimdiff`
* Push только текущую ветку:    `git config --global push.default simple`
* Запомнить пароль на 1 час:    `git config --global credential.helper 'cache --timeout=3600'`
* Забыть сохранённый пароль:    `git config --global --unset credential.helper`

> Внимание: `credential.helper store` хранит пароль открытым текстом в `~/.git-credentials`.
> Используй `cache` (временно, в памяти) или менеджер паролей ОС (`libsecret`, `manager`).

## Создание и клонирование

* Создать репозиторий:          `git init`
* Склонировать:                 `git clone <URL>`
* Склонировать одну ветку:      `git clone --branch <ветка> <URL>`

## Синхронизация

* Забрать и слить:              `git pull`
* Отправить:                    `git push`
* Безопасно перезаписать:       `git push --force-with-lease`
* Полностью перезаписать:       `git push --force` (только если точно знаешь, что делаешь, — затирает чужую работу)

## Изменения и коммиты

* Статус:                       `git status`
* Добавить файл:                `git add <файл>` (см. вывод `status`)
* Добавить всё:                 `git add -A`
* Отменить изменения в файле:   `git restore <файл>`
* Добавить и закоммитить отслеживаемые: `git commit -a -m "Текст коммита"`
* Закоммитить staged:           `git commit -m "Текст коммита"`
* Посмотреть изменения:         `git diff`

> Legacy-синтаксис: старый `git checkout` для этих операций заменён на `git switch` (ветки) и `git restore` (файлы).

## История и отмена

* Лог:                          `git log`
* Лог в одну строку:            `git log --oneline`
* Показать коммит:              `git show <хеш>`
* Сколько коммитов:             `git log --oneline | wc -l`
* Жёсткий откат:                `git reset --hard <хеш>`
* Мягкий откат (коммит остаётся в index): `git reset --soft <хеш>`

Обновить индекс, если `.gitignore` изменился задним числом:

```
git rm -r --cached .
git add .
git commit -m "fixed untracked files"
```

## Ветки

* Ветки локально:               `git branch`
* Все ветки:                    `git branch -a`
* Создать и перейти:            `git switch -c <ветка>`
* Перейти:                      `git switch <ветка>`
* Удалить локально:             `git branch -d <ветка>`
* Удалить на сервере:           `git push --delete origin <ветка>`
* Переписать локальную по удалённой:
```
git fetch
git reset --hard origin/<ветка>
```

Слить ветку в `main`:

```
git switch main
git merge <ветка>
```

Сшить коммиты (первые `pick`/`reword`, далее `fixup`):

```
git rebase -i HEAD~<число>
```

## Удалённые репозитории

* Показать:                     `git remote -v`
* Поменять `origin`:            `git remote set-url origin <URL>`
* Добавить второй пульт:        `git remote add gitlab <URL>`
* Поменять второй пульт:        `git remote set-url gitlab <URL>`
* Удалить пульт:                `git remote remove gitlab`
* Отправить во второй пульт:    `git push gitlab`

## Проверка на секреты: gitleaks

```
gitleaks dir . -v
gitleaks git . -v
```

Исключения через `.gitleaks.toml`:

```
title = "Игнорируем Gitleaks"

[allowlist]
description = "Исключения для мультимедиа клавиш"
regexes = [
  '''XF86[A-Za-z]+''',
]
```

## Очистка истории: git filter-repo

* Пробный запуск без изменений: `--dry-run`
* Подробный вывод:              `--debug`
* Заменить секреты по файлу замен (пример `replacements.txt`):
```
'password': 'real_pass'==>'password': '[PASS]'
regex:base_token = '[A-Za-z0-9+/=]{10,}'==>base_token = '[TOKEN]'
```
```
git filter-repo --replace-text replacements.txt
```
* Удалить каталоги из истории:
```
git filter-repo --path 'themes/' --path 'images/' --invert-paths
```

Найти самые большие файлы в истории:

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

После чистки истории удалённый репозиторий перезаписывается (данные стираются):

```
git remote add origin <URL>
git remote -v
git push origin --force-with-lease --all
```

## Копия и архив

* Полное зеркало:               `git clone --mirror <URL>` → `git clone mirror_path new_folder`
* Архив в один файл:            `git bundle create file.bundle --all` → `git clone file.bundle new_folder`
