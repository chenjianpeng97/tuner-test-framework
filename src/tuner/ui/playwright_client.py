"""Playwright UI helpers for post-test automation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from http.cookiejar import domain_match
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from tuner.util.log import get_logger

try:  # pragma: no cover - runtime dependency
    from playwright.sync_api import Browser, BrowserContext, sync_playwright
except Exception:  # pragma: no cover - allow importing without playwright installed
    Browser = BrowserContext = None  # type: ignore[assignment]
    sync_playwright = None

log = get_logger("ui.playwright")

BrowserType = Literal["chromium", "firefox", "webkit"]
WaitUntil = Literal["load", "domcontentloaded", "networkidle"]
SameSite = Literal["Lax", "Strict", "None"]


@dataclass(frozen=True)
class ScreenshotResult:
    path: Path
    url: str
    description: str
    timestamp: datetime


def sanitize_filename(value: str) -> str:
    """Sanitize value for safe filename usage (keeps unicode)."""

    # 清理首尾空白，避免出现不可见字符
    cleaned = value.strip()
    # Windows/通用文件名非法字符替换为下划线
    cleaned = re.sub(r"[<>:\"/\\|?*]+", "_", cleaned)
    # 连续空白压缩为单个下划线，便于阅读与排序
    cleaned = re.sub(r"\s+", "_", cleaned)
    # 兜底：如果为空则给一个默认名
    return cleaned or "anonymous"


def build_screenshot_path(
    output_dir: str | Path,
    description: str,
    *,
    now: datetime | None = None,
) -> Path:
    """Build a screenshot path using description and UTC timestamp."""

    # 使用 UTC 时间戳，便于跨时区比对与排序
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        msg = "now must be timezone-aware"
        raise ValueError(msg)

    # 确保输出目录存在
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    # 文件名包含昵称 + UTC 时间
    ts = timestamp.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(description)}_{ts}.png"
    return directory / filename


def build_storage_init_script(
    *,
    local_storage: dict[str, str] | None = None,
    session_storage: dict[str, str] | None = None,
) -> str:
    """Build a Playwright init script to seed local/session storage."""

    # 生成一个在页面加载前执行的 JS 脚本
    lines = ["() => {", "  try {"]
    if local_storage:
        for key, value in local_storage.items():
            # 使用 JSON 转义，避免引号/特殊字符导致脚本报错
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
    # 捕获异常，避免脚本失败影响页面加载
    lines.extend([
        "  } catch (e) {",
        "    console.warn('storage init failed', e);",
        "  }",
        "}",
    ])
    return "\n".join(lines)


def _normalize_samesite(value: str | None) -> SameSite | None:
    # 统一 SameSite 的大小写与合法值
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
    # host/domain 为空时不做限制（保持原有行为）
    if not host or not domain:
        return True
    # 是否允许子域匹配
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

    # 从 URL 解析出默认域名
    parsed = urlparse(url)
    host = parsed.hostname
    default_domain = cookie_domain or host

    if isinstance(cookies_source, dict):
        # dict 形式无法推断域名时必须显式提供
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
        # 跳过过期 cookie（除非允许）
        if cookie.is_expired() and not include_expired:
            continue

        # 确认 cookie 的域是否与当前访问域匹配
        domain = cookie_domain or cookie.domain or host
        if not _domain_matches(host, domain, include_subdomains=include_subdomains):
            continue
        if domain is None:
            continue

        rest = getattr(cookie, "rest", {})
        raw_samesite = rest.get("samesite") or rest.get("SameSite")
        samesite = _normalize_samesite(raw_samesite)

        # 组装 Playwright 期望的 cookie 字段
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


def _build_auth_headers(
    token: str,
    *,
    include_auth_header: bool,
    auth_header_prefix: str,
    extra_headers: dict[str, str] | None,
) -> dict[str, str]:
    # 组装请求头，通常用于设置 Authorization
    headers: dict[str, str] = {}
    if include_auth_header:
        prefix = auth_header_prefix.strip()
        headers["Authorization"] = f"{prefix} {token}" if prefix else token

    # 合并用户传入的额外 header
    if extra_headers:
        headers.update(extra_headers)

    return headers


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
    """Open the page with token and capture a screenshot.

    Args:
        url: Target page URL.
        token: Token from API DDT run.
        description: description used in DDT; used in screenshot filename.
        output_dir: Directory to store screenshots.
        token_storage_key: localStorage key for the token.
        extra_local_storage: Extra localStorage entries to set before page load.
        extra_session_storage: Extra sessionStorage entries to set before page load.
        include_auth_header: Whether to send Authorization header.
        auth_header_prefix: Prefix for Authorization header (e.g., "Bearer").
        extra_headers: Additional headers for the browser context.
        wait_until: Playwright wait condition for page navigation.
        full_page: Capture full-page screenshot.
        browser_type: Browser engine to use.
        headless: Launch browser in headless mode.
        viewport: Optional viewport size, e.g. {"width": 1280, "height": 720}.
        timeout_ms: Navigation timeout in milliseconds.
        now: Optional fixed time for deterministic filenames.
        debug_requests: Enable verbose request/response logging.
        token_cookie_name: If set, inject token as a cookie with this name.
        cookie_domain: Cookie domain override (defaults to page hostname).
        cookie_path: Cookie path.
        httpx_client: httpx Client/Cookies or raw cookie dict to inject.
        playwright_cookies: Pre-built Playwright cookie dicts to inject.
        include_subdomains: Whether to include subdomain cookies.
        include_expired_cookies: Whether to include expired cookies.
    """

    if not token:
        msg = "token must not be empty"
        raise ValueError(msg)

    if sync_playwright is None:  # pragma: no cover - runtime safeguard
        msg = "playwright is not installed; run 'playwright install' after pip install"
        raise RuntimeError(msg)

    # 将 token 写入 localStorage，便于前端在加载时读取
    local_storage = {token_storage_key: token}
    if extra_local_storage:
        local_storage.update(extra_local_storage)

    # 初始化脚本在页面加载前执行
    init_script = build_storage_init_script(
        local_storage=local_storage,
        session_storage=extra_session_storage,
    )
    # 需要的话通过请求头注入 Authorization
    headers = _build_auth_headers(
        token,
        include_auth_header=include_auth_header,
        auth_header_prefix=auth_header_prefix,
        extra_headers=extra_headers,
    )

    # 截图文件路径（包含时间戳）
    timestamp = now or datetime.now(UTC)
    screenshot_path = build_screenshot_path(output_dir, description, now=timestamp)

    log.info(
        "Capturing screenshot for {description} at {url}",
        description=description,
        url=url,
    )

    # 启动 Playwright（同步 API）
    playwright = sync_playwright()
    browser: Browser | None = None
    context: BrowserContext | None = None

    try:
        # 进入 Playwright 上下文
        pw = playwright.__enter__()
        browser_launcher = getattr(pw, browser_type)
        # 启动指定浏览器引擎
        browser = browser_launcher.launch(headless=headless)
        # 创建上下文并附加请求头
        context = browser.new_context(extra_http_headers=headers or None)
        if viewport:
            context.set_viewport_size(viewport)
        # 注入 storage 脚本
        context.add_init_script(init_script)
        cookies_to_add: list[dict[str, object]] = []
        if httpx_client is not None:
            if not isinstance(httpx_client, (httpx.Client, httpx.Cookies, dict)):
                msg = "httpx_client must be httpx.Client, httpx.Cookies, or dict"
                raise TypeError(msg)
            # 从 httpx cookies 转换为 Playwright cookie
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
            # 直接添加预构建的 Playwright cookie
            cookies_to_add.extend(playwright_cookies)
        if token_cookie_name:
            parsed = urlparse(url)
            domain = cookie_domain or parsed.hostname
            if domain is None:
                msg = "Failed to determine cookie domain from url"
                raise ValueError(msg)
            # 可选：将 token 作为 cookie 注入
            cookies_to_add.append({
                "name": token_cookie_name,
                "value": token,
                "domain": domain,
                "path": cookie_path,
                "secure": parsed.scheme == "https",
                "httpOnly": False,
                "sameSite": "Lax",
            })
        if cookies_to_add:
            # 统一写入到浏览器上下文
            context.add_cookies(cookies_to_add)

        # 打开新页面
        page = context.new_page()
        if debug_requests:
            parsed = urlparse(url)
            host = parsed.hostname

            def _log_request(request):
                # 仅打印目标域名下的请求，避免噪音
                if host and urlparse(request.url).hostname == host:
                    log.info(
                        "Request: {method} {request_url} headers={headers}",
                        method=request.method,
                        request_url=request.url,
                        headers=request.headers,
                    )

            def _log_response(response):
                # 仅打印目标域名下的响应
                if host and urlparse(response.url).hostname == host:
                    log.info(
                        "Response: {status} {response_url}",
                        status=response.status,
                        response_url=response.url,
                    )

            page.on("request", _log_request)
            page.on("response", _log_response)

        # 导航到页面并等待指定的加载状态
        response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        if debug_requests:
            # 记录导航结果与存储快照，便于排查未登录等问题
            log.info(
                "Navigation result: status={status} final_url={final_url}",
                status=getattr(response, "status", None),
                final_url=page.url,
            )
            if response is not None:
                log.info(
                    "Navigation response headers: {headers}",
                    headers=response.headers,
                )
            local_storage = page.evaluate("() => ({...localStorage})")
            session_storage = page.evaluate("() => ({...sessionStorage})")
            log.info("localStorage snapshot: {data}", data=local_storage)
            log.info("sessionStorage snapshot: {data}", data=session_storage)
            cookies = context.cookies()
            log.info("cookie snapshot: {data}", data=cookies)
            if "/login" in page.url:
                # 如果被重定向到登录页，额外保存 HTML 便于分析
                html_path = screenshot_path.with_suffix(".login.html")
                html_path.write_text(page.content(), encoding="utf-8")
                log.info("Login page HTML saved: {path}", path=html_path)
        # 截图保存
        page.screenshot(path=str(screenshot_path), full_page=full_page)

        return ScreenshotResult(
            path=screenshot_path,
            url=url,
            description=description,
            timestamp=timestamp,
        )
    finally:
        if context is not None:
            try:
                # 关闭上下文
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                # 关闭浏览器
                browser.close()
            except Exception:
                pass
        # 退出 Playwright 上下文
        playwright.__exit__(None, None, None)
