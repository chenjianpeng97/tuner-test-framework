"""
前置/后置操作模块
支持 SQL 查询、变量提取、断言、等待等操作
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class OperationType(str, Enum):
    """操作类型枚举"""

    SQL_QUERY = "sql_query"  # SQL 查询
    SQL_EXECUTE = "sql_execute"  # SQL 执行
    EXTRACT_VARIABLE = "extract"  # 提取变量
    ASSERT = "assert"  # 断言
    SCRIPT = "script"  # 自定义脚本
    SET_VARIABLE = "set_var"  # 设置变量
    WAIT = "wait"  # 等待


class OperationContext(BaseModel):
    """操作上下文"""

    variables: dict[str, Any] = {}  # 变量存储
    request: dict[str, Any] | None = None  # 请求数据
    response: dict[str, Any] | None = None  # 响应数据

    model_config = {"arbitrary_types_allowed": True}


class Operation(BaseModel, ABC):
    """操作基类"""

    type: OperationType
    name: str = ""
    enabled: bool = True

    @abstractmethod
    def execute(self, context: OperationContext) -> OperationContext:
        """执行操作"""


class SQLQueryOperation(Operation):
    """SQL 查询操作"""

    type: OperationType = OperationType.SQL_QUERY
    sql: str
    params: tuple[Any, ...] | None = None
    result_variable: str  # 结果存储到哪个变量

    def execute(self, context: OperationContext) -> OperationContext:
        # TODO: 集成 SQLTool 后实现实际查询
        # 目前返回空列表作为占位
        context.variables[self.result_variable] = []
        return context


class SQLExecuteOperation(Operation):
    """SQL 执行操作（INSERT/UPDATE/DELETE）"""

    type: OperationType = OperationType.SQL_EXECUTE
    sql: str
    params: tuple[Any, ...] | None = None

    def execute(self, context: OperationContext) -> OperationContext:
        # TODO: 集成 SQLTool 后实现实际执行
        return context


class ExtractVariableOperation(Operation):
    """提取变量操作（从响应中提取数据）"""

    type: OperationType = OperationType.EXTRACT_VARIABLE
    source: str = "response"  # response, request, header
    jsonpath: str  # JSONPath 表达式
    variable_name: str  # 存储变量名

    def execute(self, context: OperationContext) -> OperationContext:
        if self.source == "response" and context.response:
            # 简单的 JSONPath 实现（支持 $.a.b.c 格式）
            value = self._extract_by_path(context.response, self.jsonpath)
            context.variables[self.variable_name] = value
        return context

    def _extract_by_path(self, data: dict[str, Any], path: str) -> Any:
        """简单的 JSONPath 提取（支持 $.a.b.c 和 $.a[0].b 格式）"""
        if not path.startswith("$."):
            return None

        # 移除 $. 前缀
        path = path[2:]
        if not path:
            return data

        current = data
        # 分割路径，处理数组索引
        import re

        parts = re.split(r"\.|\[|\]", path)
        parts = [p for p in parts if p]  # 移除空字符串

        for part in parts:
            if current is None:
                return None
            if part.isdigit():
                # 数组索引
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current


class AssertOperation(Operation):
    """断言操作"""

    type: OperationType = OperationType.ASSERT
    source: str = "response"  # response, variable
    jsonpath: str | None = None
    variable_name: str | None = None
    operator: str = "eq"  # eq, ne, gt, lt, contains, exists 等
    expected: Any = None
    message: str = ""  # 断言失败消息

    def execute(self, context: OperationContext) -> OperationContext:
        # 获取实际值
        actual: Any = None
        if self.source == "response" and self.jsonpath and context.response:
            actual = ExtractVariableOperation(
                jsonpath=self.jsonpath,
                variable_name="_temp",
            )._extract_by_path(context.response, self.jsonpath)
        elif self.source == "variable" and self.variable_name:
            actual = context.variables.get(self.variable_name)

        # 执行断言
        self._assert(actual, self.operator, self.expected)
        return context

    def _assert(self, actual: Any, operator: str, expected: Any) -> None:
        """执行断言逻辑"""
        operators = {
            "eq": lambda a, e: a == e,
            "ne": lambda a, e: a != e,
            "gt": lambda a, e: a > e,
            "lt": lambda a, e: a < e,
            "gte": lambda a, e: a >= e,
            "lte": lambda a, e: a <= e,
            "contains": lambda a, e: e in a if a else False,
            "not_contains": lambda a, e: e not in a if a else True,
            "exists": lambda a, _e: a is not None,
            "not_exists": lambda a, _e: a is None,
            "is_empty": lambda a, _e: len(a) == 0 if a is not None else True,
            "not_empty": lambda a, _e: len(a) > 0 if a is not None else False,
        }

        assert_func = operators.get(operator)
        if assert_func is None:
            msg = f"不支持的断言操作符: {operator}"
            raise ValueError(msg)

        if not assert_func(actual, expected):
            error_msg = self.message or f"断言失败: {actual} {operator} {expected}"
            raise AssertionError(error_msg)


class SetVariableOperation(Operation):
    """设置变量操作"""

    type: OperationType = OperationType.SET_VARIABLE
    variable_name: str
    value: Any

    def execute(self, context: OperationContext) -> OperationContext:
        context.variables[self.variable_name] = self.value
        return context


class WaitOperation(Operation):
    """等待操作"""

    type: OperationType = OperationType.WAIT
    seconds: float

    def execute(self, context: OperationContext) -> OperationContext:
        import time

        time.sleep(self.seconds)
        return context
