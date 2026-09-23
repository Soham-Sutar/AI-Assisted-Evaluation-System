import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserRole
from app.core.security import get_password_hash, create_access_token


def test_login_success(client: TestClient, test_user: User):
    response = client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "TestFacultyPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_user.email
    assert data["user"]["full_name"] == test_user.full_name
    assert data["user"]["role"] == test_user.role.value
    assert data["user"]["is_active"] is True
    # Password hash must NEVER be exposed
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_login_invalid_password(client: TestClient, test_user: User):
    response = client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_nonexistent_email(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent.user@example.com", "password": "SomePassword123!"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_inactive_user(client: TestClient, inactive_user: User):
    response = client.post(
        "/api/auth/login",
        json={"email": inactive_user.email, "password": "TestInactivePass123!"},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_get_me_success(client: TestClient, test_user: User):
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["full_name"] == test_user.full_name
    assert data["role"] == test_user.role.value
    assert "password_hash" not in data


def test_get_me_without_token(client: TestClient):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_me_invalid_token(client: TestClient):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert response.status_code == 401


def test_duplicate_email_rejection(db_session: Session, test_user: User):
    duplicate_user = User(
        email=test_user.email,  # duplicate
        full_name="Duplicate Name",
        password_hash=get_password_hash("DuplicatePass123!"),
        role=UserRole.FACULTY,
    )
    db_session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
