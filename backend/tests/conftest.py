"""Shared pytest fixtures for backend tests."""
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.core.security import create_server_session
from backend.app.models.entities import UserSession

# In-memory SQLite engine for fast isolated tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provides a fresh isolated database for each test function."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers_factory(db_session: Session):
    """Factory creating authenticated request headers with desired role."""
    def _create_headers(role: str = "analyst") -> dict:
        session = create_server_session(
            db=db_session,
            user_id=f"test_{role}_1",
            username=f"test_{role}",
            email=f"{role}@example.test",
            role=role,
            duration_hours=12
        )
        return {
            "Authorization": f"Bearer {session.token}",
            "X-CSRF-Token": session.csrf_token
        }
    return _create_headers
