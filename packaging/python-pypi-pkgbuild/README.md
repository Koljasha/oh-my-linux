# Сборка Python-пакетов из PyPI

Как достать прямую ссылку на исходники пакета из PyPI и упаковать
их в PKGBUILD для Arch Linux.

## Прямая ссылка через JSON API PyPI

У каждого пакета есть JSON с полем `urls`, где лежат прямые ссылки
на файлы:

```text
https://pypi.org/pypi/<имя-пакета>/json
```

Примеры (версии ниже — только примеры, за свежестью не гнаться):

* Django:
    * API: `https://pypi.org/pypi/Django/json`
    * исходники: `https://files.pythonhosted.org/packages/source/D/Django/Django-4.2.6.tar.gz`
    * wheel: `https://files.pythonhosted.org/packages/py3/D/Django/Django-4.2.6-py3-none-any.whl`
* Flask:
    * API: `https://pypi.org/pypi/flask/json`
    * исходники: `https://files.pythonhosted.org/packages/source/f/flask/flask-3.0.0.tar.gz`
    * wheel: `https://files.pythonhosted.org/packages/py3/f/flask/flask-3.0.0-py3-none-any.whl`

## Пример PKGBUILD для Python-пакета

```bash
pkgname=python-pulsectl-asyncio
_name=${pkgname#python-}
pkgver=1.1.1
pkgrel=1
pkgdesc="Asyncio frontend for pulsectl, a Python bindings library for PulseAudio (libpulse)"
arch=('any')
license=('MIT')
depends=('python' 'python-pulsectl')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
source=("https://files.pythonhosted.org/packages/source/${_name::1}/$_name/$_name-$pkgver.tar.gz")
sha256sums=('b5976b0ddd235d9ccc3455a03be664f7cb2201c942993b03ceb6b39d9cea8ad0')

build() {
  cd "$_name-$pkgver"
  python -m build --wheel --no-isolation
}

package() {
  cd "$_name-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
}
```

Шаблон ссылки на архив: первая буква имени пакета становится
подкаталогом (`.../source/<первая-буква>/<имя>/<имя>-<версия>.tar.gz`).

## См. также

* Минимальный учебный PKGBUILD:
  [../hello-world-pkgbuild/README.md](../hello-world-pkgbuild/README.md).
