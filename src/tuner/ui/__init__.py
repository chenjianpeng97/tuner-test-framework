"""UI automation helpers based on Playwright."""

from tuner.ui.auth_handler import (
    build_playwright_cookies_from_httpx,
    build_storage_init_script,
)
from tuner.ui.core import (
    BrowserSession,
    PageSession,
    ScreenshotResult,
    build_screenshot_path,
    capture_page_screenshot,
    sanitize_filename,
)

__all__ = [
    "BrowserSession",
    "PageSession",
    "ScreenshotResult",
    "build_playwright_cookies_from_httpx",
    "build_screenshot_path",
    "build_storage_init_script",
    "capture_page_screenshot",
    "sanitize_filename",
]
