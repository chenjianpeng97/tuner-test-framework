"""
APIModel 使用示例
展示如何定义、注册、调用 APIModel，并结合环境切换、认证、前置/后置操作。
"""

from tuner.api.auth import NoAuth
from tuner.api.base import APIExecutor, APIModel
from tuner.api.body import JsonBody
from tuner.api.environment import Environment, EnvironmentManager, EnvironmentType
from tuner.api.operations import (
    AssertOperation,
    ExtractVariableOperation,
    SQLQueryOperation,
)

# 1. 注册环境
EnvironmentManager.register(
    Environment(name=EnvironmentType.TEST, url_prefix="https://test-api.example.com")
)
EnvironmentManager.register(
    Environment(name=EnvironmentType.PRODUCTION, url_prefix="https://api.example.com")
)
EnvironmentManager.switch(EnvironmentType.TEST)

# 2. 定义 API 模型
user_list_api = APIModel(
    name="用户列表",
    description="获取用户列表数据",
    method="GET",
    url="/api/v1/users",
    params={"page": 1, "pageSize": 10},
    headers={"Accept": "application/json"},
    auth=NoAuth(),
    pre_request=[
        SQLQueryOperation(
            name="查询用户总数",
            sql="SELECT COUNT(*) as total FROM users WHERE status = 'active'",
            result_variable="expected_total",
        ),
    ],
    post_request=[
        ExtractVariableOperation(
            name="提取用户列表",
            jsonpath="$.data.users",
            variable_name="actual_users",
        ),
        AssertOperation(
            name="验证响应码",
            jsonpath="$.code",
            operator="eq",
            expected=0,
            message="接口响应码应为 0",
        ),
    ],
)

# 3. 执行 API
executor = APIExecutor()
response = executor.execute(user_list_api)

print(f"HTTP 状态码: {response.status_code}")
print(f"响应数据: {response.body}")
print(f"预期用户总数: {executor.get_variable('expected_total')}")
print(f"实际用户列表: {executor.get_variable('actual_users')}")

# 4. 切换环境后再次调用
EnvironmentManager.switch(EnvironmentType.PRODUCTION)
response_prod = executor.execute(user_list_api)
print(f"[生产环境] HTTP 状态码: {response_prod.status_code}")

# 5. 定义并调用一个 JSON Body 的接口示例（POST 创建用户）
create_user_api = APIModel(
    name="创建用户",
    description="使用 JSON Body 创建新用户",
    method="POST",
    url="/api/v1/users",
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
    body=JsonBody(
        data={
            "username": "demo_user",
            "password": "123456",
            "email": "demo@example.com",
            "role": "user",
        }
    ),
)

create_response = executor.execute(create_user_api)
print(f"[JSON Body] 创建用户状态码: {create_response.status_code}")
print(f"[JSON Body] 创建用户响应: {create_response.body}")

# 6. 【常用场景】调用时动态覆盖部分字段（不修改原始 APIModel 定义）
# 测试工程师经常需要在不同测试用例中，对同一个 API 的 headers/params/body 做微调
# executor.execute() 支持 extra_headers, extra_params, override_body 参数

print("\n===== 动态覆盖字段示例 =====")

# 场景 A: 覆盖 headers 中的 Authorization（模拟不同用户 Token）
response_with_new_token = executor.execute(
    create_user_api,
    extra_headers={
        "Authorization": "Bearer new_token_for_test",  # 覆盖或新增 header
        "X-Request-Id": "test-request-12345",  # 新增自定义 header
    },
)
print(f"[覆盖 Header] 状态码: {response_with_new_token.status_code}")

# 场景 B: 覆盖 params（适用于 GET 请求，修改分页、筛选条件等）
response_with_new_params = executor.execute(
    user_list_api,
    extra_params={
        "page": 2,  # 覆盖默认的 page=1
        "status": "active",  # 新增筛选条件
    },
)
print(f"[覆盖 Params] 状态码: {response_with_new_params.status_code}")

# 场景 C: 覆盖 JSON Body 中的部分字段（最常见的测试场景）
# 方式一：使用 override_body 完全替换 body
response_with_new_body = executor.execute(
    create_user_api,
    override_body=JsonBody(
        data={
            "username": "test_user_001",  # 修改用户名
            "password": "new_password_123",  # 修改密码
            "email": "test001@example.com",  # 修改邮箱
            "role": "admin",  # 修改角色
            "department": "QA",  # 新增字段
        }
    ),
)
print(f"[覆盖 Body] 状态码: {response_with_new_body.status_code}")

# 场景 D: 组合覆盖 - 同时修改 headers + params + body
response_combined = executor.execute(
    create_user_api,
    extra_headers={
        "Authorization": "Bearer admin_token",
        "X-Tenant-Id": "tenant_001",
    },
    extra_params={
        "dryRun": "true",  # 测试模式，不实际创建
    },
    override_body=JsonBody(
        data={
            "username": "batch_user",
            "password": "batch_pwd",
            "email": "batch@example.com",
            "role": "user",
            "tags": ["test", "batch"],  # 支持复杂类型
        }
    ),
)
print(f"[组合覆盖] 状态码: {response_combined.status_code}")


# 场景 E: 使用辅助函数快速修改 body 中的个别字段（推荐封装）
def patch_json_body(original_body: JsonBody, **updates) -> JsonBody:
    """快速 patch JsonBody 中的部分字段"""
    new_data = {**original_body.data, **updates}
    return JsonBody(data=new_data)


# 只修改用户名和邮箱，其他保持默认
patched_body = patch_json_body(
    create_user_api.body,
    username="patched_user",
    email="patched@example.com",
)
response_patched = executor.execute(create_user_api, override_body=patched_body)
print(f"[Patch Body] 状态码: {response_patched.status_code}")
