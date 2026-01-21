"""
Unit tests for CLI recorder code generation.
"""

from tuner.cli.recorder.codegen import (
    RecordedRequest,
    RecordedResponse,
    generate_api_name,
    generate_apimodel_code,
    generate_filename,
)


class TestGenerateApiName:
    """Tests for generate_api_name function."""

    def test_simple_path(self):
        name = generate_api_name("GET", "/api/v1/users")
        assert name == "get_users"

    def test_post_method(self):
        name = generate_api_name("POST", "/api/users")
        assert name == "post_users"

    def test_path_with_param(self):
        name = generate_api_name("GET", "/api/users/{id}")
        assert name == "get_users"

    def test_empty_path(self):
        name = generate_api_name("GET", "/")
        assert name == "get_api"


class TestGenerateFilename:
    """Tests for generate_filename function."""

    def test_generates_py_file(self):
        filename = generate_filename("GET", "/api/users")
        assert filename == "get_users.py"

    def test_post_method(self):
        filename = generate_filename("POST", "/api/v1/products")
        assert filename == "post_products.py"


class TestGenerateApiModelCode:
    """Tests for generate_apimodel_code function."""

    def test_simple_get_request(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users",
            headers={"Accept": "application/json"},
        )

        code = generate_apimodel_code(request)

        # Check imports
        assert "from tuner.api.base import APIModel" in code
        assert "from tuner.api.body import" in code

        # Check model definition
        assert 'method="GET"' in code
        assert 'url="/api/users"' in code
        assert "get_users_api = APIModel(" in code

    def test_post_with_json_body(self):
        request = RecordedRequest(
            method="POST",
            url="http://example.com/api/users",
            headers={"Content-Type": "application/json"},
            body_content=b'{"name": "test", "age": 25}',
            body_content_type="application/json",
        )

        code = generate_apimodel_code(request)

        assert "JsonBody" in code
        assert 'method="POST"' in code
        assert "body=JsonBody" in code

    def test_with_query_params(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users?page=1&size=10",
            headers={},
        )

        code = generate_apimodel_code(request)

        assert "params=" in code
        assert '"page"' in code
        assert '"size"' in code

    def test_with_response(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users",
            headers={},
        )
        response = RecordedResponse(
            status_code=200,
            headers={},
        )

        code = generate_apimodel_code(request, response)

        assert "Response status: 200" in code

    def test_custom_api_name(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users",
            headers={},
        )

        code = generate_apimodel_code(request, api_name="list_all_users")

        assert "list_all_users_api = APIModel(" in code
        assert 'name="list_all_users"' in code

    def test_custom_variable_name(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users",
            headers={},
        )

        code = generate_apimodel_code(request, variable_name="my_api")

        assert "my_api = APIModel(" in code

    def test_filters_connection_headers(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api/users",
            headers={
                "Host": "example.com",
                "Connection": "keep-alive",
                "Accept": "application/json",
                "Content-Length": "100",
            },
        )

        code = generate_apimodel_code(request)

        # Should be filtered out
        assert '"Host"' not in code
        assert '"Connection"' not in code
        assert '"Content-Length"' not in code

        # Should be kept
        assert '"Accept"' in code


class TestBodyParsing:
    """Tests for body parsing in code generation."""

    def test_form_urlencoded_body(self):
        request = RecordedRequest(
            method="POST",
            url="http://example.com/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body_content=b"username=test&password=secret",
            body_content_type="application/x-www-form-urlencoded",
        )

        code = generate_apimodel_code(request)

        assert "FormUrlencodedBody" in code

    def test_text_body(self):
        request = RecordedRequest(
            method="POST",
            url="http://example.com/text",
            headers={"Content-Type": "text/plain"},
            body_content=b"Hello World",
            body_content_type="text/plain",
        )

        code = generate_apimodel_code(request)

        assert "TextBody" in code

    def test_xml_body(self):
        request = RecordedRequest(
            method="POST",
            url="http://example.com/xml",
            headers={"Content-Type": "application/xml"},
            body_content=b"<root><item>test</item></root>",
            body_content_type="application/xml",
        )

        code = generate_apimodel_code(request)

        assert "XmlBody" in code

    def test_no_body(self):
        request = RecordedRequest(
            method="GET",
            url="http://example.com/api",
            headers={},
            body_content=None,
        )

        code = generate_apimodel_code(request)

        # NoneBody should not be explicitly set (it's the default)
        assert "body=NoneBody()" not in code
