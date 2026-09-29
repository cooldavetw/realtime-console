"""Local transport and static hosting tests; no provider credentials required."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main
from backend.core.conversation_store import ConversationStore


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    from backend.core import session

    database = tmp_path / "conversations.db"
    monkeypatch.setattr(session, "ConversationStore", lambda: ConversationStore(database))
    monkeypatch.setattr(main, "setup_logging", lambda: None)
    return main.create_app, database


def test_static_hosting_and_route_precedence(app_factory, tmp_path):
    create_app, _ = app_factory
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<html>Console</html>")
    (build / "app.js").write_text("console.log('console');")
    with TestClient(create_app(build)) as client:
        assert client.get("/").text == "<html>Console</html>"
        assert client.get("/app.js").status_code == 200
        assert client.get("/missing.js").status_code == 404
        navigation = client.get("/conversation/example", headers={"Accept": "text/html"})
        assert navigation.status_code == 200
        assert navigation.text == "<html>Console</html>"
        assert client.get("/conversation/example", headers={"Accept": "application/json"}).status_code == 404
        assert client.get("/health").json() == {"status": "ok"}
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "session.created"


def test_missing_frontend_keeps_api_available(app_factory, tmp_path):
    create_app, _ = app_factory
    with TestClient(create_app(tmp_path / "missing")) as client:
        assert client.get("/").status_code == 503
        assert client.get("/health").status_code == 200


def test_websocket_events_and_disconnect_cleanup(app_factory, tmp_path):
    create_app, database = app_factory
    app = create_app(tmp_path / "missing")
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            created = ws.receive_json()
            assert created["type"] == "session.created"
            session_id = created["session_id"]
            assert session_id in app.state.websocket_handler.session_manager.sessions
            ws.send_text("invalid json")
            assert ws.receive_json()["code"] == "invalid_json"
            ws.send_json({})
            assert ws.receive_json()["code"] == "missing_event_type"
            ws.send_json({"type": "session.update", "config": {"mode": "push_to_talk"}})
            assert ws.receive_json()["type"] == "session.updated"
    assert app.state.websocket_handler.session_manager.sessions == {}
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
