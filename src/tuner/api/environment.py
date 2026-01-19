"""
环境管理模块
支持多环境切换（test/staging/production）
"""

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel


class EnvironmentType(str, Enum):
    """环境类型枚举"""

    TEST = "test"  # 测试环境
    STAGING = "staging"  # 预发布环境
    PRODUCTION = "prod"  # 生产环境


class Environment(BaseModel):
    """环境配置"""

    name: EnvironmentType
    url_prefix: str  # 如 https://test-api.example.com
    variables: dict[str, str] = {}  # 环境变量


class EnvironmentManager:
    """环境管理器（单例模式）"""

    _environments: ClassVar[dict[EnvironmentType, Environment]] = {}
    _current: ClassVar[EnvironmentType] = EnvironmentType.TEST

    @classmethod
    def register(cls, env: Environment) -> None:
        """注册环境配置"""
        cls._environments[env.name] = env

    @classmethod
    def switch(cls, env_type: EnvironmentType) -> None:
        """切换当前环境"""
        if env_type not in cls._environments:
            msg = f"环境 {env_type} 未注册，请先调用 register() 注册"
            raise ValueError(msg)
        cls._current = env_type

    @classmethod
    def get_current(cls) -> Environment | None:
        """获取当前环境"""
        return cls._environments.get(cls._current)

    @classmethod
    def get_url_prefix(cls) -> str:
        """获取当前环境的 URL 前缀"""
        env = cls.get_current()
        return env.url_prefix if env else ""

    @classmethod
    def get_variable(cls, name: str, default: str = "") -> str:
        """获取当前环境的变量"""
        env = cls.get_current()
        if env:
            return env.variables.get(name, default)
        return default

    @classmethod
    def reset(cls) -> None:
        """重置环境管理器（用于测试）"""
        cls._environments.clear()
        cls._current = EnvironmentType.TEST
