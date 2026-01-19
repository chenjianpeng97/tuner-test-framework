# API 模型管理设计文档

## 1. 概述

API 模型管理组件负责统一管理和调用 API 接口，参考 Apifox 的设计理念，提供完整的 API 定义和请求封装能力。

## 2. 设计目标

- **模型化定义**: 每个 API 接口定义为一个模型类，包含完整的请求属性
- **环境切换**: 支持通过 URL Prefix 切换测试/预发布/生产环境
- **多种 Body 类型**: 支持 JSON、Text、None 等多种请求体类型
- **认证管理**: 支持 Bearer Token、API Key 等鉴权方式（第一版仅支持 Bearer Token）
- **前置/后置操作**: 支持请求前后的数据库操作和断言
- **会话管理**: 支持登录态管理和复用

## 3. API 属性结构

参考 Apifox 设计，API 模型包含以下核心属性：

| 属性         | 类型            | 说明                                        |
| ------------ | --------------- | ------------------------------------------- |
| method       | str             | HTTP 方法: GET, POST, PUT, DELETE, PATCH 等 |
| url          | str             | API 路径，支持路径参数如 `/users/{user_id}` |
| url_prefix   | str             | 环境 URL 前缀，通过环境配置切换             |
| params       | Dict            | Query 参数                                  |
| body         | Body            | 请求体，支持多种子类型                      |
| headers      | Dict            | 请求头                                      |
| cookies      | Dict            | Cookies                                     |
| auth         | Auth            | 认证配置                                    |
| pre_request  | List[Operation] | 前置操作列表                                |
| post_request | List[Operation] | 后置操作列表                                |

## 4. 核心类设计

### 4.1 环境配置

```python
# src/tuner/api/environment.py

from enum import Enum
from typing import Dict
from pydantic import BaseModel

class EnvironmentType(str, Enum):
    """环境类型枚举"""
    TEST = "test"           # 测试环境
    STAGING = "staging"     # 预发布环境
    PRODUCTION = "prod"     # 生产环境

class Environment(BaseModel):
    """环境配置"""
    name: EnvironmentType
    url_prefix: str         # 如 https://test-api.example.com
    variables: Dict[str, str] = {}  # 环境变量

class EnvironmentManager:
    """环境管理器"""

    _environments: Dict[EnvironmentType, Environment] = {}
    _current: EnvironmentType = EnvironmentType.TEST

    @classmethod
    def register(cls, env: Environment):
        """注册环境配置"""
        cls._environments[env.name] = env

    @classmethod
    def switch(cls, env_type: EnvironmentType):
        """切换当前环境"""
        cls._current = env_type

    @classmethod
    def get_current(cls) -> Environment:
        """获取当前环境"""
        return cls._environments.get(cls._current)

    @classmethod
    def get_url_prefix(cls) -> str:
        """获取当前环境的 URL 前缀"""
        env = cls.get_current()
        return env.url_prefix if env else ""
```

### 4.2 请求体类型 (Body)

```python
# src/tuner/api/body.py

from abc import ABC
from enum import Enum
from typing import Any, Optional, Dict
from pydantic import BaseModel

class BodyType(str, Enum):
    """Body 类型枚举"""
    NONE = "none"           # 无 Body
    JSON = "json"           # JSON 格式
    TEXT = "text"           # 纯文本
    FORM_DATA = "form-data" # 表单数据
    FORM_URLENCODED = "x-www-form-urlencoded"  # URL 编码表单
    BINARY = "binary"       # 二进制文件
    XML = "xml"             # XML 格式

class Body(BaseModel, ABC):
    """Body 基类"""
    type: BodyType

class NoneBody(Body):
    """无 Body"""
    type: BodyType = BodyType.NONE

class JsonBody(Body):
    """JSON Body"""
    type: BodyType = BodyType.JSON
    data: Dict[str, Any]

class TextBody(Body):
    """文本 Body"""
    type: BodyType = BodyType.TEXT
    content: str
    content_type: str = "text/plain"

class FormDataBody(Body):
    """表单 Body"""
    type: BodyType = BodyType.FORM_DATA
    fields: Dict[str, Any]
    files: Optional[Dict[str, str]] = None  # 文件路径映射

class XmlBody(Body):
    """XML Body"""
    type: BodyType = BodyType.XML
    content: str
```

### 4.3 认证配置 (Auth)

