# 测试用例设计文档

## 1. 概述

本文档描述第一个测试用例 "list&export 权限验证并截图" 的详细设计。

## 2. 用例信息

| 字段     | 内容                       |
| -------- | -------------------------- |
| 用例名称 | list&export 权限验证并截图 |
| 用例 ID  | TC_USER_LIST_EXPORT_001    |
| 优先级   | P0                         |
| 测试类型 | API + UI                   |

## 3. 测试场景

验证用户列表和导出功能的权限控制及数据正确性，并通过截图留存测试证据。

## 4. 前置条件

1. 测试环境数据库已准备好测试用户数据
2. 测试账号已配置相应权限
3. API 服务正常运行
4. 导出功能可正常使用

## 5. 测试步骤

### Step 1: 获取数据库用户列表

**工具**: SQL 工具

```python
# 查询数据库获取预期用户数据
sql = """
    SELECT id, username, email, status, created_at
    FROM users
    WHERE status = 'active'
    ORDER BY id
    LIMIT 20
"""
expected_users = sql_tool.query(sql)
```

**预期结果**: 成功获取用户列表数据

### Step 2: 调用 List API

**工具**: API 模型管理

```python
# 调用用户列表接口
user_list_api = UserListAPI(api_session.client)
list_response = user_list_api.list_users(page=1, page_size=20)
```

**预期结果**:

- HTTP Status Code: 200
- Response Body 包含用户列表数据

### Step 3: 验证 List API 响应

**工具**: JSONPath 提取

```python
jp = JSONPathTool(list_response.body)

# 验证响应结构
assert jp.extract("$.code") == 0
assert jp.exists("$.data.users")

# 验证数据条数
actual_count = jp.count("$.data.users[*]")
assert actual_count == len(expected_users)

# 验证数据内容
actual_users = jp.extract_all("$.data.users[*]")
for i, user in enumerate(actual_users):
    assert user["username"] == expected_users[i]["username"]
```

**预期结果**: API 返回数据与数据库数据一致

### Step 4: 调用 Export API

**工具**: API 模型管理

```python
# 调用导出接口
export_api = UserExportAPI(api_session.client)
export_response = export_api.export_users(format="xlsx")

# 获取下载链接并下载文件
download_url = JSONPathTool(export_response.body).extract("$.data.downloadUrl")
# ... 下载文件 ...
```

**预期结果**:

- HTTP Status Code: 200
- 返回有效的下载链接

### Step 5: 验证导出 Excel 文件

**工具**: Excel 工具

```python
# 读取导出的 Excel 文件
excel = ExcelTool().load(Path("downloads/users_export.xlsx"))
excel_data = excel.read_sheet(sheet_name="用户列表")

# 验证数据
assert len(excel_data) == len(expected_users)

for i, row in enumerate(excel_data):
    assert row["用户名"] == expected_users[i]["username"]
    assert row["邮箱"] == expected_users[i]["email"]
    assert row["状态"] == expected_users[i]["status"]
```

**预期结果**: Excel 数据与数据库数据一致

### Step 6: 页面截图

**工具**: Playwright

```python
# 复用 API 登录态
browser = playwright.chromium.launch()
context = browser.new_context(
    storage_state=api_session.get_storage_state()
)
page = context.new_page()

# 访问用户列表页面
page.goto(f"{base_url}/users")
page.wait_for_load_state("networkidle")

# 截图保存
screenshot_path = Path(f"screenshots/user_list_{timestamp}.png")
page.screenshot(path=screenshot_path, full_page=True)

# 关闭浏览器
browser.close()
```

**预期结果**: 成功截图并保存

## 6. 完整测试代码

```python
# tests/cases/test_list_export.py

import pytest
from pathlib import Path
from datetime import datetime

from tuner.api.models.user import UserListAPI, UserExportAPI
from tuner.tools.sql import SQLTool
from tuner.tools.excel import ExcelTool
from tuner.tools.jsonpath import JSONPathTool


class TestUserListExport:
    """用户列表与导出功能测试"""

    @pytest.fixture(autouse=True)
    def setup(self, sql_tool, api_session, browser_context):
        """测试前置"""
        self.sql_tool = sql_tool
        self.api_session = api_session
        self.browser_context = browser_context

    def test_list_export_with_screenshot(self):
        """list&export 权限验证并截图"""

        # Step 1: 查询数据库
        expected_users = self.sql_tool.query(
            "SELECT * FROM users WHERE status = 'active' ORDER BY id LIMIT 20"
        )

        # Step 2: 调用 List API
        list_api = UserListAPI(self.api_session.client)
        list_response = list_api.list_users(page=1, page_size=20)

        assert list_response.status_code == 200

        # Step 3: JSONPath 验证
        jp = JSONPathTool(list_response.body)
        assert jp.extract("$.code") == 0

        actual_users = jp.extract_all("$.data.users[*]")
        assert len(actual_users) == len(expected_users)

        # Step 4: 调用 Export API
        export_api = UserExportAPI(self.api_session.client)
        export_response = export_api.export_users()

        assert export_response.status_code == 200

        # Step 5: 验证 Excel
        download_url = JSONPathTool(export_response.body).extract("$.data.downloadUrl")
        # 下载文件逻辑...

        excel = ExcelTool().load(Path("downloads/export.xlsx"))
        excel_data = excel.read_sheet()

        assert len(excel_data) == len(expected_users)

        # Step 6: 截图
        page = self.browser_context.new_page()
        page.goto("/users")
        page.wait_for_load_state("networkidle")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        page.screenshot(
            path=f"screenshots/user_list_{timestamp}.png",
            full_page=True
        )
```

## 7. 数据依赖

| 数据类型 | 来源           | 说明               |
| -------- | -------------- | ------------------ |
| 用户数据 | MySQL 数据库   | users 表           |
| API 配置 | 环境配置       | base_url, 登录凭证 |
| 预期结果 | 数据库实时查询 | 动态获取           |

## 8. 测试报告

测试完成后生成的产物：

1. pytest 测试报告 (HTML/XML)
2. 截图文件 (`screenshots/user_list_*.png`)
3. 日志文件
