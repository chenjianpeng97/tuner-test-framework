# 工具组件设计文档

## 1. 概述

工具组件提供测试过程中常用的数据处理能力，包括 Excel 处理、SQL 查询和 JSONPath 数据提取。

## 2. Excel 工具

### 2.1 功能列表

- 读取 Excel 文件内容
- 写入 Excel 文件
- Excel 数据比对
- 支持多 Sheet 操作
- 支持导出文件验证

### 2.2 接口设计

```python
# src/tuner/tools/excel.py

from pathlib import Path
from typing import List, Dict, Any, Optional
from openpyxl import load_workbook, Workbook

class ExcelTool:
    """Excel 处理工具"""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path
        self._workbook = None

    def load(self, file_path: Path) -> "ExcelTool":
        """加载 Excel 文件"""
        self.file_path = file_path
        self._workbook = load_workbook(file_path)
        return self

    def read_sheet(
        self,
        sheet_name: Optional[str] = None,
        header_row: int = 1,
        start_row: int = 2
    ) -> List[Dict[str, Any]]:
        """
        读取 Sheet 数据为字典列表

        Args:
            sheet_name: Sheet 名称，默认为活动 Sheet
            header_row: 表头行号
            start_row: 数据起始行号

        Returns:
            List[Dict]: 每行数据为一个字典
        """
        pass

    def read_cell(
        self,
        row: int,
        col: int,
        sheet_name: Optional[str] = None
    ) -> Any:
        """读取单元格值"""
        pass

    def write_sheet(
        self,
        data: List[Dict[str, Any]],
        sheet_name: str = "Sheet1",
        header_row: int = 1
    ) -> "ExcelTool":
        """写入数据到 Sheet"""
        pass

    def save(self, file_path: Optional[Path] = None):
        """保存文件"""
        pass

    def compare(
        self,
        other: "ExcelTool",
        sheet_name: Optional[str] = None,
        ignore_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        比对两个 Excel 文件

        Returns:
            {
                "is_equal": bool,
                "differences": [
                    {"row": 1, "column": "A", "expected": "x", "actual": "y"}
                ]
            }
        """
        pass
```

### 2.3 使用示例

```python
# 读取导出文件并验证
excel = ExcelTool().load(Path("exports/users.xlsx"))
data = excel.read_sheet(sheet_name="用户列表")

assert len(data) == expected_count
assert data[0]["用户名"] == "admin"
```

## 3. SQL 工具

### 3.1 功能列表

- 数据库连接管理
- 执行 SELECT 查询
- 执行 INSERT/UPDATE/DELETE
- 事务支持
- 连接池管理

### 3.2 接口设计

```python
# src/tuner/tools/sql.py

from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import pymysql
from pymysql.cursors import DictCursor

class DatabaseConfig:
    """数据库配置"""
    host: str
    port: int = 3306
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

class SQLTool:
    """SQL 处理工具"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None

    def connect(self) -> "SQLTool":
        """建立数据库连接"""
        self._connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.config.charset,
            cursorclass=DictCursor
        )
        return self

    def query(
        self,
        sql: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        执行查询语句

        Args:
            sql: SQL 语句，支持参数化 %s
            params: 参数元组

        Returns:
            查询结果列表
        """
        pass

    def execute(
        self,
        sql: str,
        params: Optional[tuple] = None
    ) -> int:
        """
        执行非查询语句

        Returns:
            affected_rows: 影响行数
        """
        pass

    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        try:
            yield
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
```

### 3.3 使用示例

```python
# 查询用户数据用于断言
sql_tool = SQLTool(db_config).connect()

users = sql_tool.query(
    "SELECT * FROM users WHERE status = %s LIMIT %s",
    ("active", 10)
)

assert len(users) == 10
```

## 4. JSONPath 工具

### 4.1 功能列表

- 从 JSON 数据中提取值
- 支持 JSONPath 表达式
- 支持多值提取
- 支持默认值

### 4.2 接口设计

```python
# src/tuner/tools/jsonpath.py

from typing import Any, List, Optional
from jsonpath_ng import parse
from jsonpath_ng.exceptions import JsonPathParserError

class JSONPathTool:
    """JSONPath 提取工具"""

    def __init__(self, data: Optional[dict] = None):
        self.data = data

    def load(self, data: dict) -> "JSONPathTool":
        """加载 JSON 数据"""
        self.data = data
        return self

    def extract(
        self,
        path: str,
        default: Any = None
    ) -> Any:
        """
        提取单个值

        Args:
            path: JSONPath 表达式，如 "$.data.users[0].name"
            default: 未找到时的默认值

        Returns:
            提取的值或默认值
        """
        pass

    def extract_all(
        self,
        path: str
    ) -> List[Any]:
        """
        提取所有匹配的值

        Args:
            path: JSONPath 表达式，如 "$.data.users[*].name"

        Returns:
            所有匹配值的列表
        """
        pass

    def exists(self, path: str) -> bool:
        """检查路径是否存在"""
        pass

    def count(self, path: str) -> int:
        """统计匹配数量"""
        pass
```

### 4.3 常用 JSONPath 表达式

| 表达式                        | 说明             |
| ----------------------------- | ---------------- |
| `$.store.book[0].title`       | 第一本书的标题   |
| `$.store.book[*].author`      | 所有书的作者     |
| `$..author`                   | 所有 author 字段 |
| `$.store.book[?(@.price<10)]` | 价格小于 10 的书 |
| `$.store.book[0,1]`           | 第一和第二本书   |
| `$.store.book[-1:]`           | 最后一本书       |

### 4.4 使用示例

```python
# 从 API 响应中提取数据
response_body = {
    "code": 0,
    "data": {
        "total": 100,
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"}
        ]
    }
}

jp = JSONPathTool(response_body)

# 提取总数
total = jp.extract("$.data.total")
assert total == 100

# 提取所有用户名
names = jp.extract_all("$.data.users[*].name")
assert names == ["Alice", "Bob"]

# 提取第一个用户
first_user = jp.extract("$.data.users[0]")
assert first_user["name"] == "Alice"
```

## 5. 工具整合使用

```python
# 在测试用例中组合使用工具
def test_export_data_consistency(sql_tool, api_session, excel_tool):
    """验证导出数据与数据库一致性"""

    # 1. 从数据库获取预期数据
    db_users = sql_tool.query("SELECT * FROM users WHERE status = 'active'")

    # 2. 调用导出 API
    export_api = UserExportAPI(api_session.client)
    response = export_api.export_users()

    # 3. 使用 JSONPath 提取下载链接
    jp = JSONPathTool(response.body)
    download_url = jp.extract("$.data.downloadUrl")

    # 4. 下载并读取 Excel 文件
    # ... 下载文件逻辑 ...
    excel_data = excel_tool.load(Path("downloads/export.xlsx")).read_sheet()

    # 5. 比对数据
    assert len(excel_data) == len(db_users)
    for i, row in enumerate(excel_data):
        assert row["用户名"] == db_users[i]["username"]
```
