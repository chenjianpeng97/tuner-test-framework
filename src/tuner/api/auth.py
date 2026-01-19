"""
认证管理模块
支持 Bearer Token、API Key 等认证方式（第一版重点支持 Bearer Token）
"""

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class AuthType(str, Enum):
    """认证类型枚举"""

    NONE = "none"
    BEARER_TOKEN = "bearer"
    API_KEY = "apikey"
    BASIC = "basic"


class Auth(BaseModel, ABC):
    """认证基类"""

    type: AuthType = AuthType.NONE

    @abstractmethod
    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """将认证信息应用到请求头"""


class NoAuth(Auth):
    """无认证"""

    type: AuthType = AuthType.NONE

    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return headers


class BearerTokenAuth(Auth):
    """Bearer Token 认证（第一版重点支持）"""

    type: AuthType = AuthType.BEARER_TOKEN
    token: str
    prefix: str = "Bearer"  # 可自定义前缀

    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        headers = {**headers}
        headers["Authorization"] = f"{self.prefix} {self.token}"
        return headers


class ApiKeyAuth(Auth):
    """API Key 认证（预留）"""

    type: AuthType = AuthType.API_KEY
    key: str  # Header 名称或 Query 参数名
    value: str  # API Key 值
    add_to: str = "header"  # header 或 query

    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        if self.add_to == "header":
            headers = {**headers}
            headers[self.key] = self.value
        return headers


class BasicAuth(Auth):
    """Basic 认证（预留）"""

    type: AuthType = AuthType.BASIC
    username: str
    password: str

    def apply_to_headers(self, headers: dict[str, str]) -> dict[str, str]:
        import base64

        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers = {**headers}
        headers["Authorization"] = f"Basic {encoded}"
        return headers
