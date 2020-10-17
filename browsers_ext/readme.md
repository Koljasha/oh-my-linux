## Vim расширения для браузеров
* **Chrome** - [cVim](https://github.com/1995eaton/chromium-vim)
* **Firefox** - [Vim Vixen](https://github.com/ueokande/vim-vixen)
```
{
  "keymaps": {
    "0": {
      "type": "scroll.home"
    },
    ":": {
      "type": "command.show"
    },
    "o": {
      "type": "command.show.open",
      "alter": false
    },
    "b": {
      "type": "command.show.buffer"
    },
    "O": {
      "type": "command.show.open",
      "alter": true
    },
    "t": {
      "type": "command.show.tabopen",
      "alter": false
    },
    "a": {
      "type": "command.show.tabopen",
      "alter": false
    },
    "T": {
      "type": "command.show.tabopen",
      "alter": true
    },
    "": {
      "type": "command.show.winopen",
      "alter": false
    },
    "B": {
      "type": "command.show.buffer"
    },
    "w": {
      "type": "scroll.vertically",
      "count": -1
    },
    "s": {
      "type": "scroll.vertically",
      "count": 1
    },
    "e": {
      "type": "scroll.vertically",
      "count": -5
    },
    "d": {
      "type": "scroll.vertically",
      "count": 5
    },
    "h": {
      "type": "scroll.horizonally",
      "count": -1
    },
    "l": {
      "type": "scroll.horizonally",
      "count": 1
    },
    "gg": {
      "type": "scroll.top"
    },
    "G": {
      "type": "scroll.bottom"
    },
    "$": {
      "type": "scroll.end"
    },
    "x": {
      "type": "tabs.close"
    },
    "X": {
      "type": "tabs.reopen"
    },
    "K": {
      "type": "tabs.prev",
      "count": 1
    },
    "E": {
      "type": "tabs.prev",
      "count": 1
    },
    "J": {
      "type": "tabs.next",
      "count": 1
    },
    "g0": {
      "type": "tabs.first"
    },
    "g$": {
      "type": "tabs.last"
    },
    "r": {
      "type": "tabs.reload",
      "cache": false
    },
    "R": {
      "type": "tabs.reload",
      "cache": true
    },
    "zp": {
      "type": "tabs.pin.toggle"
    },
    "zd": {
      "type": "tabs.duplicate"
    },
    "zi": {
      "type": "zoom.in"
    },
    "zo": {
      "type": "zoom.out"
    },
    "zz": {
      "type": "zoom.neutral"
    },
    "f": {
      "type": "follow.start",
      "newTab": false
    },
    "F": {
      "type": "follow.start",
      "newTab": true
    },
    "S": {
      "type": "navigate.history.prev"
    },
    "D": {
      "type": "navigate.history.next"
    },
    "[[": {
      "type": "navigate.link.prev"
    },
    "]]": {
      "type": "navigate.link.next"
    },
    "gu": {
      "type": "navigate.parent"
    },
    "gU": {
      "type": "navigate.root"
    },
    "gi": {
      "type": "focus.input"
    },
    "yy": {
      "type": "urls.yank"
    },
    "p": {
      "type": "urls.paste",
      "newTab": false
    },
    "P": {
      "type": "urls.paste",
      "newTab": true
    },
    "/": {
      "type": "find.start"
    },
    "n": {
      "type": "find.next"
    },
    "N": {
      "type": "find.prev"
    },
    "<S-Esc>": {
      "type": "addon.toggle.enabled"
    }
  },
  "search": {
    "default": "google",
    "engines": {
      "google": "https://google.com/search?q={}",
      "yandex": "https://yandex.ru/search/?text={}",
      "bing": "https://www.bing.com/search?q={}",
      "duckduckgo": "https://duckduckgo.com/?q={}"
    }
  },
  "properties": {
    "hintchars": "abcdefghijklmnopqrstuvwxyz",
    "smoothscroll": false
  }
}
```
