"""
请求体类型模块
支持 JSON、Text、FormData 等多种 Body 类型
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class BodyType(str, Enum):
    """Body 类型枚举"""

    NONE = "none"  # 无 Body
    JSON = "json"  # JSON 格式
    TEXT = "text"  # 纯文本
    FORM_DATA = "form-data"  # 表单数据
    FORM_URLENCODED = "x-www-form-urlencoded"  # URL 编码表单
    BINARY = "binary"  # 二进制文件
    XML = "xml"  # XML 格式


class Body(BaseModel):
    """Body 基类"""

    type: BodyType = BodyType.NONE


class NoneBody(Body):
    """无 Body"""

    type: BodyType = BodyType.NONE


class JsonBody(Body):
    """JSON Body"""

    type: BodyType = BodyType.JSON
    data: dict[str, Any]


class TextBody(Body):
    """文本 Body"""

    type: BodyType = BodyType.TEXT
    content: str
    content_type: str = "text/plain"


class FormDataBody(Body):
    """表单 Body (multipart/form-data)"""

    type: BodyType = BodyType.FORM_DATA
    fields: dict[str, Any]
    files: dict[str, str] | None = None  # 文件字段: 文件路径映射


class FormUrlencodedBody(Body):
    """URL 编码表单 Body"""

    type: BodyType = BodyType.FORM_URLENCODED
    data: dict[str, str]


class XmlBody(Body):
    """XML Body"""

    type: BodyType = BodyType.XML
    content: str
