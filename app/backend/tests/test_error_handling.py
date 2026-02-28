import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from errors import ApiError, register_error_handling


def build_test_app():
    app = FastAPI()
    register_error_handling(app, logging.getLogger("test.errors"))

    @app.get("/http")
    def raise_http():
        raise HTTPException(status_code=400, detail="Bad input")

    @app.get("/api")
    def raise_api():
        raise ApiError(status_code=409, code="CONFLICT_TEST", message="Conflict happened", detail={"field": "x"})

    @app.get("/crash")
    def raise_crash():
        raise RuntimeError("boom")

    @app.get("/items/{item_id}")
    def item(item_id: int):
        return {"item_id": item_id}

    return app


def test_http_exception_is_wrapped_with_code():
    client = TestClient(build_test_app())
    resp = client.get("/http")

    assert resp.status_code == 400
    payload = resp.json()["error"]
    assert payload["code"] == "BAD_REQUEST"
    assert payload["message"] == "Bad input"
    assert payload.get("request_id")
    assert resp.headers.get("X-Request-ID")


def test_custom_api_error_preserves_code_message_and_detail():
    client = TestClient(build_test_app())
    resp = client.get("/api")

    assert resp.status_code == 409
    payload = resp.json()["error"]
    assert payload["code"] == "CONFLICT_TEST"
    assert payload["message"] == "Conflict happened"
    assert payload["detail"] == {"field": "x"}


def test_validation_error_uses_unified_format():
    client = TestClient(build_test_app())
    resp = client.get("/items/not-an-int")

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Request validation failed."
    assert isinstance(payload["detail"], list)


def test_unhandled_error_uses_internal_error_code():
    client = TestClient(build_test_app(), raise_server_exceptions=False)
    resp = client.get("/crash")

    assert resp.status_code == 500
    payload = resp.json()["error"]
    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["message"] == "Unexpected internal error."
