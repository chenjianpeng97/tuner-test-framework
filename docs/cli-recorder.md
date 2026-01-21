# CLI 录制工具

Tuner 框架提供了一个 CLI 工具，用于通过代理服务录制 HTTP 请求，自动生成 `APIModel` 定义文件。

## 安装

录制功能依赖 `mitmproxy`，作为可选依赖安装：

```bash
# 安装带录制功能的完整版本
pip install tuner-test-framework[recorder]

# 或单独安装 mitmproxy
pip install mitmproxy
```

## 使用方法

### 启动录制服务

```bash
# 基本用法
tuner record --url-prefix http://api.example.com/v1

# 指定端口和输出目录
tuner record -p 8080 -u http://api.example.com/v1 -o my_apis

# 录制多个 URL 前缀
tuner record \
    -u http://api.example.com/v1 \
    -u http://api.example.com/v2

# 覆盖已存在的文件
tuner record -u http://api.example.com/v1 --overwrite
```

### 命令参数

| 参数           | 简写 | 默认值        | 说明                 |
| -------------- | ---- | ------------- | -------------------- |
| `--port`       | `-p` | 8080          | 代理监听端口         |
| `--url-prefix` | `-u` | (必填)        | URL 前缀，可多次指定 |
| `--output`     | `-o` | recorded_apis | 输出目录             |
| `--overwrite`  | -    | False         | 是否覆盖已存在的文件 |

### 配置代理

启动录制服务后，需要配置客户端使用代理：

1. **浏览器**: 配置 HTTP 代理为 `127.0.0.1:8080`
2. **移动设备**: 在 WiFi 设置中配置手动代理
3. **应用程序**: 设置 `HTTP_PROXY` 环境变量

### 安装 HTTPS 证书

如果需要录制 HTTPS 请求，需要安装 mitmproxy 证书：

1. 配置代理后，访问 http://mitm.it
2. 根据设备类型下载并安装证书
3. 信任证书（某些系统需要手动信任）

## 生成的代码

录制器会为每个匹配的请求生成一个 `.py` 文件，内容示例：

```python
"""
API Model: post_users
录制自: POST http://api.example.com/v1/users?role=admin
响应状态码: 200
"""

from tuner.api.base import APIModel
from tuner.api.body import JsonBody, NoneBody


post_users_api = APIModel(
    name="post_users",
    description="录制生成的 API 模型",
    method="POST",
    url="/v1/users",
    params={
        "role": "admin",
    },
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer xxx",
    },
    body=JsonBody(
        data={'username': 'demo', 'email': 'demo@example.com'}
    ),
)
```

## 架构设计

```
src/tuner/cli/recorder/
├── __init__.py     # 模块导出
├── main.py         # CLI 入口和命令定义
├── addon.py        # mitmproxy addon（录制器）
└── codegen.py      # APIModel 代码生成器
```

### 设计原则

1. **无技术债**: 生成的代码直接使用 `tuner.api.base.APIModel` 和 `tuner.api.body.*`，
   不引入独立的模型描述，保持单一数据源。

2. **可扩展**: 代码生成逻辑与 mitmproxy 解耦，`codegen.py` 可独立使用。

3. **支持多前缀**: 可同时录制多个 URL 前缀，每个前缀独立处理。

## 编程式使用

除了 CLI，录制器也可以在代码中使用：

```python
from tuner.cli.recorder import (
    RecordedRequest,
    RecordedResponse,
    generate_apimodel_code,
)

# 从其他来源获取请求数据
request = RecordedRequest(
    method="POST",
    url="http://api.example.com/v1/users",
    headers={"Content-Type": "application/json"},
    body_content=b'{"username": "demo"}',
    body_content_type="application/json",
)

response = RecordedResponse(
    status_code=200,
    headers={},
    body_content=b'{"id": 1}',
)

# 生成代码
code = generate_apimodel_code(request, response)
print(code)
```

## 注意事项

1. **证书安全**: mitmproxy 证书仅用于测试环境，请勿在生产环境使用
2. **敏感信息**: 录制的请求头可能包含 Token 等敏感信息，请妥善保管
3. **文件命名**: 默认根据 HTTP 方法和路径生成文件名，相同路径会添加序号
