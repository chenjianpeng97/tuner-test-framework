"""Core Playwright browser/page wrappers.

This module provides low-coupling primitives to manage browser lifecycle and
page operations. Higher-level helpers (e.g. screenshot) build upon these.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from tuner.ui.auth_handler import (
    build_playwright_cookies_from_httpx,
    build_storage_init_script,
)
from tuner.util.log import get_logger

try:  # pragma: no cover - runtime dependency
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except Exception:  # pragma: no cover - allow importing without playwright installed
    Browser = BrowserContext = Page = None  # type: ignore[assignment]
    sync_playwright = None

log = get_logger("ui.playwright.core")

BrowserType = Literal["chromium", "firefox", "webkit"]
WaitUntil = Literal["load", "domcontentloaded", "networkidle"]


@dataclass(frozen=True)
class ScreenshotResult:
    path: Path
    url: str
    description: str
    timestamp: datetime


def sanitize_filename(value: str) -> str:
    """Sanitize value for safe filename usage (keeps unicode)."""

    cleaned = value.strip()
    cleaned = re.sub(r"[<>:\"/\\|?*]+", "_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "anonymous"


def build_screenshot_path(
    output_dir: str | Path,
    description: str,
    *,
    now: datetime | None = None,
) -> Path:
    """Build a screenshot path using description and UTC timestamp."""

    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        msg = "now must be timezone-aware"
        raise ValueError(msg)

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    ts = timestamp.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(description)}_{ts}.png"
    return directory / filename


def _build_auth_headers(
    token: str,
    *,
    include_auth_header: bool,
    auth_header_prefix: str,
    extra_headers: dict[str, str] | None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_auth_header:
        prefix = auth_header_prefix.strip()
        headers["Authorization"] = f"{prefix} {token}" if prefix else token
    if extra_headers:
        headers.update(extra_headers)
    return headers


@dataclass
class BrowserSession:
    browser_type: BrowserType = "chromium"
    headless: bool = True
    viewport: dict[str, int] | None = None
    extra_http_headers: dict[str, str] | None = None
    init_script: str | None = None
    cookies: list[dict[str, object]] | None = None

    _manager: Any | None = None
    _playwright: Any | None = None
    _browser: Browser | None = None
    _context: BrowserContext | None = None

    def __enter__(self) -> BrowserSession:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            msg = "BrowserSession is not started"
            raise RuntimeError(msg)
        return self._context

    def start(self) -> None:
        if sync_playwright is None:  # pragma: no cover - runtime safeguard
            msg = "playwright is not installed; run 'playwright install' after pip install"
            raise RuntimeError(msg)

        self._manager = sync_playwright()
        self._playwright = self._manager.__enter__()
        launcher = getattr(self._playwright, self.browser_type)
        self._browser = launcher.launch(headless=self.headless)
        self._context = self._browser.new_context(
            extra_http_headers=self.extra_http_headers or None
        )
        if self.viewport:
            self._context.set_viewport_size(self.viewport)
        if self.init_script:
            self._context.add_init_script(self.init_script)
        if self.cookies:
            self._context.add_cookies(self.cookies)

    def new_page(
        self,
        *,
        debug_requests: bool = False,
        target_url: str | None = None,
    ) -> PageSession:
        page = self.context.new_page()
        session = PageSession(page=page, context=self.context)
        if debug_requests:
            session.enable_request_logging(target_url=target_url)
        return session

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._manager is not None:
            try:
                self._manager.__exit__(None, None, None)
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None
        self._manager = None


@dataclass
class PageSession:
    page: Any
    context: Any

    def goto(
        self,
        url: str,
        *,
        wait_until: WaitUntil = "networkidle",
        timeout_ms: int = 30_000,
    ):
        return self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)

    def click(self, selector: str, **kwargs: Any) -> None:
        self.page.click(selector, **kwargs)

    def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        self.page.fill(selector, value, **kwargs)

    def wait_for_selector(self, selector: str, **kwargs: Any):
        return self.page.wait_for_selector(selector, **kwargs)

    def evaluate(self, expression: str, *args: Any):
        return self.page.evaluate(expression, *args)

    def screenshot(self, *, path, full_page: bool = True) -> None:
        self.page.screenshot(path=str(path), full_page=full_page)

    def enable_request_logging(self, *, target_url: str | None = None) -> None:
        host = urlparse(target_url).hostname if target_url else None

        def _log_request(request):
            if host and urlparse(request.url).hostname == host:
                log.info(
                    "Request: {method} {request_url} headers={headers}",
                    method=request.method,
                    request_url=request.url,
                    headers=request.headers,
                )

        def _log_response(response):
            if host and urlparse(response.url).hostname == host:
                log.info(
                    "Response: {status} {response_url}",
                    status=response.status,
                    response_url=response.url,
                )

        self.page.on("request", _log_request)
        self.page.on("response", _log_response)

    def log_navigation_details(self, *, response: Any, screenshot_path) -> None:
        log.info(
            "Navigation result: status={status} final_url={final_url}",
            status=getattr(response, "status", None),
            final_url=self.page.url,
        )
        if response is not None:
            log.info("Navigation response headers: {headers}", headers=response.headers)
        local_storage = self.page.evaluate("() => ({...localStorage})")
        session_storage = self.page.evaluate("() => ({...sessionStorage})")
        log.info("localStorage snapshot: {data}", data=local_storage)
        log.info("sessionStorage snapshot: {data}", data=session_storage)
        cookies = self.context.cookies()
        log.info("cookie snapshot: {data}", data=cookies)
        if "/login" in self.page.url:
            html_path = screenshot_path.with_suffix(".login.html")
            html_path.write_text(self.page.content(), encoding="utf-8")
            log.info("Login page HTML saved: {path}", path=html_path)


def capture_page_screenshot(
    *,
    url: str,
    token: str,
    description: str,
    output_dir: str | Path = "screenshots",
    token_storage_key: str = "token",
    extra_local_storage: dict[str, str] | None = None,
    extra_session_storage: dict[str, str] | None = None,
    include_auth_header: bool = False,
    auth_header_prefix: str = "Bearer",
    extra_headers: dict[str, str] | None = None,
    wait_until: WaitUntil = "networkidle",
    full_page: bool = True,
    browser_type: BrowserType = "chromium",
    headless: bool = True,
    viewport: dict[str, int] | None = None,
    timeout_ms: int = 30_000,
    now: datetime | None = None,
    debug_requests: bool = False,
    token_cookie_name: str | None = None,
    cookie_domain: str | None = None,
    cookie_path: str = "/",
    httpx_client: object | None = None,
    playwright_cookies: list[dict[str, object]] | None = None,
    include_subdomains: bool = True,
    include_expired_cookies: bool = False,
) -> ScreenshotResult:
    """Open the page with token and capture a screenshot."""

    if not token:
        msg = "token must not be empty"
        raise ValueError(msg)

    local_storage = {token_storage_key: token}
    if extra_local_storage:
        local_storage.update(extra_local_storage)

    init_script = build_storage_init_script(
        local_storage=local_storage,
        session_storage=extra_session_storage,
    )
    headers = _build_auth_headers(
        token,
        include_auth_header=include_auth_header,
        auth_header_prefix=auth_header_prefix,
        extra_headers=extra_headers,
    )

    timestamp = now or datetime.now(UTC)
    screenshot_path = build_screenshot_path(output_dir, description, now=timestamp)

    log.info(
        "Capturing screenshot for {description} at {url}",
        description=description,
        url=url,
    )

    cookies_to_add: list[dict[str, object]] = []
    if httpx_client is not None:
        try:
            import httpx  # local import to avoid hard dependency in type checks

            if not isinstance(httpx_client, (httpx.Client, httpx.Cookies, dict)):
                msg = "httpx_client must be httpx.Client, httpx.Cookies, or dict"
                raise TypeError(msg)
        except Exception:
            msg = "httpx_client must be httpx.Client, httpx.Cookies, or dict"
            raise TypeError(msg)

        cookies_to_add.extend(
            build_playwright_cookies_from_httpx(
                httpx_client,
                url,
                cookie_domain=cookie_domain,
                include_subdomains=include_subdomains,
                include_expired=include_expired_cookies,
            )
        )
    if playwright_cookies:
        cookies_to_add.extend(playwright_cookies)
    if token_cookie_name:
        parsed = urlparse(url)
        domain = cookie_domain or parsed.hostname
        if domain is None:
            msg = "Failed to determine cookie domain from url"
            raise ValueError(msg)
        cookies_to_add.append({
            "name": token_cookie_name,
            "value": token,
            "domain": domain,
            "path": cookie_path,
            "secure": url.startswith("https"),
            "httpOnly": False,
            "sameSite": "Lax",
        })

    with BrowserSession(
        browser_type=browser_type,
        headless=headless,
        viewport=viewport,
        extra_http_headers=headers or None,
        init_script=init_script,
        cookies=cookies_to_add or None,
    ) as session:
        page = session.new_page(debug_requests=debug_requests, target_url=url)
        response = page.goto(url, wait_until=wait_until, timeout_ms=timeout_ms)

        if debug_requests:
            page.log_navigation_details(
                response=response, screenshot_path=screenshot_path
            )

        page.screenshot(path=screenshot_path, full_page=full_page)

        return ScreenshotResult(
            path=screenshot_path,
            url=url,
            description=description,
            timestamp=timestamp,
        )
