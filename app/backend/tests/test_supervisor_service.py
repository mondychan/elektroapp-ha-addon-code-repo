import logging

from services.supervisor_service import SupervisorService


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {"result": "ok"}
        self.status_code = status_code
        self.content = b'{"result":"ok"}'

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse()


def test_supervisor_service_posts_self_options(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "token")
    session = FakeSession()
    service = SupervisorService(logger=logging.getLogger("test"))
    service.session = session

    result = service.sync_addon_options({"hp": {"enabled": True}})

    assert result["ok"] is True
    assert session.calls[0]["url"] == "http://supervisor/addons/self/options"
    assert session.calls[0]["json"] == {"options": {"hp": {"enabled": True}}}
    assert session.calls[0]["headers"]["Authorization"] == "Bearer token"


def test_supervisor_service_skips_without_token(monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    service = SupervisorService(logger=logging.getLogger("test"))

    result = service.sync_addon_options({"hp": {"enabled": True}})

    assert result["ok"] is False
    assert result["skipped"] is True


def test_supervisor_service_returns_detailed_http_error(monkeypatch):
    from services.supervisor_service import SupervisorSyncError

    monkeypatch.setenv("SUPERVISOR_TOKEN", "token")
    session = FakeSession()
    session.post = lambda *args, **kwargs: FakeResponse(
        payload={"result": "error", "message": "Invalid user input", "data": {"schema": "hp.entities[0].unit"}},
        status_code=400,
    )
    service = SupervisorService(logger=logging.getLogger("test"))
    service.session = session

    try:
        service.sync_addon_options({"hp": {"enabled": True}})
        assert False, "sync_addon_options was expected to raise SupervisorSyncError"
    except SupervisorSyncError as exc:
        assert exc.status_code == 400
        assert exc.detail["code"] == "supervisor_http_error"
        assert exc.detail["message"] == "Invalid user input"
