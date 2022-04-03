## Шифрование | расшифрование на примере копии данных **pass**

1. Работа с архивом **tar**
* *создание архива*
  * `tar czvf pass.tar.gz --directory=/home/koljasha .password-store/`
* *разархивирование*
  * `tar xzvf pass.tar.gz`

2. Симметричное | ассиметричное шифрование с помощью **GPG**
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
* *шифрование*
  * `openssl aes-256-cbc [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes` - *бинарный формат - aes*
  * `openssl aes-256-cbc -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes.asc` - *текстовый формат - asc*
* *расшифровка (параметры pbkdf2 и iter должны совпадать с параметрами шифрования)*
  * `openssl aes-256-cbc -d [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes -out pass.tar.gz` - *бинарный формат - aes*
  * `openssl aes-256-cbc -d -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes.asc -out pass.tar.gz` - *текстовый формат - asc*

4. Создание зашифрованного архива **zip**
* *перейти в домашнюю директорию*: `cd ~`
* *создание архива и шифрование паролем*
  * `zip -e -r pass.zip .password-store/`

