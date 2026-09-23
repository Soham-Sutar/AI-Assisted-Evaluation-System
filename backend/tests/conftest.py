import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.core.database import get_db, engine
from app.core.security import get_password_hash
from app.models.user import User, UserRole


@pytest.fixture(scope="session")
def db_engine():
    """Return the SQLAlchemy engine."""
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Provide an isolated database session rolled back after every test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    test_session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = test_session_factory()

    # Override get_db dependency to use the isolated test session
    app.dependency_overrides[get_db] = lambda: session

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient bound to the isolated session."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a temporary test user within the isolated transaction."""
    user = User(
        email="test.faculty@example.com",
        full_name="Test Faculty",
        password_hash=get_password_hash("TestFacultyPass123!"),
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_admin_user(db_session: Session) -> User:
    """Create a temporary admin user within the isolated transaction."""
    admin = User(
        email="test.admin@example.com",
        full_name="Test Admin",
        password_hash=get_password_hash("TestAdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.refresh(admin)
    return admin


@pytest.fixture(scope="function")
def inactive_user(db_session: Session) -> User:
    """Create a temporary inactive user within the isolated transaction."""
    user = User(
        email="test.inactive@example.com",
        full_name="Test Inactive",
        password_hash=get_password_hash("TestInactivePass123!"),
        role=UserRole.FACULTY,
        is_active=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user
