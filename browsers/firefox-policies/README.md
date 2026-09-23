# Firefox — политика доступа только к разрешённым сайтам

Пример киоск-политики: файл [`policies.json`](policies.json) блокирует все сайты (`<all_urls>`), кроме списка исключений, и отключает приватный просмотр.

## Установка

```sh
sudo mkdir -p /etc/firefox/policies
sudo cp policies.json /etc/firefox/policies/policies.json
```

Путь `/etc/firefox/policies/` дистрибутивно-специфичен: в вашем дистрибутиве каталог политик может отличаться — сверьтесь с документацией [policy-templates](https://mozilla.github.io/policy-templates/) и пакетом Firefox.

Другие настройки браузера — см. [../README.md](../README.md).
