"""Playwright auth/session helpers (storage + cookies)."""

from __future__ import annotations

import json
from http.cookiejar import domain_match
from typing import Literal
from urllib.parse import urlparse

import httpx

SameSite = Literal["Lax", "Strict", "None"]


def build_storage_init_script(
    *,
    local_storage: dict[str, str] | None = None,
    session_storage: dict[str, str] | None = None,
) -> str:
    """Build a Playwright init script to seed local/session storage."""

    lines = ["() => {", "  try {"]
    if local_storage:
        for key, value in local_storage.items():
            key_json = json.dumps(str(key), ensure_ascii=False)
            value_json = json.dumps(str(value), ensure_ascii=False)
            lines.append(f"    window.localStorage.setItem({key_json}, {value_json});")
    if session_storage:
        for key, value in session_storage.items():
            key_json = json.dumps(str(key), ensure_ascii=False)
            value_json = json.dumps(str(value), ensure_ascii=False)
            lines.append(
                f"    window.sessionStorage.setItem({key_json}, {value_json});"
            )
    lines.extend([
        "  } catch (e) {",
        "    console.warn('storage init failed', e);",
        "  }",
        "}",
    ])
    return "\n".join(lines)


def _normalize_samesite(value: str | None) -> SameSite | None:
    if not value:
        return None
    normalized = str(value).strip().lower()
    if normalized == "lax":
        return "Lax"
    if normalized == "strict":
        return "Strict"
    if normalized == "none":
        return "None"
    return None


def _domain_matches(
    host: str | None, domain: str | None, *, include_subdomains: bool
) -> bool:
    if not host or not domain:
        return True
    if include_subdomains:
        return domain_match(host, domain)
    return host == domain.lstrip(".")


def build_playwright_cookies_from_httpx(
    cookies_source: httpx.Client | httpx.Cookies | dict[str, str],
    url: str,
    *,
    cookie_domain: str | None = None,
    include_subdomains: bool = True,
    include_expired: bool = False,
) -> list[dict[str, object]]:
    """Convert httpx cookies (or a plain dict) into Playwright cookie dicts."""

    parsed = urlparse(url)
    host = parsed.hostname
    default_domain = cookie_domain or host

    if isinstance(cookies_source, dict):
        if not default_domain:
            msg = "cookie_domain is required when url has no hostname"
            raise ValueError(msg)
        return [
            {
                "name": name,
                "value": value,
                "domain": default_domain,
                "path": "/",
                "secure": parsed.scheme == "https",
                "httpOnly": False,
                "sameSite": "Lax",
            }
            for name, value in cookies_source.items()
        ]

    jar = (
        cookies_source.cookies.jar
        if isinstance(cookies_source, httpx.Client)
        else cookies_source.jar
    )

    cookies: list[dict[str, object]] = []
    for cookie in jar:
        if cookie.is_expired() and not include_expired:
            continue

        domain = cookie_domain or cookie.domain or host
        if not _domain_matches(host, domain, include_subdomains=include_subdomains):
            continue
        if domain is None:
            continue

        rest = getattr(cookie, "rest", {})
        raw_samesite = rest.get("samesite") or rest.get("SameSite")
        samesite = _normalize_samesite(raw_samesite)

        payload: dict[str, object] = {
            "name": cookie.name,
            "value": cookie.value,
            "domain": domain,
            "path": cookie.path or "/",
            "secure": cookie.secure,
            "httpOnly": cookie.has_nonstandard_attr("HttpOnly"),
        }
        if cookie.expires:
            payload["expires"] = cookie.expires
        if samesite:
            payload["sameSite"] = samesite
        cookies.append(payload)

    return cookies
