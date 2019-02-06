## Базовые плагины Sublime

* Package Control - менеджер пакетов (стандартно)
* Material Theme - схема и тема
***

* A File Icon - иконки файлов
* AceJump - быстрое перемещение (аналог EasyMotion)
* AutoFileName - автодобавление имен файлов
* SideBarEnhancements - расширение SideBar
* AllAutocomplete - автодобавление по открытым файлам
* AdvancedNewFile - создание нового файла (super+alt+n или ctrl+alt+n)
* PackageResourceViewer - редактирование ресурсов/плагинов
<br>

* ColorHighlighter - подсветить цвет (Ctrl+Shift+C - Color picker)
* BracketHighlighter - выделить теги/скобки (ярко)
* Emmet - автонаписание HTML и СSS (для Win нужно PyV8 Binaries)
***

* ColorCoder - дополнительная раскраска кода
* SublimeCodeIntel - автодополнения кода
* SublimeREPL - интерактивная среда
<br>

* other completion - различные автодополнения
* other linter - проверки синтаксиса и т.п.
<br>

* Git - git в Sublime
* GitGutter - изменения
<br>

* LocalizedMenu - локализация
***
***

#### Main:
* A File Icon
* AceJump
* All Autocomplete
* AutoFileName
* BracketHighlighter
* Color Highlight
* ColorPicker
* PackageResourceViewer
* SideBarEnhancements
* SublimeREPL
* SublimeLinter
#### HTML-CSS-JS:
* HTML-CSS-JS Prettify
* JavaScript Completions
* LiveReload
* SublimeLinter-eslint
* View In Browser
* Vue Syntax Highlight
#### Python:
* SublimePythonIDE
* Virtualenv
***
***

### Русский язык в Python + Virtualenv Build System:
* открыть Virtualenv с помощью PackageResourceViewer (Open Resource)
* добавить в Python + Virtualenv.sublime-build 
`"env": {"PYTHONIOENCODING": "utf-8"}`
