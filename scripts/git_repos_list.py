#!/usr/bin/env python3
"""Список всех репозиториев одного аккаунта на GitHub, GitLab или Bitbucket Cloud.

Использование
-------------
    ./git_repos_list.py github
    ./git_repos_list.py gitlab
    ./git_repos_list.py bitbucket
    ./git_repos_list.py github --json
    ./git_repos_list.py gitlab --all        # + проекты групп / репо организаций
    ./git_repos_list.py github --env-file ~/.config/git_repos_list/.env

Вывод — таблица: имя, видимость и итог; в шапке видно, использован ли токен:

    github: Koljasha (token)
      Koljasha/alpha  public
      Koljasha/beta   private

    Total: 2 (public 1, private 1)

С ``--json`` — объект с полями ``platform``, ``user``, ``authenticated``,
``total``, ``counts`` и ``repositories`` (``name``, ``visibility``, ``url``).

Страницы запрашиваются по 100 записей; защитный лимит — 10 000 репозиториев
за запуск (дальше скрипт останавливается с ошибкой).

Настройка через .env
--------------------
Площадка передаётся аргументом, всё остальное берётся из ``.env``. Скрипт
читает ``./.env``, а если его нет — ``.env`` рядом со скриптом; другой путь
задаётся ``--env-file``. Переменные, уже заданные в окружении, имеют приоритет
над файлом. Пример (chmod 600, в git не коммитить):

    # Аккаунт; по умолчанию Koljasha.
    REPO_USER=Koljasha

    # GitHub: classic PAT со scope ``repo`` либо fine-grained PAT с доступом
    # "All repositories" и правом Metadata: read
    # https://github.com/settings/tokens
    GITHUB_TOKEN=ghp_xxx

    # GitLab: personal access token со scope ``read_api``
    # (Settings -> Access tokens -> Personal)
    GITLAB_TOKEN=glpat-xxx

    # Bitbucket: API token со scope ``read:repository:bitbucket``; API-токены
    # передаются по HTTP Basic, поэтому нужен e-mail аккаунта
    # https://id.atlassian.com/manage-profile/security/api-tokens
    BITBUCKET_EMAIL=you@example.com
    BITBUCKET_TOKEN=ATATT-xxx

    # Необязательные переопределения для self-hosted и локальных тестов:
    # GITHUB_API_URL=https://api.github.com
    # GITLAB_URL=https://gitlab.com
    # BITBUCKET_API_URL=https://api.bitbucket.org/2.0

Допустимы кавычки (``KEY="a b"``), строки-комментарии (``#`` в начале строки)
и префикс ``export``; подстановка ``${VAR}`` и хвостовые комментарии
(``KEY=value # ...``) не поддерживаются.

Зачем токен, если работа идёт по SSH
------------------------------------
SSH-ключ аутентифицирует только ``git clone`` / ``git push``. Получение списка
репозиториев — это HTTPS-запрос к REST API, и приватные репозитории видны там
только аутентифицированному клиенту. Без токена скрипт тоже работает, но
возвращает лишь публичные репозитории.

Особенности площадок
--------------------
* GitHub  — с токеном ``/user/repos`` отдаёт репозитории владельца токена
  (``--all`` добавляет репо, где пользователь коллаборатор или член
  организации). ``REPO_USER`` участвует только в неаутентифицированном
  запросе к ``/users/{user}/repos``.
* GitLab  — ``--all`` требует токен и переключает на ``/projects?membership``
  (включая проекты групп и подгрупп; ``REPO_USER`` в этом режиме не
  используется). Без токена возвращаются только публичные личные проекты.
* Bitbucket — только Cloud (у Data Center другой API). Для личного workspace
  slug совпадает с именем аккаунта; ``REPO_USER`` — это и есть workspace.

Коды возврата: 0 — успех, 2 — ошибка API, сети, .env или аргументов.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

DEFAULT_USERNAME = "Koljasha"
PER_PAGE = 100
MAX_PAGES = 100
TIMEOUT = 30
USER_AGENT = "list-repos/1.0"

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Repo:
    name: str
    visibility: str
    url: str


class ApiError(RuntimeError):
    """Неустранимая ошибка API, транспорта или файла настроек."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _resolve_env_file(explicit: str | None) -> tuple[Path, bool]:
    """Возвращает путь к .env и признак того, что путь задан явно."""
    if explicit:
        return Path(explicit).expanduser(), True
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate, False
    return candidates[0], False


