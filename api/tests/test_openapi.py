import json

from fastapi.routing import APIRoute

from app.main import app
from scripts.export_openapi import CONTRACT

METHODS = {"get", "post", "patch", "put", "delete"}


def operations() -> list[tuple[str, dict]]:
    return [
        (f"{method.upper()} {path}", operation)
        for path, item in app.openapi()["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    ]


def test_the_committed_contract_is_up_to_date() -> None:
    # If this fails, run: python -m scripts.export_openapi
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == app.openapi()


def test_every_route_has_a_tag_and_a_summary() -> None:
    for name, operation in operations():
        assert operation.get("tags"), name
        assert operation.get("summary"), name


def test_every_json_route_has_a_response_model() -> None:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path != "/auth/google/callback":
            assert route.response_model is not None, route.path


def test_every_error_response_has_the_error_shape() -> None:
    document = app.openapi()
    # FastAPI's own validation error body is never sent: the handlers answer with ours.
    assert "HTTPValidationError" not in document["components"]["schemas"]
    error = {"$ref": "#/components/schemas/ErrorResponse"}
    for name, operation in operations():
        errors = {code: r for code, r in operation["responses"].items() if code[0] in "45"}
        assert errors or name == "GET /health", name
        for code, response in errors.items():
            assert response["content"]["application/json"]["schema"] == error, (name, code)


def test_the_error_shape_is_documented() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["ErrorResponse"]["required"] == ["error"]
    assert schemas["ErrorDetail"]["required"] == ["code", "message"]
