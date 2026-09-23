# Шифрование

Заметки по шифрованию на примере бэкапа хранилища **pass** (`~/.password-store/`).

## 1. Бэкап pass в tar-архив

* *Создание архива:*
  * `tar czvf pass.tar.gz --directory=~ .password-store/`
* *Разархивирование:*
  * `tar xzvf pass.tar.gz`

## 2. GPG: симметричное и асимметричное шифрование

### Симметричное (расшифровка по паролю)

* Флаги: `-c`, `--symmetric`, `-a`, `--armor`
  * `gpg -c pass.tar.gz` — *бинарный формат (.gpg)*
  * `gpg -c -a pass.tar.gz` — *текстовый формат (.asc)*

### Асимметричное (расшифровка по приватному ключу)

* Флаги: `-e`, `--encrypt`, `-r`, `--recipient`, `-a`, `--armor`
  * `gpg -r <key-id> -e pass.tar.gz` — *бинарный формат (.gpg)*
  * `gpg -r <key-id> -e -a pass.tar.gz` — *текстовый формат (.asc)*

### Расшифровка

* Флаги: `-d`, `--decrypt`
  * `gpg -d pass.tar.gz.gpg > pass.tar.gz` — *бинарный формат*
  * `gpg --decrypt pass.tar.gz.asc > pass.tar.gz` — *текстовый формат*

## 3. OpenSSL: симметричное шифрование aes-256-cbc

* *Шифрование:*
  * `openssl aes-256-cbc [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes` — *бинарный формат*
  * `openssl aes-256-cbc -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz -out pass.tar.gz.aes.asc` — *текстовый формат*
* *Расшифровка (параметры pbkdf2 и iter должны совпадать с параметрами шифрования):*
  * `openssl aes-256-cbc -d [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes -out pass.tar.gz` — *бинарный формат*
  * `openssl aes-256-cbc -d -a [-pbkdf2] [-iter <number>] -salt -in pass.tar.gz.aes.asc -out pass.tar.gz` — *текстовый формат*

## 4. Зашифрованный архив zip

* *Перейти в домашнюю директорию:* `cd ~`
* *Создание архива с шифрованием паролем:*
  * `zip -e -r pass.zip .password-store/`
  * `zip --encrypt -r pass.zip .password-store/`

> ⚠️ Предупреждение: классическое шифрование `zip -e` считается слабым. Не использовать для чего-то действительно ценного — для бэкапа `pass` предпочтительнее GPG или OpenSSL из разделов выше.

## 5. Зашифрованный раздел (LUKS через cryptsetup)

* *Опционально — создание ключа шифрования:*
  * `openssl genrsa -out keyfile 4096`
  * `chmod 400 keyfile; chown root:root keyfile`

1. *Создание зашифрованного раздела:*
   * `sudo cryptsetup luksFormat /dev/sdXY`
   * `sudo cryptsetup luksAddKey /dev/sdXY keyfile` — *опционально, добавление ключа*
2. *Открытие зашифрованного раздела:*
   * `sudo cryptsetup open /dev/sdXY crypto`
   * *или* `sudo cryptsetup open /dev/sdXY crypto --key-file=keyfile`
3. *Форматирование:*
   * `sudo mkfs.ext4 /dev/mapper/crypto`
4. *Монтирование расшифрованного раздела:*
   * `sudo mount /dev/mapper/crypto /mnt`
   * *или* `udisksctl mount -b /dev/mapper/crypto`
5. *Размонтирование раздела:*
   * `sudo umount /mnt/`
   * *или* `udisksctl unmount -b /dev/mapper/crypto`
6. *Закрытие раздела:*
   * `sudo cryptsetup close crypto`
