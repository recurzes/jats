import pytest
from fastapi.testclient import TestClient

from app.config import Settings

DEV_ORIGIN = "http://localhost:5173"


def preflight(client: TestClient, origin: str, method: str = "POST"):
    return client.options(
        "/devices",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


@pytest.mark.parametrize("origin", [DEV_ORIGIN, "https://jats.example.com"])
def test_preflight_from_an_allowed_origin_succeeds(client: TestClient, origin: str) -> None:
    response = preflight(client, origin)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    allowed_methods = response.headers["access-control-allow-methods"]
    assert {"GET", "POST", "PATCH"} <= {method.strip() for method in allowed_methods.split(",")}


def test_preflight_from_another_origin_is_refused(client: TestClient) -> None:
    response = preflight(client, "https://evil.example.com")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_preflight_for_a_method_that_is_not_allowed_is_refused(client: TestClient) -> None:
    assert preflight(client, DEV_ORIGIN, method="DELETE").status_code == 400


def test_error_responses_carry_the_cors_header(client: TestClient) -> None:
    # Without it the browser hides the 401 body from the React app.
    response = client.post("/devices", json={"name": "x"}, headers={"Origin": DEV_ORIGIN})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_cors_origins_are_split_on_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://jats.example.com,")

    settings = Settings(_env_file=None)

    assert settings.cors_origin_list == ["http://localhost:5173", "https://jats.example.com"]
