## Базовые плагины Atom
* minimap
* file-icons
* highlight-selected
* pigments
* color-picker
***
* emmet
* atom-live-server
***
* atom-ide-ui
* atom-ternjs
* ide-typescript
***
* atom-beautify
* platformio-ide-terminal
* *(or terminal-plus)*
***
* autocomplete-paths

for *html* add to *config.cson*:
```
  "autocomplete-paths":
    scopes: [
      {
        scopes: ['text.html.basic'],
        prefixes: [
          'src=[\'"]',
          'href=[\'"]'
        ],
        extensions: ['html', 'css', 'js', 'png', 'gif', 'jpeg', 'jpg'],
        relative: true
      }
    ]
```
***
* Скрыть ограничитель длины строки:
`Settings => Packages => wrap-guide => Disable`
