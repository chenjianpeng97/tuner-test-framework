"""UI automation helpers based on Playwright."""

from tuner.ui.playwright_client import (
    ScreenshotResult,
    build_playwright_cookies_from_httpx,
    build_screenshot_path,
    build_storage_init_script,
    capture_page_screenshot,
    sanitize_filename,
)

__all__ = [
    "ScreenshotResult",
    "build_playwright_cookies_from_httpx",
    "build_screenshot_path",
    "build_storage_init_script",
    "capture_page_screenshot",
    "sanitize_filename",
]
