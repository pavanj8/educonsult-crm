"""Verify DATABASE_OVERRIDE startup creates schema for Test Agent scratch DBs."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_login_unknown_user_returns_401_with_database_override(tmp_path):
    """Mirrors Test Agent scratch DB: empty sqlite file + DATABASE_OVERRIDE."""
    db_path = tmp_path / "qa_scratch.db"
    env = {
        **os.environ,
        "DATABASE_OVERRIDE": f"sqlite:///{db_path}",
        "PYTHONPATH": str(BACKEND_ROOT),
    }

    script = """
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    response = client.post(
        "/auth/login",
        json={
            "email": "qa-issue-85-unknown@example.com",
            "password": "NotTheRealPassword_85!",
        },
    )
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid email or password"}

    me_response = client.get("/auth/me")
    assert me_response.status_code == 401, me_response.text
    assert me_response.json()["detail"] == "Not authenticated"
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
