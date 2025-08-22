# conftest.py
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import os

# Import the real FastAPI app; keep SQLAlchemy intact
from app.main import app

# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def client():
    """FastAPI TestClient"""
    return TestClient(app)

@pytest.fixture
def mock_db():
    """
    Mock the database session.
    Any query/filter/count calls return empty results.
    """
    with patch("app.database.get_db") as mock_get_db:
        mock_session = Mock()
        # Mock chained query calls
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        mock_get_db.return_value = mock_session
        yield mock_session

@pytest.fixture
def mock_cognito():
    """
    Mock Cognito token verification.
    Returns a fake user object.
    """
    with patch("app.auth.verify_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "custom:site": "dev"
        }
        yield mock_verify

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Mock environment variables for all tests.
    Ensures no real AWS or database credentials are required.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "dummy")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "dummy")
