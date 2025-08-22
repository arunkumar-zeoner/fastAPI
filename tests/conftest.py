import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock database dependencies before importing the app
with patch.dict('sys.modules', {
    'pymysql': Mock(),
    'sqlalchemy': Mock(),
    'sqlalchemy.orm': Mock(),
    'app.database': Mock(),
    'app.models': Mock(),
    'app.auth': Mock(),
}):
    # Mock database session
    mock_session = Mock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    mock_session.query.return_value.filter.return_value.count.return_value = 0
    
    # Mock database functions
    mock_db_module = Mock()
    mock_db_module.get_db.return_value = mock_session
    mock_db_module.SessionLocal.return_value = mock_session
    
    sys.modules['app.database'] = mock_db_module
    
    # Import the app after mocking
    from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_db():
    with patch('app.database.get_db') as mock:
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        mock.return_value = mock_session
        yield mock_session

@pytest.fixture
def mock_cognito():
    with patch('app.auth.verify_token') as mock:
        mock.return_value = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "custom:site": "dev"
        }
        yield mock

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for all tests"""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "dummy")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "dummy")
