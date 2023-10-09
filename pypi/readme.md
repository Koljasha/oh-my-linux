## Прямые ссылки пакетов из PyPi | Пример PKGBUILD из PyPi

* api (ссылки в urls):
    * https://pypi.org/pypi/Django/json
* каталог:
    * https://files.pythonhosted.org/packages/source/D/Django/Django-4.2.6.tar.gz
    * https://files.pythonhosted.org/packages/py3/D/Django/Django-4.2.6-py3-none-any.whl


* api (ссылки в urls):
    * https://pypi.org/pypi/flask/json (ссылки в urls)
* каталог:
    * https://files.pythonhosted.org/packages/source/f/flask/flask-3.0.0.tar.gz
    * https://files.pythonhosted.org/packages/py3/f/flask/flask-3.0.0-py3-none-any.whl

***

```
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