def load_env_file(path: Path, *, explicit: bool) -> None:
    """Читает KEY=VALUE из .env; уже заданные переменные окружения не трогает."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        if explicit:
            raise ApiError(f"env file not found: {path}") from None
        return
    except OSError as exc:
        raise ApiError(f"cannot read {path}: {exc}") from exc

    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not _KEY_RE.match(key):
            raise ApiError(f"{path}:{number}: expected KEY=VALUE, got {raw.strip()!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _get_json(url: str, headers: dict[str, str]) -> tuple[object, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.load(response)
            return payload, {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise ApiError(f"HTTP {exc.code} {exc.reason} for {url}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"cannot reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ApiError(f"invalid JSON from {url}: {exc}") from exc


def _items(payload: object, url: str) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        raise ApiError(f"unexpected response shape from {url}")
    return [item for item in payload if isinstance(item, dict)]


def _next_link(headers: dict[str, str]) -> str | None:
    for part in headers.get("link", "").split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None


def _with_page(url: str, page: int) -> str:
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "page"]
    query.append(("page", str(page)))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def fetch_github(user: str, all_accessible: bool) -> Iterator[Repo]:
    """Репозитории GitHub: все доступные при наличии токена, иначе только публичные."""
    token = _env("GITHUB_TOKEN")
    api = (os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        affiliation = "owner,collaborator,organization_member" if all_accessible else "owner"
        url = f"{api}/user/repos?per_page={PER_PAGE}&affiliation={affiliation}&sort=full_name"
    else:
        url = (
            f"{api}/users/{urllib.parse.quote(user)}/repos"
            f"?per_page={PER_PAGE}&type=owner&sort=full_name"
        )

    for _ in range(MAX_PAGES):
        payload, page_headers = _get_json(url, headers)
        for item in _items(payload, url):
            yield Repo(
                name=str(item.get("full_name", "")),
                visibility=str(
                    item.get("visibility") or ("private" if item.get("private") else "public")
                ),
                url=str(item.get("html_url", "")),
            )
        next_url = _next_link(page_headers)
        if not next_url:
            return
        url = next_url
    raise ApiError(f"pagination exceeded {MAX_PAGES} pages")


def fetch_gitlab(user: str, all_accessible: bool) -> Iterator[Repo]:
    """Проекты GitLab: личные, а с токеном и ``--all`` — все, где есть членство."""
    token = _env("GITLAB_TOKEN")
    host = (os.environ.get("GITLAB_URL") or "https://gitlab.com").rstrip("/")
    api = f"{host}/api/v4"
    headers = {"Accept": "application/json"}
    if token:
        headers["PRIVATE-TOKEN"] = token
    if token and all_accessible:
        url = f"{api}/projects?membership=true&per_page={PER_PAGE}&order_by=path&sort=asc"
    else:
        url = (
            f"{api}/users/{urllib.parse.quote(user)}/projects"
            f"?per_page={PER_PAGE}&order_by=path&sort=asc"
        )

    for _ in range(MAX_PAGES):
        payload, page_headers = _get_json(url, headers)
        for item in _items(payload, url):
            yield Repo(
                name=str(item.get("path_with_namespace", "")),
                visibility=str(item.get("visibility", "unknown")),
                url=str(item.get("web_url", "")),
            )
        next_url = _next_link(page_headers)
        if not next_url and page_headers.get("x-next-page"):
            next_url = _with_page(url, int(page_headers["x-next-page"]))
        if not next_url:
            return
        url = next_url
    raise ApiError(f"pagination exceeded {MAX_PAGES} pages")


def fetch_bitbucket(user: str, all_accessible: bool) -> Iterator[Repo]:
    """Репозитории workspace (Bitbucket Cloud); ``--all`` не нужен — список уже полный."""
    _ = all_accessible  # список репозиториев workspace уже полный
    api = (os.environ.get("BITBUCKET_API_URL") or "https://api.bitbucket.org/2.0").rstrip("/")
    headers = {"Accept": "application/json"}
    token = _env("BITBUCKET_TOKEN")
    if token:
        email = _env("BITBUCKET_EMAIL") or _env("BITBUCKET_USERNAME")
        if not email:
            raise ApiError(
                "BITBUCKET_TOKEN is set but BITBUCKET_EMAIL is missing "
                "(API tokens use HTTP Basic auth: e-mail + token)"
            )
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"

    url = f"{api}/repositories/{urllib.parse.quote(user)}?pagelen={PER_PAGE}&sort=name"
    for _ in range(MAX_PAGES):
        payload, _headers = _get_json(url, headers)
        if not isinstance(payload, dict):
            raise ApiError(f"unexpected response shape from {url}")
        for item in _items(payload.get("values", []), url):
            links = item.get("links")
            html = links.get("html") if isinstance(links, dict) else None
            yield Repo(
                name=str(item.get("full_name", "")),
                visibility="private" if item.get("is_private") else "public",
                url=str(html.get("href", "")) if isinstance(html, dict) else "",
            )
        next_url = payload.get("next")
        if not isinstance(next_url, str) or not next_url:
            return
        url = next_url
    raise ApiError(f"pagination exceeded {MAX_PAGES} pages")


FETCHERS = {
    "github": fetch_github,
    "gitlab": fetch_gitlab,
    "bitbucket": fetch_bitbucket,
}

HINTS = {
    "github": (
        "hint: private repos need GITHUB_TOKEN (classic PAT with `repo` scope, "
        "or fine-grained PAT with Metadata: read): https://github.com/settings/tokens"
    ),
    "gitlab": (
        "hint: private projects need GITLAB_TOKEN (PAT with `read_api` scope) "
        "and GITLAB_URL for self-hosted instances (default https://gitlab.com)"
    ),
    "bitbucket": (
        "hint: private repos need BITBUCKET_TOKEN (API token, scope "
        "read:repository:bitbucket) plus BITBUCKET_EMAIL: "
        "https://id.atlassian.com/manage-profile/security/api-tokens"
    ),
}


def _authenticated(platform: str) -> bool:
    variable = {
        "github": "GITHUB_TOKEN",
        "gitlab": "GITLAB_TOKEN",
        "bitbucket": "BITBUCKET_TOKEN",
    }[platform]
    return bool(_env(variable))


def _format_counts(repos: list[Repo]) -> str:
    counts = Counter(repo.visibility for repo in repos)
    order = ["public", "private", "internal"]
    ordered = [(label, counts.pop(label)) for label in order if label in counts]
    ordered.extend(sorted(counts.items()))
    return ", ".join(f"{label} {count}" for label, count in ordered)


def _print_table(platform: str, user: str, repos: list[Repo]) -> None:
    auth = "token" if _authenticated(platform) else "no token, public only"
    print(f"{platform}: {user} ({auth})")
    if not repos:
        print("  no repositories")
        return
    width = max(len(repo.name) for repo in repos)
    for repo in repos:
        print(f"  {repo.name:<{width}}  {repo.visibility}")
    print()
    print(f"Total: {len(repos)} ({_format_counts(repos)})")


def _build_json(platform: str, user: str, repos: list[Repo]) -> dict[str, object]:
    counts = Counter(repo.visibility for repo in repos)
    return {
        "platform": platform,
        "user": user,
        "authenticated": _authenticated(platform),
        "total": len(repos),
        "counts": dict(sorted(counts.items())),
        "repositories": [
            {"name": repo.name, "visibility": repo.visibility, "url": repo.url} for repo in repos
        ],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="git_repos_list.py",
        description="List repositories of one account on GitHub, GitLab or Bitbucket Cloud.",
        epilog="Settings come from .env (example in the module docstring) or the environment.",
    )
    parser.add_argument(
        "platform",
        choices=sorted(FETCHERS),
        help="hosting platform",
    )
    parser.add_argument(
        "--env-file",
        metavar="PATH",
        default=None,
        help="path to .env (default: ./.env, then .env next to the script)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="GitHub: add collaborator and org repos; GitLab: add group projects "
        "(requires a token). Ignored by Bitbucket.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    env_file, explicit = _resolve_env_file(args.env_file)
    try:
        load_env_file(env_file, explicit=explicit)
    except ApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    platform = args.platform
    user = _env("REPO_USER") or DEFAULT_USERNAME

    if args.all and platform == "bitbucket":
        print(
            "note: --all has no effect on Bitbucket (workspace listing is complete)",
            file=sys.stderr,
        )
    elif args.all and not _authenticated(platform):
        print(f"note: --all ignored on {platform} without a token", file=sys.stderr)

    try:
        repos = sorted(
            FETCHERS[platform](user, args.all),
            key=lambda repo: repo.name.casefold(),
        )
    except ApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(HINTS[platform], file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_build_json(platform, user, repos), ensure_ascii=False, indent=2))
    else:
        _print_table(platform, user, repos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
