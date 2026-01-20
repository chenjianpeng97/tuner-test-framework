"""Playwright 截图示例：复用 DDT 的 token 进入页面并截图。

说明：
- 这个系统的登录态不在 localStorage，而是在 Cookie + sessionStorage 中。
- 因此仅给页面请求加 Authorization 头并不够，前端路由仍会重定向到登录页。
- 需要把 token 写入 Cookie，同时构造 sessionStorage 的 sessionObj。
"""

from __future__ import annotations

from pathlib import Path

from tuner.ui import capture_page_screenshot

# 假设这些值来自本次 DDT（或 API 测试的返回结果）
NICKNAME = "李开心"
USERNAME = "Happy.li@argonmedical.com"
TOKEN = "your_token_from_ddt"
TARGET_URL = "http://116.204.94.77:8524/auth/distributorRelation"

result = capture_page_screenshot(
    url=TARGET_URL,
    token=TOKEN,
    nickname=NICKNAME,
    output_dir=Path("screenshots"),
    # 1) 这类系统前端会从 sessionStorage 读 sessionObj
    #    这里复刻手工登录后的结构（只要字段齐全即可）
    extra_session_storage={
        "sessionObj": (
            f'{{"url":"/login","data":"{{\\"username\\":\\"{USERNAME}\\",'
            f'\\"password\\":\\"123456\\",\\"systemId\\":1}}",'
            '"time":0}'
        ),
    },
    # 2) Cookie 中需要 Admin-Token-autho，前端会用它判断是否登录
    token_cookie_name="Admin-Token-autho",
    # 3) Header 仍可保留，便于后续 API 请求（但仅 header 不能放行页面）
    token_storage_key="token",
    include_auth_header=True,
    browser_type="chromium",
    headless=True,
)

print(f"Screenshot saved: {result.path}")
