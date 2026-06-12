from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static


register = template.Library()

DEFAULT_VERSIONED_EXTENSIONS = (
    ".css",
    ".js",
    ".mjs",
    ".json",
    ".map",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
)

DEPLOY_VERSION_ENV_NAMES = (
    "STATIC_VERSION",
    "RELEASE_VERSION",
    "SOURCE_VERSION",
    "GIT_COMMIT",
    "COMMIT_SHA",
    "RENDER_GIT_COMMIT",
    "VERCEL_GIT_COMMIT_SHA",
)


def _as_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _configured_version() -> str:
    value = getattr(settings, "STATIC_VERSION", "")
    if value:
        return str(value).strip()

    for name in DEPLOY_VERSION_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return ""


def _clean_static_path(path: str) -> str:
    parts = urlsplit(str(path))
    clean = parts.path.lstrip("/")
    static_url_path = urlsplit(getattr(settings, "STATIC_URL", "")).path.lstrip("/")
    if static_url_path and clean.startswith(static_url_path):
        clean = clean[len(static_url_path):].lstrip("/")
    return clean


def _is_absolute_url(path: str) -> bool:
    parts = urlsplit(str(path))
    return parts.scheme in {"http", "https", "data"} or str(path).startswith("//")


def _versioned_extensions() -> tuple[str, ...]:
    extensions = getattr(settings, "STATIC_VERSION_EXTENSIONS", DEFAULT_VERSIONED_EXTENSIONS)
    return tuple(str(ext).lower() for ext in extensions)


def _should_version(path: str) -> bool:
    if not _as_bool(getattr(settings, "STATIC_VERSION_QUERY", True), default=True):
        return False
    if _is_absolute_url(path):
        return False
    clean_path = _clean_static_path(path).lower()
    return clean_path.endswith(_versioned_extensions())


def _append_version(url: str, version: str) -> str:
    param = getattr(settings, "STATIC_VERSION_PARAM", "v") or "v"
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[str(param)] = str(version)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _resolve_static_url(path: str) -> str:
    try:
        return static(path)
    except Exception:
        static_url = getattr(settings, "STATIC_URL", "/static/")
        return f"{static_url.rstrip('/')}/{str(path).lstrip('/')}"


def _find_static_file(path: str) -> Path | None:
    clean_path = _clean_static_path(path)
    if not clean_path:
        return None

    found = finders.find(clean_path)
    if isinstance(found, (list, tuple)):
        found = found[0] if found else None
    return Path(found) if found else None


@lru_cache(maxsize=2048)
def _content_hash(file_path: str, mtime_ns: int, size: int) -> str:
    digest = hashlib.sha256()
    path = Path(file_path)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 128), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _file_version(path: str) -> str:
    configured = _configured_version()
    found = _find_static_file(path)
    if not found:
        return configured

    try:
        stat = found.stat()
        digest = _content_hash(str(found), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return configured

    return f"{digest}-{stat.st_size}" if digest else configured


@register.simple_tag
def version_static(path: str) -> str:
    """
    Return a static URL with deterministic cache busting.

    Django's ManifestStaticFilesStorage still provides hashed filenames after
    collectstatic. This tag adds a content-based query version as a strong
    fallback for development, missed collectstatic runs, and aggressive caches.
    """
    raw_path = str(path)
    if _is_absolute_url(raw_path):
        return raw_path

    url = _resolve_static_url(raw_path)

    if not _should_version(raw_path):
        return url

    version = _file_version(raw_path)
    return _append_version(url, version) if version else url


@register.simple_tag
def vstatic(path: str) -> str:
    return version_static(path)


@register.filter(name="version_static")
def version_static_filter(path: str) -> str:
    return version_static(path)