```python
# src/tuner/api/auth.py

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel
import httpx

class AuthType(str, Enum):
    """认证类型枚举"""
    NONE = "none"
    BEARER_TOKEN = "bearer"
    API_KEY = "apikey"
    BASIC = "basic"
    # 第一版仅实现 BEARER_TOKEN

class Auth(BaseModel, ABC):
    """认证基类"""
    type: AuthType

    @abstractmethod
    def apply(self, request: httpx.Request) -> httpx.Request:
        """应用认证到请求"""
        pass

class NoAuth(Auth):
    """无认证"""
    type: AuthType = AuthType.NONE

    def apply(self, request: httpx.Request) -> httpx.Request:
        return request

class BearerTokenAuth(Auth):
    """Bearer Token 认证 (第一版重点支持)"""
    type: AuthType = AuthType.BEARER_TOKEN
    token: str
    prefix: str = "Bearer"  # 可自定义前缀

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = f"{self.prefix} {self.token}"
        return request

# 以下为后续版本扩展
class ApiKeyAuth(Auth):
    """API Key 认证 (预留)"""
    type: AuthType = AuthType.API_KEY
    key: str
    value: str
    add_to: str = "header"  # header 或 query

    def apply(self, request: httpx.Request) -> httpx.Request:
        if self.add_to == "header":
            request.headers[self.key] = self.value
        # query 参数处理...
        return request

class BasicAuth(Auth):
    """Basic 认证 (预留)"""
    type: AuthType = AuthType.BASIC
    username: str
    password: str

    def apply(self, request: httpx.Request) -> httpx.Request:
        # Basic 认证实现...
        pass
```

### 4.4 前置/后置操作

```python
# src/tuner/api/operations.py

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Dict, List, Callable
from pydantic import BaseModel

class OperationType(str, Enum):
    """操作类型枚举"""
    SQL_QUERY = "sql_query"         # SQL 查询
    SQL_EXECUTE = "sql_execute"     # SQL 执行
    EXTRACT_VARIABLE = "extract"    # 提取变量
    ASSERT = "assert"               # 断言
    SCRIPT = "script"               # 自定义脚本
    SET_VARIABLE = "set_var"        # 设置变量
    WAIT = "wait"                   # 等待

class OperationContext(BaseModel):
    """操作上下文"""
    variables: Dict[str, Any] = {}  # 变量存储
    request: Optional[Dict] = None   # 请求数据
    response: Optional[Dict] = None  # 响应数据

    class Config:
        arbitrary_types_allowed = True

class Operation(BaseModel, ABC):
    """操作基类"""
    type: OperationType
    name: str = ""
    enabled: bool = True

    @abstractmethod
    def execute(self, context: OperationContext) -> OperationContext:
        """执行操作"""
        pass

class SQLQueryOperation(Operation):
    """SQL 查询操作"""
    type: OperationType = OperationType.SQL_QUERY
    sql: str
    params: Optional[tuple] = None
    result_variable: str  # 结果存储到哪个变量

    def execute(self, context: OperationContext) -> OperationContext:
        from tuner.tools.sql import SQLTool
        # 获取 SQL 工具实例并执行查询
        # result = sql_tool.query(self.sql, self.params)
        # context.variables[self.result_variable] = result
        return context

class SQLExecuteOperation(Operation):
    """SQL 执行操作"""
    type: OperationType = OperationType.SQL_EXECUTE
    sql: str
    params: Optional[tuple] = None

    def execute(self, context: OperationContext) -> OperationContext:
        # 执行 SQL (INSERT/UPDATE/DELETE)
        return context

class ExtractVariableOperation(Operation):
    """提取变量操作"""
    type: OperationType = OperationType.EXTRACT_VARIABLE
    source: str = "response"  # response, request, header
    jsonpath: str             # JSONPath 表达式
    variable_name: str        # 存储变量名

    def execute(self, context: OperationContext) -> OperationContext:
        from tuner.tools.jsonpath import JSONPathTool

        if self.source == "response" and context.response:
            jp = JSONPathTool(context.response)
            value = jp.extract(self.jsonpath)
            context.variables[self.variable_name] = value

        return context

class AssertOperation(Operation):
    """断言操作"""
    type: OperationType = OperationType.ASSERT
    source: str = "response"   # response, variable
    jsonpath: Optional[str] = None
    variable_name: Optional[str] = None
    operator: str = "eq"       # eq, ne, gt, lt, contains, exists 等
    expected: Any = None
    message: str = ""          # 断言失败消息

    def execute(self, context: OperationContext) -> OperationContext:
        # 获取实际值
        if self.source == "response" and self.jsonpath:
            from tuner.tools.jsonpath import JSONPathTool
            actual = JSONPathTool(context.response).extract(self.jsonpath)
        elif self.source == "variable" and self.variable_name:
            actual = context.variables.get(self.variable_name)
        else:
            actual = None

        # 执行断言
        self._assert(actual, self.operator, self.expected)
        return context

    def _assert(self, actual: Any, operator: str, expected: Any):
        """执行断言逻辑"""
        operators = {
            "eq": lambda a, e: a == e,
            "ne": lambda a, e: a != e,
            "gt": lambda a, e: a > e,
            "lt": lambda a, e: a < e,
            "gte": lambda a, e: a >= e,
            "lte": lambda a, e: a <= e,
            "contains": lambda a, e: e in a,
            "not_contains": lambda a, e: e not in a,
            "exists": lambda a, e: a is not None,
            "not_exists": lambda a, e: a is None,
            "is_empty": lambda a, e: len(a) == 0,
            "not_empty": lambda a, e: len(a) > 0,
        }

        assert_func = operators.get(operator)
        if not assert_func(actual, expected):
            raise AssertionError(
                self.message or f"Assertion failed: {actual} {operator} {expected}"
            )

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
```

