"""
APIModel 单元测试：环境切换与认证
使用 httpbin.org 作为测试服务器
"""

import pytest

from tuner.api.auth import BasicAuth, BearerTokenAuth
from tuner.api.base import APIExecutor, APIModel
from tuner.api.environment import Environment, EnvironmentManager, EnvironmentType


@pytest.fixture(autouse=True)
def setup_envs():
    """每个测试前重置并配置多个环境"""
    EnvironmentManager.reset()
    EnvironmentManager.register(
        Environment(name=EnvironmentType.TEST, url_prefix="https://httpbin.org")
    )
    EnvironmentManager.register(
        Environment(
            name=EnvironmentType.STAGING,
            url_prefix="https://httpbin.org",
            variables={"env_name": "staging"},
        )
    )
    EnvironmentManager.switch(EnvironmentType.TEST)
    yield
    EnvironmentManager.reset()


class TestEnvironmentManagement:
    """环境管理测试"""

    def test_env_register_and_switch(self):
        """测试环境注册和切换"""
        assert EnvironmentManager.get_url_prefix() == "https://httpbin.org"

        EnvironmentManager.switch(EnvironmentType.STAGING)
        assert EnvironmentManager.get_variable("env_name") == "staging"

    def test_env_switch_to_unregistered(self):
        """测试切换到未注册环境"""
        with pytest.raises(ValueError, match="未注册"):
            EnvironmentManager.switch(EnvironmentType.PRODUCTION)

    def test_api_uses_current_env(self):
        """测试 API 使用当前环境的 URL 前缀"""
        api = APIModel(
            name="环境测试",
            method="GET",
            url="/get",
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            # httpbin.org 返回请求的 URL
            assert "httpbin.org" in response.body.get("url", "")

    def test_api_url_prefix_override_env(self):
        """测试 API 的 url_prefix 覆盖环境配置"""
        api = APIModel(
            name="URL 前缀覆盖测试",
            method="GET",
            url="/get",
            url_prefix="https://httpbin.org",  # 显式指定
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200


class TestAuthMethods:
    """认证方式测试"""

    def test_bearer_token_auth(self):
        """测试 Bearer Token 认证"""
        api = APIModel(
            name="Bearer 测试",
            method="GET",
            url="/headers",
            auth=BearerTokenAuth(token="test-token-123"),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            headers = response.body.get("headers", {})
            assert headers.get("Authorization") == "Bearer test-token-123"

    def test_bearer_token_custom_prefix(self):
        """测试自定义 Bearer 前缀"""
        api = APIModel(
            name="自定义 Bearer 前缀测试",
            method="GET",
            url="/headers",
            auth=BearerTokenAuth(token="my-token", prefix="Token"),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            headers = response.body.get("headers", {})
            assert headers.get("Authorization") == "Token my-token"

    def test_basic_auth(self):
        """测试 Basic 认证"""
        api = APIModel(
            name="Basic 认证测试",
            method="GET",
            url="/headers",
            auth=BasicAuth(username="user", password="pass"),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            headers = response.body.get("headers", {})
            # Basic dXNlcjpwYXNz (base64 of "user:pass")
            assert "Basic " in headers.get("Authorization", "")

    def test_httpbin_basic_auth_endpoint(self):
        """测试 httpbin 的 Basic 认证端点"""
        api = APIModel(
            name="Basic Auth 端点测试",
            method="GET",
            url="/basic-auth/testuser/testpass",
            auth=BasicAuth(username="testuser", password="testpass"),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            assert response.body.get("authenticated") is True
            assert response.body.get("user") == "testuser"
