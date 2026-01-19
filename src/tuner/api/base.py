"""
API 模型和执行器核心模块
"""

import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from tuner.api.auth import Auth, NoAuth
from tuner.api.body import (
    Body,
    BodyType,
    FormDataBody,
    FormUrlencodedBody,
    JsonBody,
    NoneBody,
    TextBody,
    XmlBody,
)
from tuner.api.environment import EnvironmentManager
from tuner.api.operations import Operation, OperationContext
from tuner.api.response import APIResponse
from tuner.util.log import get_logger


class APIModel(BaseModel):
    """API 模型定义"""

    # 基本属性
    name: str = ""  # API 名称
    description: str = ""  # API 描述
    method: str = "GET"  # HTTP 方法
    url: str  # API 路径
    url_prefix: str | None = None  # URL 前缀（优先于环境配置）

    # 请求参数
    params: dict[str, Any] = {}  # Query 参数
    body: Body = NoneBody()  # 请求体
    headers: dict[str, str] = {}  # 请求头
    cookies: dict[str, str] = {}  # Cookies

    # 认证
    auth: Auth = NoAuth()  # 认证配置

    # 前置/后置操作
    pre_request: list[Operation] = []  # 前置操作
    post_request: list[Operation] = []  # 后置操作

    # 超时配置
    timeout: float = 30.0  # 超时时间（秒）

    model_config = {"arbitrary_types_allowed": True}