### 4.5 API 响应

```python
# src/tuner/api/response.py

from typing import Any, Dict, Optional
from pydantic import BaseModel

class APIResponse(BaseModel):
    """API 响应封装"""
    status_code: int
    headers: Dict[str, str]
    cookies: Dict[str, str]
    body: Any
    elapsed: float  # 响应时间（秒）
    raw_text: str = ""  # 原始响应文本

    def json(self) -> Dict:
        """获取 JSON 响应"""
        return self.body if isinstance(self.body, dict) else {}

    def is_success(self) -> bool:
        """是否成功响应 (2xx)"""
        return 200 <= self.status_code < 300
```

### 4.6 API 模型基类

```python
# src/tuner/api/base.py

from abc import ABC
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel
import httpx

from .environment import EnvironmentManager
from .body import Body, NoneBody, JsonBody, TextBody, BodyType
from .auth import Auth, NoAuth, BearerTokenAuth
from .operations import Operation, OperationContext
from .response import APIResponse

class APIModel(BaseModel):
    """API 模型定义"""

    # 基本属性
    name: str = ""                          # API 名称
    description: str = ""                   # API 描述
    method: str = "GET"                     # HTTP 方法
    url: str                                # API 路径
    url_prefix: Optional[str] = None        # URL 前缀（优先于环境配置）

    # 请求参数
    params: Dict[str, Any] = {}             # Query 参数
    body: Body = NoneBody()                 # 请求体
    headers: Dict[str, str] = {}            # 请求头
    cookies: Dict[str, str] = {}            # Cookies

    # 认证
    auth: Auth = NoAuth()                   # 认证配置

    # 前置/后置操作
    pre_request: List[Operation] = []       # 前置操作
    post_request: List[Operation] = []      # 后置操作

    # 超时配置
    timeout: float = 30.0                   # 超时时间（秒）

    class Config:
        arbitrary_types_allowed = True

class APIExecutor:
    """API 执行器"""

    def __init__(self, session: Optional[httpx.Client] = None):
        self.session = session or httpx.Client()
        self.context = OperationContext()

    def execute(
        self,
        api: APIModel,
        path_params: Optional[Dict] = None,
        extra_params: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None,
        override_body: Optional[Body] = None,
    ) -> APIResponse:
        """
        执行 API 请求

        Args:
            api: API 模型
            path_params: 路径参数，用于替换 URL 中的 {param}
            extra_params: 额外的 Query 参数
            extra_headers: 额外的请求头
            override_body: 覆盖请求体

        Returns:
            APIResponse: 响应对象
        """

        # 1. 执行前置操作
        self._run_operations(api.pre_request)

        # 2. 构建请求
        request = self._build_request(
            api, path_params, extra_params, extra_headers, override_body
        )

        # 3. 发送请求
        response = self._send_request(request, api.timeout)

        # 4. 更新上下文
        self.context.response = response.body

        # 5. 执行后置操作
        self._run_operations(api.post_request)

        return response

    def _build_request(
        self,
        api: APIModel,
        path_params: Optional[Dict],
        extra_params: Optional[Dict],
        extra_headers: Optional[Dict],
        override_body: Optional[Body],
    ) -> httpx.Request:
        """构建 HTTP 请求"""

        # URL 处理
        url_prefix = api.url_prefix or EnvironmentManager.get_url_prefix()
        url = api.url.format(**(path_params or {}))
        full_url = f"{url_prefix}{url}"

        # 合并参数
        params = {**api.params, **(extra_params or {})}

        # 合并请求头
        headers = {**api.headers, **(extra_headers or {})}

        # 处理 Body
        body = override_body or api.body
        content, content_type = self._prepare_body(body)
        if content_type:
            headers["Content-Type"] = content_type

        # 创建请求
        request = self.session.build_request(
            method=api.method,
            url=full_url,
            params=params,
            headers=headers,
            cookies=api.cookies,
            content=content if isinstance(content, (str, bytes)) else None,
            json=content if isinstance(content, dict) else None,
        )

        # 应用认证
        request = api.auth.apply(request)

        return request

    def _prepare_body(self, body: Body) -> tuple[Any, Optional[str]]:
        """准备请求体"""
        if body.type == BodyType.NONE:
            return None, None
        elif body.type == BodyType.JSON:
            return body.data, "application/json"
        elif body.type == BodyType.TEXT:
            return body.content, body.content_type
        elif body.type == BodyType.XML:
            return body.content, "application/xml"
        # 其他类型处理...
        return None, None

    def _send_request(self, request: httpx.Request, timeout: float) -> APIResponse:
        """发送请求"""
        response = self.session.send(request, timeout=timeout)

        # 解析响应体
        try:
            body = response.json()
        except:
            body = None

        return APIResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            cookies=dict(response.cookies),
            body=body,
            elapsed=response.elapsed.total_seconds(),
            raw_text=response.text,
        )

    def _run_operations(self, operations: List[Operation]):
        """执行操作列表"""
        for op in operations:
            if op.enabled:
                self.context = op.execute(self.context)

    def get_variable(self, name: str) -> Any:
        """获取上下文变量"""
        return self.context.variables.get(name)

    def set_variable(self, name: str, value: Any):
        """设置上下文变量"""
        self.context.variables[name] = value
```

