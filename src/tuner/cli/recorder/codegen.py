"""
API Model Code Generator

Convert recorded HTTP traffic to tuner APIModel definition code.
Directly references tuner.api.base.APIModel and tuner.api.body.* classes,
avoiding maintenance of independent model descriptions and reducing technical debt.
"""

import json
import re
from dataclasses import dataclass, field
from pprint import pformat
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass
class RecordedRequest:
    """Recorded request data."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body_content: bytes | None = None
    body_content_type: str | None = None


@dataclass
class RecordedResponse:
    """Recorded response data."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body_content: bytes | None = None


def _safe_identifier(name: str) -> str:
    """Convert a string to a valid Python identifier."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    safe = re.sub(r"^[0-9]+", "", safe)
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_")
    return safe or "api"


def _format_dict(d: dict[str, Any], indent: int = 8) -> str:
    """Format dict as multi-line Python code."""
    if not d:
        return "{}"

    lines = ["{"]
    for key, value in d.items():
        if isinstance(value, str):
            lines.append(f'{" " * indent}"{key}": "{value}",')
        elif isinstance(value, dict):
            nested = _format_dict(value, indent + 4)
            lines.append(f'{" " * indent}"{key}": {nested},')
        else:
            lines.append(f'{" " * indent}"{key}": {value!r},')
    lines.append(f"{' ' * (indent - 4)}}}")
    return "\n".join(lines)


def _format_dict_oneline(d: dict[str, Any]) -> str:
    """Format dict as single-line Python code."""
    if not d:
        return "{}"
    items = []
    for key, value in d.items():
        if isinstance(value, str):
            items.append(f'"{key}": "{value}"')
        else:
            items.append(f'"{key}": {value!r}')
    return "{" + ", ".join(items) + "}"


def _parse_json_body(content: bytes) -> tuple[str, str] | None:
    """Try to parse JSON body."""
    try:
        data = json.loads(content.decode("utf-8"))
        formatted = pformat(data, width=100, sort_dicts=False)
        return "JsonBody", f"JsonBody(\n        data={formatted}\n    )"
    except Exception:
        return None


def _parse_form_body(content: bytes) -> tuple[str, str] | None:
    """Try to parse form-urlencoded body."""
    try:
        text = content.decode("utf-8")
        parsed = parse_qs(text, keep_blank_values=True)
        data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        formatted = _format_dict_oneline(data)
        return "FormUrlencodedBody", f"FormUrlencodedBody(data={formatted})"
    except Exception:
        return None


def _parse_xml_body(content: bytes) -> tuple[str, str] | None:
    """Try to parse XML body."""
    try:
        text = content.decode("utf-8")
        return "XmlBody", f'XmlBody(content="""{text}""")'
    except Exception:
        return None


def _parse_text_body(content: bytes) -> tuple[str, str] | None:
    """Try to parse text body."""
    try:
        text = content.decode("utf-8")
        return "TextBody", f'TextBody(content="""{text}""")'
    except Exception:
        return None


def _parse_body(  # noqa: C901, PLR0911
    content: bytes | None, content_type: str | None
) -> tuple[str, str]:
    """
    Parse request body and return (body_import, body_code).

    Returns:
        body_import: Body class name to import (e.g., "JsonBody")
        body_code: Body instantiation code
    """
    if not content:
        return "NoneBody", "NoneBody()"

    ct = (content_type or "").lower()

    # JSON
    if "application/json" in ct:
        result = _parse_json_body(content)
        if result:
            return result

    # Form URL Encoded
    if "application/x-www-form-urlencoded" in ct:
        result = _parse_form_body(content)
        if result:
            return result

    # XML
    if "application/xml" in ct or "text/xml" in ct:
        result = _parse_xml_body(content)
        if result:
            return result

    # Plain text
    if "text/" in ct:
        result = _parse_text_body(content)
        if result:
            return result

    # Multipart form data (simplified)
    if "multipart/form-data" in ct:
        return "FormDataBody", "FormDataBody(fields={})  # TODO: parse multipart"

    # Unrecognized type
    return "NoneBody", "NoneBody()  # Unrecognized body type"


def _filter_headers(headers: dict[str, str]) -> dict[str, str]:
    """Filter out headers that don't need to be preserved."""
    skip_headers = {
        "host",
        "content-length",
        "connection",
        "proxy-connection",
        "accept-encoding",
        "transfer-encoding",
        "upgrade-insecure-requests",
    }
    return {k: v for k, v in headers.items() if k.lower() not in skip_headers}


