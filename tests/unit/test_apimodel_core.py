"""
APIModel 单元测试：核心功能
使用 httpbin.org 作为测试服务器
"""

import pytest

from tuner.api.auth import BearerTokenAuth, NoAuth
from tuner.api.base import APIExecutor, APIModel
from tuner.api.body import JsonBody, NoneBody
from tuner.api.environment import Environment, EnvironmentManager, EnvironmentType
from tuner.api.operations import AssertOperation, ExtractVariableOperation


@pytest.fixture(autouse=True)
def setup_env():
    """每个测试前重置并配置环境"""
    EnvironmentManager.reset()
    EnvironmentManager.register(
        Environment(name=EnvironmentType.TEST, url_prefix="https://httpbin.org")
    )
    EnvironmentManager.switch(EnvironmentType.TEST)
    yield
    EnvironmentManager.reset()


class TestAPIModelBasic:
    """APIModel 基础功能测试"""

    def test_create_api_model(self):
        """测试创建 APIModel"""
        api = APIModel(
            name="测试接口",
            description="测试描述",
            method="GET",
            url="/get",
        )
        assert api.name == "测试接口"
        assert api.method == "GET"
        assert api.url == "/get"
        assert isinstance(api.body, NoneBody)
        assert isinstance(api.auth, NoAuth)

    def test_api_model_with_params(self):
        """测试带参数的 APIModel"""
        api = APIModel(
            name="带参数接口",
            method="GET",
            url="/get",
            params={"page": 1, "size": 10},
            headers={"Accept": "application/json"},
        )
        assert api.params == {"page": 1, "size": 10}
        assert api.headers["Accept"] == "application/json"

    def test_api_model_with_json_body(self):
        """测试带 JSON Body 的 APIModel"""
        api = APIModel(
            name="POST 接口",
            method="POST",
            url="/post",
            body=JsonBody(data={"username": "test", "password": "123"}),
        )
        assert isinstance(api.body, JsonBody)
        assert api.body.data["username"] == "test"