class APIExecutor:
    """API 执行器"""

    def __init__(self, client: httpx.Client | None = None):
        self._client = client
        self._owns_client = client is None
        self.context = OperationContext()
        self._log = get_logger("APIExecutor")

    @staticmethod
    def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
        sensitive = {"authorization", "cookie", "set-cookie", "x-api-key"}
        redacted: dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in sensitive:
                redacted[key] = "***"
            else:
                redacted[key] = value
        return redacted

    @staticmethod
    def _truncate(value: str, *, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "…(truncated)"

    @classmethod
    def _deep_merge_dict(
        cls, base: dict[str, Any], updates: dict[str, Any]
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {**base}
        for key, value in updates.items():
            existing = merged.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                merged[key] = cls._deep_merge_dict(existing, value)
            else:
                merged[key] = value
        return merged

    @property
    def client(self) -> httpx.Client:
        """懒加载 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    def execute(
        self,
        api: APIModel,
        path_params: dict[str, Any] | None = None,
        extra_params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        update_body: dict[str, Any] | None = None,
        override_body: Body | None = None,
    ) -> APIResponse:
        """
        执行 API 请求

        Args:
            api: API 模型
            path_params: 路径参数，用于替换 URL 中的 {param}
            extra_params: 额外的 Query 参数（会合并/覆盖默认值）
            extra_headers: 额外的请求头（会合并/覆盖默认值）
            update_body: 更新请求体（保留默认字段；目前仅支持 JSON Body）
            override_body: 覆盖请求体

        Returns:
            APIResponse: 响应对象
        """
        # 1. 执行前置操作
        self._run_operations(api.pre_request)

        # 2. 构建并发送请求
        response = self._send_request(
            api, path_params, extra_params, extra_headers, update_body, override_body
        )

        # 3. 更新上下文（供后置操作使用）
        self.context.response = response.body if isinstance(response.body, dict) else {}

        # 4. 执行后置操作
        self._run_operations(api.post_request)

        return response

    def _send_request(
        self,
        api: APIModel,
        path_params: dict[str, Any] | None,
        extra_params: dict[str, Any] | None,
        extra_headers: dict[str, str] | None,
        update_body: dict[str, Any] | None,
        override_body: Body | None,
    ) -> APIResponse:
        """构建并发送 HTTP 请求"""
        # URL 处理
        url_prefix = api.url_prefix or EnvironmentManager.get_url_prefix()
        url = api.url.format(**(path_params or {}))
        full_url = f"{url_prefix}{url}"

        # 合并参数
        params = {**api.params, **(extra_params or {})}

        # 合并请求头：先应用 API 默认 headers，再应用 auth，最后应用 extra_headers
        # 这样 extra_headers 可以覆盖 auth 设置的值
        headers = {**api.headers}
        headers = api.auth.apply_to_headers(headers)
        if extra_headers:
            headers = {**headers, **extra_headers}

        # 处理 Body
        body = override_body or api.body

        if update_body:
            if body.type == BodyType.JSON and isinstance(body, JsonBody):
                body = JsonBody(data=self._deep_merge_dict(body.data, update_body))
            # TODO: support update_body for other body types when needed.

        content, json_data, data, files, content_type = self._prepare_body(body)

        if content_type and "Content-Type" not in headers:
            headers["Content-Type"] = content_type

        if body.type == BodyType.JSON and isinstance(body, JsonBody):
            self._log.debug(
                "Request body (json): {body}",
                body=self._truncate(json.dumps(json_data or {}, ensure_ascii=False)),
            )
        # TODO: support logging for other body types (TEXT/XML/FORM/FILES) when needed.

        self._log.debug(
            "Sending request: {method} {url} params={params} headers={headers}",
            method=api.method,
            url=full_url,
            params=params,
            headers=self._redact_headers(headers),
        )

        # 发送请求
        try:
            response = self.client.request(
                method=api.method,
                url=full_url,
                params=params if params else None,
                headers=headers if headers else None,
                cookies=api.cookies if api.cookies else None,
                content=content,
                json=json_data,
                data=data,
                files=files,
                timeout=api.timeout,
            )
        except httpx.RequestError as e:
            # 网络错误时返回特殊响应
            self._log.warning(
                "Request failed: {method} {url} error={error}",
                method=api.method,
                url=full_url,
                error=str(e),
            )
            return APIResponse(
                status_code=0,
                headers={},
                cookies={},
                body={"error": str(e)},
                elapsed=0.0,
                raw_text=str(e),
            )

        # 解析响应体
        try:
            response_body = response.json()
        except Exception:
            response_body = None

        content_type_resp = response.headers.get("content-type")
        body_preview: Any
        if isinstance(response_body, (dict, list)):
            body_preview = response_body
        else:
            body_preview = self._truncate(response.text)

        self._log.debug(
            "Received response: {status_code} in {elapsed:.3f}s content-type={content_type} body={body}",
            status_code=response.status_code,
            elapsed=response.elapsed.total_seconds(),
            content_type=content_type_resp,
            body=body_preview,
        )

        return APIResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            cookies=dict(response.cookies),
            body=response_body,
            elapsed=response.elapsed.total_seconds(),
            raw_text=response.text,
        )

    def _prepare_body(
        self, body: Body
    ) -> tuple[
        bytes | str | None,  # content
        dict[str, Any] | None,  # json
        dict[str, Any] | None,  # data (form)
        dict[str, Any] | None,  # files
        str | None,  # content_type
    ]:
        """准备请求体"""
        if body.type == BodyType.NONE:
            return None, None, None, None, None

        if body.type == BodyType.JSON:
            json_body = body
            if isinstance(json_body, JsonBody):
                return None, json_body.data, None, None, "application/json"

        if body.type == BodyType.TEXT:
            text_body = body
            if isinstance(text_body, TextBody):
                return text_body.content, None, None, None, text_body.content_type

        if body.type == BodyType.XML:
            xml_body = body
            if isinstance(xml_body, XmlBody):
                return xml_body.content, None, None, None, "application/xml"

        if body.type == BodyType.FORM_URLENCODED:
            form_body = body
            if isinstance(form_body, FormUrlencodedBody):
                return (
                    None,
                    None,
                    form_body.data,
                    None,
                    "application/x-www-form-urlencoded",
                )

        if body.type == BodyType.FORM_DATA:
            form_data_body = body
            if isinstance(form_data_body, FormDataBody):
                files = None
                if form_data_body.files:
                    files = {}
                    for field_name, file_path in form_data_body.files.items():
                        path = Path(file_path)
                        if path.exists():
                            files[field_name] = (
                                path.name,
                                path.read_bytes(),
                            )
                return None, None, form_data_body.fields, files, None

        return None, None, None, None, None

    def _run_operations(self, operations: list[Operation]) -> None:
        """执行操作列表"""
        for op in operations:
            if op.enabled:
                self.context = op.execute(self.context)

    def get_variable(self, name: str) -> Any:
        """获取上下文变量"""
        return self.context.variables.get(name)

    def set_variable(self, name: str, value: Any) -> None:
        """设置上下文变量"""
        self.context.variables[name] = value

    def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client and self._owns_client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "APIExecutor":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
