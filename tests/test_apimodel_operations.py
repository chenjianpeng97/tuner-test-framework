"""
APIModel 单元测试：前置/后置操作
"""

import pytest

from tuner.api.base import APIExecutor, APIModel
from tuner.api.environment import Environment, EnvironmentManager, EnvironmentType
from tuner.api.operations import (
    AssertOperation,
    ExtractVariableOperation,
    OperationContext,
    SetVariableOperation,
    WaitOperation,
)


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


class TestExtractVariableOperation:
    """变量提取操作测试"""

    def test_extract_simple_path(self):
        """测试简单路径提取"""
        op = ExtractVariableOperation(
            name="提取测试",
            jsonpath="$.name",
            variable_name="result",
        )
        context = OperationContext(response={"name": "test", "value": 123})
        context = op.execute(context)
        assert context.variables["result"] == "test"

    def test_extract_nested_path(self):
        """测试嵌套路径提取"""
        op = ExtractVariableOperation(
            name="嵌套提取",
            jsonpath="$.data.user.name",
            variable_name="user_name",
        )
        context = OperationContext(
            response={"data": {"user": {"name": "Alice", "age": 30}}}
        )
        context = op.execute(context)
        assert context.variables["user_name"] == "Alice"

    def test_extract_array_index(self):
        """测试数组索引提取"""
        op = ExtractVariableOperation(
            name="数组提取",
            jsonpath="$.items[0].id",
            variable_name="first_id",
        )
        context = OperationContext(
            response={"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        )
        context = op.execute(context)
        assert context.variables["first_id"] == 1

    def test_extract_nonexistent_path(self):
        """测试不存在的路径"""
        op = ExtractVariableOperation(
            name="不存在路径",
            jsonpath="$.nonexistent.path",
            variable_name="result",
        )
        context = OperationContext(response={"name": "test"})
        context = op.execute(context)
        assert context.variables["result"] is None


class TestAssertOperation:
    """断言操作测试"""

    def test_assert_eq_pass(self):
        """测试相等断言（通过）"""
        op = AssertOperation(
            name="相等断言",
            jsonpath="$.code",
            operator="eq",
            expected=0,
        )
        context = OperationContext(response={"code": 0, "message": "ok"})
        # 不应抛出异常
        op.execute(context)

    def test_assert_eq_fail(self):
        """测试相等断言（失败）"""
        op = AssertOperation(
            name="相等断言",
            jsonpath="$.code",
            operator="eq",
            expected=0,
            message="响应码错误",
        )
        context = OperationContext(response={"code": 1, "message": "error"})
        with pytest.raises(AssertionError, match="响应码错误"):
            op.execute(context)

    def test_assert_ne(self):
        """测试不等断言"""
        op = AssertOperation(
            name="不等断言",
            jsonpath="$.status",
            operator="ne",
            expected="error",
        )
        context = OperationContext(response={"status": "success"})
        op.execute(context)

    def test_assert_gt(self):
        """测试大于断言"""
        op = AssertOperation(
            name="大于断言",
            jsonpath="$.count",
            operator="gt",
            expected=5,
        )
        context = OperationContext(response={"count": 10})
        op.execute(context)

    def test_assert_contains(self):
        """测试包含断言"""
        op = AssertOperation(
            name="包含断言",
            jsonpath="$.message",
            operator="contains",
            expected="success",
        )
        context = OperationContext(response={"message": "operation success"})
        op.execute(context)

    def test_assert_exists(self):
        """测试存在断言"""
        op = AssertOperation(
            name="存在断言",
            jsonpath="$.data",
            operator="exists",
        )
        context = OperationContext(response={"data": {"id": 1}})
        op.execute(context)

    def test_assert_not_empty(self):
        """测试非空断言"""
        op = AssertOperation(
            name="非空断言",
            jsonpath="$.items",
            operator="not_empty",
        )
        context = OperationContext(response={"items": [1, 2, 3]})
        op.execute(context)

    def test_assert_from_variable(self):
        """测试从变量断言"""
        op = AssertOperation(
            name="变量断言",
            source="variable",
            variable_name="my_var",
            operator="eq",
            expected="expected_value",
        )
        context = OperationContext(variables={"my_var": "expected_value"})
        op.execute(context)


class TestSetVariableOperation:
    """设置变量操作测试"""

    def test_set_simple_value(self):
        """测试设置简单值"""
        op = SetVariableOperation(
            name="设置变量",
            variable_name="my_var",
            value="my_value",
        )
        context = OperationContext()
        context = op.execute(context)
        assert context.variables["my_var"] == "my_value"

    def test_set_complex_value(self):
        """测试设置复杂值"""
        op = SetVariableOperation(
            name="设置复杂变量",
            variable_name="config",
            value={"host": "localhost", "port": 8080},
        )
        context = OperationContext()
        context = op.execute(context)
        assert context.variables["config"]["host"] == "localhost"


class TestWaitOperation:
    """等待操作测试"""

    def test_wait(self):
        """测试等待"""
        import time

        op = WaitOperation(name="等待", seconds=0.1)
        context = OperationContext()

        start = time.time()
        op.execute(context)
        elapsed = time.time() - start

        assert elapsed >= 0.1


class TestOperationsIntegration:
    """操作集成测试（与真实 API 结合）"""

    def test_operations_chain(self):
        """测试操作链"""
        api = APIModel(
            name="操作链测试",
            method="GET",
            url="/get",
            params={"test": "value"},
            pre_request=[
                SetVariableOperation(
                    name="设置前置变量",
                    variable_name="pre_var",
                    value="pre_value",
                ),
            ],
            post_request=[
                ExtractVariableOperation(
                    name="提取 URL",
                    jsonpath="$.url",
                    variable_name="request_url",
                ),
                ExtractVariableOperation(
                    name="提取参数",
                    jsonpath="$.args.test",
                    variable_name="test_param",
                ),
                AssertOperation(
                    name="断言参数值",
                    source="variable",
                    variable_name="test_param",
                    operator="eq",
                    expected="value",
                ),
            ],
        )
        with APIExecutor() as executor:
            response = executor.execute(api)
            assert response.status_code == 200
            assert executor.get_variable("pre_var") == "pre_value"
            assert "httpbin.org" in executor.get_variable("request_url")
            assert executor.get_variable("test_param") == "value"
