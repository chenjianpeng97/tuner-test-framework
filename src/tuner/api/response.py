"""
API 响应封装模块
"""

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    """API 响应封装"""

    status_code: int
    headers: dict[str, str]
    cookies: dict[str, str]
    body: Any
    elapsed: float  # 响应时间（秒）
    raw_text: str = ""  # 原始响应文本

    def json(self) -> dict[str, Any]:
        """获取 JSON 响应"""
        if isinstance(self.body, dict):
            return self.body
        return {}

    def is_success(self) -> bool:
        """是否成功响应 (2xx)"""
        return 200 <= self.status_code < 300

    def is_client_error(self) -> bool:
        """是否客户端错误 (4xx)"""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """是否服务端错误 (5xx)"""
        return 500 <= self.status_code < 600
