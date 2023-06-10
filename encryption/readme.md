## Шифрование | дешифрование на примере копии данных **pass**

1. Работа с архивом **tar**
* *создание архива*
  * `tar czvf pass.tar.gz --directory=/home/koljasha .password-store/`
* *разархивирование*
  * `tar xzvf pass.tar.gz`
***

2. Симметричное | ассиметричное шифрование с помощью **GPG**
* *симметричное шифрование - расшифровка по паролю*:
* `-c`, `--symmetric`, `-a`, `--armor`
  * `gpg -c pass.tar.gz` - *бинарный формат - gpg*
  * `gpg -c -a pass.tar.gz` - *текстовый формат - asc*
* *ассиметричное шифрование - расшифровка по приватному ключу пользователя koljasha*
* `-e`, `--encrypt`, `-r`, `--recipient`, `-a`, `--armor`
  * `gpg -r koljasha -e pass.tar.gz` - *бинарный формат - gpg*
  * `gpg -r koljasha -e -a pass.tar.gz` - *текстовый формат - asc*
* *расшифровка*:
* `-d`, `--decrypt`
  * `gpg -d pass.tar.gz.gpg > pass.tar.gz` - *бинарный формат - gpg*
  * `gpg --decrypt pass.tar.gz.asc > pass.tar.gz` - *текстовый формат - asc*
***

3. Симметричное шифрование с помощью **OpenSSL**
* *шифрование*
  * `openssl aes-256-cbc [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes` - *бинарный формат - aes*
  * `openssl aes-256-cbc -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes.asc` - *текстовый формат - asc*
* *расшифровка (параметры pbkdf2 и iter должны совпадать с параметрами шифрования)*
  * `openssl aes-256-cbc -d [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes -out pass.tar.gz` - *бинарный формат - aes*
  * `openssl aes-256-cbc -d -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes.asc -out pass.tar.gz` - *текстовый формат - asc*
***

4. Создание зашифрованного архива **zip**
* *перейти в домашнюю директорию*: `cd ~`
* *создание архива и шифрование паролем*
  * `zip -e -r pass.zip .password-store/`
  * `zip --encrypt -r pass.zip .password-store/`

***
***

## Зашифрованный раздел с помощью **cryptsetup**

* *опционально* Создание ключа шифрования
  * `openssl genrsa -out keyfile`
  * `chmod 400 keyfile; chown root:root keyfile`
1. Создание зашифрованного раздела
  * `sudo cryptsetup luksFormat /dev/sdXY`
  * `sudo cryptsetup luksAddKey /dev/sdaXY keyfile` - *опционально* Добавление ключа
2. Открытие зашифрованного раздела
  * `sudo cryptsetup open /dev/sdaXY crypto`
  * *или* `sudo cryptsetup open /dev/sdaXY crypto --key-file=keyfile`
3. Форматирование
  * `sudo mkfs.ext4 /dev/mapper/crypto`
4. Открытие расшифрованного раздела
  * `sudo mount /dev/mapper/crypto /mnt`
  * *или* `udisksctl mount -b /dev/mapper/crypto`
5. Размонтирование раздела
  * `sudo umount /mnt/`
  * *или* `udisksctl unmount -b /dev/mapper/crypto`
6. Закрытие раздела
  * `sudo cryptsetup close crypto`

***