def generate_api_name(method: str, path: str) -> str:
    """Generate API name from HTTP method and path.

    Uses full path segments joined by underscore for unique naming.
    """
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if not parts:
        return f"{method.lower()}_api"
    # Join all path segments with underscore for unique name
    path_name = "_".join(_safe_identifier(p) for p in parts)
    return f"{method.lower()}_{path_name}"


def _strip_prefix_from_path(full_path: str, url_prefix: str | None) -> str:
    """Strip URL prefix path from full path."""
    if not url_prefix:
        return full_path
    prefix_parsed = urlparse(url_prefix)
    prefix_path = prefix_parsed.path.rstrip("/")
    if full_path.startswith(prefix_path):
        path = full_path[len(prefix_path) :]
        return path if path.startswith("/") else "/" + path
    return full_path


def generate_apimodel_code(
    request: RecordedRequest,
    response: RecordedResponse | None = None,
    *,
    url_prefix: str | None = None,
    api_name: str | None = None,
    description: str | None = None,
    variable_name: str | None = None,
) -> str:
    """
    Generate APIModel definition code.

    Args:
        request: Recorded request data
        response: Recorded response data (optional, for comments)
        url_prefix: URL prefix used during recording (will be stripped from url)
        api_name: API name (optional, auto-generated)
        description: API description (optional)
        variable_name: Python variable name (optional, auto-generated)

    Returns:
        Complete Python module code
    """
    parsed = urlparse(request.url)
    path = _strip_prefix_from_path(parsed.path, url_prefix)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

    if not api_name:
        api_name = generate_api_name(request.method, path)
    if not variable_name:
        variable_name = _safe_identifier(api_name) + "_api"

    body_import, body_code = _parse_body(
        request.body_content, request.body_content_type
    )

    imports = ["from tuner.api.base import APIModel"]
    body_imports = {body_import}
    if body_imports != {"NoneBody"}:
        body_imports.add("NoneBody")
    imports.append(f"from tuner.api.body import {', '.join(sorted(body_imports))}")

    headers = _filter_headers(request.headers)

    lines = [
        '"""',
        f"API Model: {api_name}",
        f"Recorded from: {request.method} {request.url}",
    ]
    if response:
        lines.append(f"Response status: {response.status_code}")
    lines.append('"""')
    lines.append("")
    lines.extend(imports)
    lines.append("")
    lines.append("")
    lines.append(f"{variable_name} = APIModel(")
    lines.append(f'    name="{api_name}",')

    if description:
        lines.append(f'    description="{description}",')
    else:
        lines.append('    description="Recorded API model",')

    lines.append(f'    method="{request.method}",')
    lines.append(f'    url="{path}",')

    if params:
        params_str = _format_dict(params, indent=8)
        lines.append(f"    params={params_str},")

    if headers:
        headers_str = _format_dict(headers, indent=8)
        lines.append(f"    headers={headers_str},")

    if body_code != "NoneBody()":
        lines.append(f"    body={body_code},")

    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def generate_filename(method: str, path: str, url_prefix: str | None = None) -> str:
    """Generate Python filename.

    Args:
        method: HTTP method
        path: Full URL path
        url_prefix: URL prefix to strip from path

    Returns:
        Python filename like 'get_system_user_list.py'
    """
    relative_path = _strip_prefix_from_path(path, url_prefix)
    name = generate_api_name(method, relative_path)
    return f"{name}.py"
