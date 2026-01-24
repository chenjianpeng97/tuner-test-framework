import httpx
import pytest

from tuner.api.base import APIExecutor
from tuner.api.environment import Environment, EnvironmentManager, EnvironmentType
from tuner.api.operations import AssertOperation

from .apimodels import get_get_api
from .envieronment import URL_PREFIX


@pytest.fixture(autouse=True)
def setup_env():
    """每个测试前重置并配置环境"""
    EnvironmentManager.reset()
    EnvironmentManager.register(
        Environment(name=EnvironmentType.TEST, url_prefix=URL_PREFIX)
    )
    EnvironmentManager.switch(EnvironmentType.TEST)
    yield
    EnvironmentManager.reset()


def test_apifox_echo_service_connection():
    """测试 Apifox Echo 服务连接是否正常"""
    api = get_get_api
    with APIExecutor() as executor:
        response = executor.execute(api)
        assert response.status_code == 200


class TestApimodelOperations:
    """测试 APIModel 的前后置操作方法"""

    def test_assert_operation_pass(self):
        """测试断言操作（通过）"""
        api = get_get_api
        api.post_request = [
            AssertOperation(
                name="验证响应参数 q1",
                jsonpath="$.args.q1",
                operator="eq",
                expected="v1",
                message="参数 q1 应为 v1",
            ),
        ]
        with APIExecutor() as executor:
            executor.execute(api)

    def test_assert_operation_fail(self):
        """测试断言操作（失败）"""
        api = get_get_api
        api.post_request = [
            AssertOperation(
                name="验证响应参数 q1",
                jsonpath="$.args.q1",
                operator="eq",
                expected="v2",
                message="参数 q1 应为 v2",
            ),
        ]
        with pytest.raises(AssertionError) as exc, APIExecutor() as executor:
            executor.execute(api)
        assert "参数 q1 应为 v2" in str(exc.value)

    def test_multiple_assertions_fail(self):
        """多个断言中有失败时应抛出断言错误"""
        api = get_get_api
        api.post_request = [
            AssertOperation(
                name="验证响应参数 q1 (通过)",
                jsonpath="$.args.q1",
                operator="eq",
                expected="v1",
                message="参数 q1 应为 v1",
            ),
            AssertOperation(
                name="验证响应参数 q1 (失败)",
                jsonpath="$.args.q1",
                operator="eq",
                expected="v2",
                message="参数 q1 应为 v2",
            ),
        ]
        with pytest.raises(AssertionError), APIExecutor() as executor:
            executor.execute(api)

    def test_assert_operation_numeric_type_httpx(self, monkeypatch):
        """断言处理 jsonpath 指向的值为数字类型（使用 httpx mock）"""
        api = get_get_api
        api.post_request = [
            AssertOperation(
                name="验证响应参数 q1（数字）",
                jsonpath="$.args.q1",
                operator="eq",
                expected=123,
                message="参数 q1 应为 123",
            ),
        ]

        class MockResponse:
            def __init__(self, data, status=200):
                import datetime
                import json as _json

                self.status_code = status
                self._data = data
                # mimic httpx.Response attributes used by APIExecutor
                self.headers = {"content-type": "application/json"}
                self.cookies = {}
                # httpx.Response.elapsed is a timedelta-like object with total_seconds()
                self.elapsed = datetime.timedelta(seconds=0)
                self.text = _json.dumps(data, ensure_ascii=False)

            def json(self):
                return self._data

        def mock_client_request(self, method, url, **kwargs):
            # 返回的 json 中 args.q1 为数字类型
            return MockResponse({"args": {"q1": 123}}, status=200)

        # 替换 httpx.Client.request，使 APIExecutor 使用我们的 mock 响应
        monkeypatch.setattr(httpx.Client, "request", mock_client_request, raising=True)

        with APIExecutor() as executor:
            # 断言应通过，不抛出 AssertionError
            executor.execute(api)