### 4.7 APISession 会话管理

```python
# src/tuner/api/session.py

from typing import Optional, Dict
import httpx

from .base import APIExecutor, APIModel
from .auth import BearerTokenAuth
from .response import APIResponse

class APISession:
    """API 会话管理"""

    def __init__(self, base_url: Optional[str] = None):
        self.client = httpx.Client()
        self.executor = APIExecutor(self.client)
        self._token: Optional[str] = None
        self._cookies: Dict[str, str] = {}

    def login(self, username: str, password: str, login_api: APIModel) -> bool:
        """
        执行登录

        Args:
            username: 用户名
            password: 密码
            login_api: 登录接口模型

        Returns:
            是否登录成功
        """
        # 执行登录请求
        response = self.executor.execute(login_api)

        if response.is_success():
            # 提取 Token
            from tuner.tools.jsonpath import JSONPathTool
            jp = JSONPathTool(response.body)
            self._token = jp.extract("$.data.token") or jp.extract("$.token")

            # 保存 Cookies
            self._cookies = response.cookies

            return True

        return False

    def get_auth(self) -> BearerTokenAuth:
        """获取当前认证"""
        return BearerTokenAuth(token=self._token) if self._token else None

    def execute(self, api: APIModel, **kwargs) -> APIResponse:
        """执行 API（自动附加认证）"""
        if self._token and api.auth.type.value == "none":
            api.auth = self.get_auth()

        return self.executor.execute(api, **kwargs)

    def get_storage_state(self) -> dict:
        """获取存储状态（用于 Playwright 复用）"""
        storage = {
            "cookies": [
                {"name": k, "value": v, "domain": "", "path": "/"}
                for k, v in self._cookies.items()
            ],
            "origins": []
        }

        # 如果有 Token，也加入 localStorage
        if self._token:
            storage["origins"].append({
                "origin": "",
                "localStorage": [
                    {"name": "token", "value": self._token}
                ]
            })

        return storage

    def close(self):
        """关闭会话"""
        self.client.close()
```

## 5. 具体 API 模型示例

### 5.1 用户列表 API

