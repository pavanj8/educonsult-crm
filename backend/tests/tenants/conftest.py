"""Shared fixtures for tenant endpoint tests."""

from unittest.mock import patch

import pytest


@pytest.fixture()
def mock_owner_invite_email():
    """Prevent real SMTP calls during tenant creation tests."""
    with patch("app.routers.tenants.send_owner_invite_email") as mock_send:
        yield mock_send


@pytest.fixture(autouse=True)
def _autouse_mock_owner_invite_email(mock_owner_invite_email):
    """All tenant HTTP tests mock owner invite delivery by default."""
    return mock_owner_invite_email
