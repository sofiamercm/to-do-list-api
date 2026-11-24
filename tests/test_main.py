"""Unit tests for to-do-list-api. The database is replaced with mocks."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Let the tests import main.py from the src/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import app  # noqa: E402

client = TestClient(app)


def test_version(monkeypatch):
    """/version returns whatever APP_VERSION says."""
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3"}


def test_health_ok(monkeypatch):
    """/health reports OK when the database connection works."""
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    with patch("main.get_connection", return_value=MagicMock()):
        response = client.get("/health")
    body = response.json()
    assert response.status_code == 200
    assert body["database"] == "OK"
    assert body["version"] == "1.2.3"
    assert "timestamp" in body


def test_health_fail():
    """/health reports FAIL (and does not crash) when the database is down."""
    with patch("main.get_connection", side_effect=Exception("db down")):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "FAIL"


def test_create_task():
    """POST /tasks saves the task and returns it with the id from the database."""
    fake_conn = MagicMock()
    fake_cursor = fake_conn.cursor.return_value.__enter__.return_value
    fake_cursor.fetchone.return_value = (7,)

    with patch("main.get_connection", return_value=fake_conn):
        response = client.post("/tasks", json={"title": "Buy milk", "completed": False})

    assert response.status_code == 201
    assert response.json() == {"id": 7, "title": "Buy milk", "completed": False}
    fake_cursor.execute.assert_called_once()
    fake_conn.commit.assert_called_once()