class TestAPIExecutorBasic:
    """APIExecutor 基础功能测试"""

    def test_executor_get_request(self):
        """测试 GET 请求"""
        api = APIModel(
            name="GET 测试",
            method="GET",
            url="/get",
            params={"foo": "bar"},
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            assert response.is_success()
            assert "foo" in response.body.get("args", {})

    def test_executor_post_json(self):
        """测试 POST JSON 请求"""
        api = APIModel(
            name="POST JSON 测试",
            method="POST",
            url="/post",
            body=JsonBody(data={"name": "test", "value": 123}),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            # httpbin 会返回 json 字段
            assert response.body.get("json") == {"name": "test", "value": 123}

    def test_executor_with_headers(self):
        """测试带自定义 Headers 的请求"""
        api = APIModel(
            name="Headers 测试",
            method="GET",
            url="/headers",
            headers={"X-Custom-Header": "custom-value"},
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            headers = response.body.get("headers", {})
            assert headers.get("X-Custom-Header") == "custom-value"


class TestAPIExecutorOverride:
    """APIExecutor 动态覆盖功能测试"""

    def test_extra_params(self):
        """测试额外参数覆盖"""
        api = APIModel(
            name="参数覆盖测试",
            method="GET",
            url="/get",
            params={"page": 1},
        )
        with APIExecutor() as executor:
            response = executor.execute(
                api,
                extra_params={"page": 2, "status": "active"},
            )
            assert response.status_code == 200
            args = response.body.get("args", {})
            assert args.get("page") == "2"  # httpbin 返回字符串
            assert args.get("status") == "active"

    def test_extra_headers(self):
        """测试额外 Headers 覆盖"""
        api = APIModel(
            name="Headers 覆盖测试",
            method="GET",
            url="/headers",
            headers={"X-Original": "original"},
        )
        with APIExecutor() as executor:
            response = executor.execute(
                api,
                extra_headers={"X-Extra": "extra", "X-Original": "overridden"},
            )
            assert response.status_code == 200
            headers = response.body.get("headers", {})
            assert headers.get("X-Extra") == "extra"
            assert headers.get("X-Original") == "overridden"

    def test_override_body(self):
        """测试 Body 覆盖"""
        api = APIModel(
            name="Body 覆盖测试",
            method="POST",
            url="/post",
            body=JsonBody(data={"original": True}),
        )
        with APIExecutor() as executor:
            response = executor.execute(
                api,
                override_body=JsonBody(data={"overridden": True, "new_field": "value"}),
            )
            assert response.status_code == 200
            json_data = response.body.get("json", {})
            assert json_data.get("overridden") is True
            assert json_data.get("new_field") == "value"
            assert "original" not in json_data

    def test_update_body_preserves_defaults(self):
        """测试 update_body 会保留未覆盖的默认字段（仅 JSON）"""
        api = APIModel(
            name="Body 更新测试",
            method="POST",
            url="/post",
            body=JsonBody(data={"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}),
        )
        with APIExecutor() as executor:
            response = executor.execute(
                api,
                update_body={"b": 3, "nested": {"y": 99}, "new": "value"},
            )
            assert response.status_code == 200
            json_data = response.body.get("json", {})
            assert json_data == {
                "a": 1,
                "b": 3,
                "nested": {"x": 1, "y": 99},
                "new": "value",
            }

    def test_path_params(self):
        """测试路径参数替换"""
        api = APIModel(
            name="路径参数测试",
            method="GET",
            url="/status/{code}",
        )
        with APIExecutor() as executor:
            response = executor.execute(api, path_params={"code": 201})
            assert response.status_code == 201


class TestAPIExecutorAuth:
    """APIExecutor 认证功能测试"""

    def test_bearer_token_auth(self):
        """测试 Bearer Token 认证"""
        api = APIModel(
            name="Bearer 认证测试",
            method="GET",
            url="/headers",
            auth=BearerTokenAuth(token="my-secret-token"),
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            headers = response.body.get("headers", {})
            assert "Bearer my-secret-token" in headers.get("Authorization", "")

    def test_extra_header_override_auth(self):
        """测试 extra_headers 覆盖认证头"""
        api = APIModel(
            name="认证覆盖测试",
            method="GET",
            url="/headers",
            auth=BearerTokenAuth(token="original-token"),
        )
        with APIExecutor() as executor:
            response = executor.execute(
                api,
                extra_headers={"Authorization": "Bearer new-token"},
            )
            assert response.status_code == 200
            headers = response.body.get("headers", {})
            # extra_headers 会覆盖 auth 设置的值
            assert "Bearer new-token" in headers.get("Authorization", "")


class TestAPIExecutorOperations:
    """APIExecutor 前置/后置操作测试"""

    def test_extract_variable(self):
        """测试变量提取"""
        api = APIModel(
            name="变量提取测试",
            method="GET",
            url="/get",
            params={"test": "value"},
            post_request=[
                ExtractVariableOperation(
                    name="提取 URL",
                    jsonpath="$.url",
                    variable_name="request_url",
                ),
            ],
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            url = executor.get_variable("request_url")
            assert url is not None
            assert "httpbin.org" in url

    def test_assert_operation_pass(self):
        """测试断言操作（通过）"""
        api = APIModel(
            name="断言测试",
            method="GET",
            url="/get",
            post_request=[
                AssertOperation(
                    name="断言 URL 存在",
                    jsonpath="$.url",
                    operator="exists",
                ),
            ],
        )
        with APIExecutor() as executor:
            # 不应抛出异常
            response = executor.execute(api)
            assert response.status_code == 200

    def test_assert_operation_fail(self):
        """测试断言操作（失败）"""
        api = APIModel(
            name="断言失败测试",
            method="GET",
            url="/get",
            post_request=[
                AssertOperation(
                    name="断言失败",
                    jsonpath="$.url",
                    operator="eq",
                    expected="wrong-value",
                    message="URL 不匹配",
                ),
            ],
        )
        with APIExecutor() as executor:
            with pytest.raises(AssertionError, match="URL 不匹配"):
                executor.execute(api)

    def test_set_and_get_variable(self):
        """测试手动设置和获取变量"""
        with APIExecutor() as executor:
            executor.set_variable("my_var", "my_value")
            assert executor.get_variable("my_var") == "my_value"
            assert executor.get_variable("non_existent") is None
