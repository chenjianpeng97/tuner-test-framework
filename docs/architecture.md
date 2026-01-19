# Tuner Test Framework 架构设计文档

## 1. 概述

Tuner Test Framework 是一个基于 Python 的自动化测试框架，集成了 API 测试和 UI 测试能力，支持数据驱动和模型化 API 管理。

## 2. 技术栈

| 组件       | 技术选型   | 说明                                           |
| ---------- | ---------- | ---------------------------------------------- |
| 用例驱动   | pytest     | Python 测试框架，支持参数化、fixture、插件扩展 |
| 浏览器驱动 | playwright | 现代化浏览器自动化工具，支持多浏览器           |
| 项目管理   | uv         | 快速的 Python 包管理器和项目管理工具           |

## 3. 项目结构

```
tuner-test-framework/
├── pyproject.toml          # uv 项目配置
├── README.md               # 项目说明
├── TODO                    # 开发任务清单
├── docs/                   # 设计文档
│   ├── architecture.md     # 架构设计文档
│   ├── api-model.md        # API 模型设计文档
│   └── tools.md            # 工具组件文档
├── src/
│   └── tuner/
│       ├── __init__.py
│       ├── api/            # API 模型管理
│       │   ├── __init__.py
│       │   ├── base.py     # API 基类
│       │   └── models/     # 具体 API 模型
│       ├── tools/          # 工具组件
│       │   ├── __init__.py
│       │   ├── excel.py    # Excel 处理工具
│       │   ├── sql.py      # SQL 处理工具
│       │   └── jsonpath.py # JSONPath 提取工具
│       ├── browser/        # 浏览器驱动封装
│       │   ├── __init__.py
│       │   └── driver.py   # Playwright 封装
│       └── config/         # 配置管理
│           ├── __init__.py
│           └── settings.py
├── tests/                  # 测试用例
│   ├── conftest.py         # pytest 配置和 fixtures
│   └── cases/              # 业务测试用例
│       └── test_list_export.py
└── data/                   # 测试数据
    ├── api/                # API 请求数据
    └── expected/           # 预期结果数据
```

## 4. 核心模块

### 4.1 API 模型管理 (`src/tuner/api/`)

- 统一的 API 请求封装
- 支持 API 模型定义（请求方法、URL、Headers、Body 模板）
- 支持请求/响应的日志记录
- 支持会话管理和登录态复用

### 4.2 工具组件 (`src/tuner/tools/`)

- **Excel 工具**: 读取/写入 Excel 文件，支持数据比对
- **SQL 工具**: 数据库连接和查询操作
- **JSONPath 工具**: 从 JSON 响应中提取数据进行断言

### 4.3 浏览器驱动 (`src/tuner/browser/`)

- Playwright 浏览器封装
- 支持复用 API 测试的登录态（Cookie/Token）
- 截图功能封装

### 4.4 配置管理 (`src/tuner/config/`)

- 环境配置（测试/预发/生产）
- 数据库连接配置
- API Base URL 配置

## 5. 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        pytest 用例执行                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. conftest.py 初始化                                           │
│     ├── 加载配置                                                  │
│     ├── 初始化数据库连接                                          │
│     └── 初始化 API Session                                       │
│                                                                   │
│  2. 测试用例执行                                                  │
│     ├── SQL 工具查询测试数据                                      │
│     ├── API 模型发起请求                                          │
│     ├── JSONPath 提取响应数据                                     │
│     ├── Excel 工具读取/验证导出文件                               │
│     └── 断言验证                                                  │
│                                                                   │
│  3. UI 验证（可选）                                               │
│     ├── 复用 API 登录态                                          │
│     ├── Playwright 打开页面                                       │
│     └── 截图保存                                                  │
│                                                                   │
│  4. 报告生成                                                      │
│     └── pytest 生成测试报告                                       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 6. 登录态复用机制

API 测试完成登录后，将登录态（Cookies/Token）传递给 Playwright：

```python
# 伪代码示例
api_session = APISession()
api_session.login(username, password)

# 复用到 Playwright
browser_context = playwright.new_context(
    storage_state=api_session.get_storage_state()
)
```

## 7. 依赖包

```
pytest>=8.0.0
playwright>=1.40.0
openpyxl>=3.1.0          # Excel 处理
pymysql>=1.1.0           # MySQL 数据库
jsonpath-ng>=1.6.0       # JSONPath 解析
pydantic>=2.0.0          # 数据模型验证
httpx>=0.27.0            # HTTP 客户端
python-dotenv>=1.0.0     # 环境变量管理
```
