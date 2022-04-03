## Шифрование | расшифрование на примере копии данных **pass**

1. Работа с архивом **tar**
* *создание архива*
  * `tar czvf pass.tar.gz --directory=/home/koljasha .password-store/`
* *разархивирование*
  * `tar xzvf pass.tar.gz`

2. Симметричное|ассиметричное шифрование с помощью **GPG**
* *симметричное шифрование - расшифровка по паролю*
  * `gpg -c pass.tar.gz` - *бинарный формат - gpg*
  * `gpg -c -a pass.tar.gz` - *текстовый формат - asc*
* *ассиметричное шифрование - расшифровка по приватному ключу пользователя koljasha*
  * `gpg -r koljasha -e pass.tar.gz` - *бинарный формат - gpg*
  * `gpg -r koljasha -e -a pass.tar.gz` - *текстовый формат - asc*
* *расшифровка*
  * `gpg -d pass.tar.gz.gpg > pass.tar.gz` - *бинарный формат - gpg*
  * `gpg -d pass.tar.gz.asc > pass.tar.gz` - *текстовый формат - asc*

3. Симметричное шифрование с помощью **OpenSSL**

