"""Unit tests for Playwright UI helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from tuner.ui import (
    build_screenshot_path,
    capture_page_screenshot,
    core,
    sanitize_filename,
)


def test_sanitize_filename_replaces_invalid_chars() -> None:
    value = "A/B:C*D?E|F"
    assert sanitize_filename(value) == "A_B_C_D_E_F"


def test_build_screenshot_path_uses_description_and_timestamp(tmp_path) -> None:
    now = datetime(2026, 1, 19, 8, 9, 10, tzinfo=UTC)
    path = build_screenshot_path(tmp_path, "测试 User", now=now)
    assert path.parent == tmp_path
    assert path.name == "测试_User_20260119_080910.png"


def test_build_screenshot_path_requires_tzinfo(tmp_path) -> None:
    now = datetime(2026, 1, 19, 8, 9, 10)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_screenshot_path(tmp_path, "nick", now=now)


def test_capture_page_screenshot_calls_playwright(monkeypatch, tmp_path) -> None:
    mock_page = MagicMock()
    mock_context = MagicMock()
    mock_browser = MagicMock()
    mock_playwright = MagicMock()

    mock_context.new_page.return_value = mock_page
    mock_browser.new_context.return_value = mock_context
    mock_playwright.chromium.launch.return_value = mock_browser

    manager = MagicMock()
    manager.__enter__.return_value = mock_playwright
    manager.__exit__.return_value = None

    monkeypatch.setattr(core, "sync_playwright", MagicMock(return_value=manager))

    now = datetime(2026, 1, 19, 8, 9, 10, tzinfo=UTC)
    result = capture_page_screenshot(
        url="https://example.com/app",
        token="token-123",
        description="测试",
        output_dir=tmp_path,
        token_storage_key="token",
        now=now,
        httpx_client={"sessionid": "sess-abc"},
    )

    mock_context.add_init_script.assert_called_once()
    mock_context.add_cookies.assert_called_once()
    script = mock_context.add_init_script.call_args.args[0]
    assert "localStorage.setItem" in script
    assert "token" in script
    assert "token-123" in script

    mock_page.goto.assert_called_once_with(
        "https://example.com/app",
        wait_until="networkidle",
        timeout=30_000,
    )
    mock_page.screenshot.assert_called_once()
    assert result.path.name == "测试_20260119_080910.png"