```python
# src/tuner/api/models/user.py

from tuner.api.base import APIModel
from tuner.api.body import NoneBody
from tuner.api.auth import NoAuth, BearerTokenAuth
from tuner.api.operations import (
    SQLQueryOperation,
    AssertOperation,
    ExtractVariableOperation,
)

# 用户列表接口
user_list_api = APIModel(
    name="用户列表",
    description="获取用户列表数据",
    method="GET",
    url="/api/v1/users",
    params={
        "page": 1,
        "pageSize": 20,
    },
    headers={
        "Accept": "application/json",
    },
    auth=NoAuth(),  # 将在 Session 中自动附加
    pre_request=[
        # 前置：查询数据库获取预期数据
        SQLQueryOperation(
            name="查询用户总数",
            sql="SELECT COUNT(*) as total FROM users WHERE status = 'active'",
            result_variable="expected_total",
        ),
    ],
    post_request=[
        # 后置：提取响应数据
        ExtractVariableOperation(
            name="提取用户列表",
            jsonpath="$.data.users",
            variable_name="actual_users",
        ),
        # 后置：断言
        AssertOperation(
            name="验证响应码",
            jsonpath="$.code",
            operator="eq",
            expected=0,
            message="接口响应码应为 0",
        ),
    ],
)
```

### 5.2 用户导出 API

```python
from tuner.api.body import JsonBody

# 用户导出接口
user_export_api = APIModel(
    name="用户导出",
    description="导出用户数据为 Excel",
    method="POST",
    url="/api/v1/users/export",
    body=JsonBody(
        data={
            "format": "xlsx",
            "filters": {},
        }
    ),
    headers={
        "Content-Type": "application/json",
    },
    post_request=[
        ExtractVariableOperation(
            name="提取下载链接",
            jsonpath="$.data.downloadUrl",
            variable_name="download_url",
        ),
        AssertOperation(
            name="验证导出成功",
            jsonpath="$.code",
            operator="eq",
            expected=0,
        ),
    ],
)
```

### 5.3 登录 API

```python
# 登录接口
login_api = APIModel(
    name="用户登录",
    description="用户登录获取 Token",
    method="POST",
    url="/api/v1/auth/login",
    body=JsonBody(
        data={
            "username": "",  # 运行时填充
            "password": "",
        }
    ),
    post_request=[
        AssertOperation(
            name="验证登录成功",
            jsonpath="$.code",
            operator="eq",
            expected=0,
            message="登录失败",
        ),
        ExtractVariableOperation(
            name="提取 Token",
            jsonpath="$.data.token",
            variable_name="token",
        ),
    ],
)
```

## 6. 使用方式

```python
# 在测试用例中使用
from tuner.api.session import APISession
from tuner.api.environment import EnvironmentManager, Environment, EnvironmentType
from tuner.api.models.user import user_list_api, user_export_api, login_api
from tuner.api.body import JsonBody

# 配置环境
EnvironmentManager.register(Environment(
    name=EnvironmentType.TEST,
    url_prefix="https://test-api.example.com",
))
EnvironmentManager.switch(EnvironmentType.TEST)

# 创建会话
session = APISession()

# 登录
login_api_copy = login_api.copy()
login_api_copy.body = JsonBody(data={"username": "admin", "password": "123456"})
session.login("admin", "123456", login_api_copy)

# 调用用户列表接口
response = session.execute(
    user_list_api,
    extra_params={"status": "active"},
)

assert response.status_code == 200

# 获取前置操作中查询的数据库结果
expected_total = session.executor.get_variable("expected_total")
# 获取后置操作中提取的数据
actual_users = session.executor.get_variable("actual_users")

print(f"预期用户数: {expected_total}, 实际用户数: {len(actual_users)}")

# 关闭会话
session.close()
```

## 7. API 模型注册机制

```python
# src/tuner/api/registry.py

class APIRegistry:
    """API 模型注册表"""

    _models: Dict[str, APIModel] = {}

    @classmethod
    def register(cls, name: str, api: APIModel):
        """注册 API 模型"""
        cls._models[name] = api

    @classmethod
    def get(cls, name: str) -> APIModel:
        """获取 API 模型"""
        return cls._models.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """列出所有已注册的 API"""
        return list(cls._models.keys())

# 注册 API
APIRegistry.register("user_list", user_list_api)
APIRegistry.register("user_export", user_export_api)
APIRegistry.register("login", login_api)
```

        def decorator(api_class):
            cls._models[name] = api_class
            return api_class
        return decorator

    @classmethod
    def get(cls, name: str) -> type:
        """获取 API 模型类"""
        return cls._models.get(name)

# 使用装饰器注册

@APIRegistry.register("user_list")
class UserListAPI(APIBase):
...

````

## 7. 配置化 API 定义（可选扩展）

支持通过 YAML 文件定义 API：

```yaml
# data/api/user.yaml
user_list:
  method: GET
  path: /api/v1/users
  headers:
    Content-Type: application/json

user_export:
  method: POST
  path: /api/v1/users/export
  headers:
    Content-Type: application/json
````
