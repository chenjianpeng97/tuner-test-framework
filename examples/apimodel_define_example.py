from tuner.api.base import APIModel
from tuner.api.body import JsonBody

# 定义并调用一个 JSON Body 的接口示例（POST 创建用户）
create_user_api = APIModel(
    name="创建用户",
    description="使用 JSON Body 创建新用户",
    method="POST",
    url="/api/v1/users",
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
    params={"extraparam1": 1, "extraparam2": "someinfo"},
    body=JsonBody(
        data={
            "username": "demo_user",
            "password": "123456",
            "email": "demo@example.com",
            "role": "user",
        }
    ),
)
