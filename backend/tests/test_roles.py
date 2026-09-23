import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.core.security import create_access_token

# Test router used exclusively within the testing layer
rbac_test_router = APIRouter(prefix="/test-rbac", tags=["Test RBAC"])


@rbac_test_router.get("/admin-only")
def admin_only_endpoint(current_user: User = Depends(require_roles(UserRole.ADMIN))):
    return {"message": "Admin access granted", "user_id": current_user.id}


@rbac_test_router.get("/faculty-or-reviewer")
def faculty_or_reviewer_endpoint(
    current_user: User = Depends(require_roles(UserRole.FACULTY, UserRole.REVIEWER))
):
    return {"message": "Evaluator access granted", "role": current_user.role.value}


@pytest.fixture(scope="module", autouse=True)
def mount_test_router():
    """Mount test router for the duration of role tests and remove it on teardown."""
    app.include_router(rbac_test_router)
    yield
    # Unmount test router routes
    app.routes[:] = [route for route in app.routes if not getattr(route, "path", "").startswith("/test-rbac")]


def test_admin_role_access_granted(client: TestClient, test_admin_user: User):
    token = create_access_token(subject=test_admin_user.id, role=test_admin_user.role.value)
    response = client.get(
        "/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == test_admin_user.id


def test_faculty_role_forbidden_from_admin_endpoint(client: TestClient, test_user: User):
    # test_user is FACULTY
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    response = client.get(
        "/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


def test_multi_role_allowance(client: TestClient, test_user: User):
    token = create_access_token(subject=test_user.id, role=test_user.role.value)
    response = client.get(
        "/test-rbac/faculty-or-reviewer",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == UserRole.FACULTY.value


def test_stale_jwt_role_claim_does_not_override_database_role(client: TestClient, test_user: User):
    """Verify that a forged or stale JWT claiming role='ADMIN' is rejected if the database record has role='FACULTY'."""
    # test_user has role FACULTY in database.
    # We forge/create a token that claims role="ADMIN".
    token_with_forged_role = create_access_token(subject=test_user.id, role="ADMIN")

    response = client.get(
        "/test-rbac/admin-only",
        headers={"Authorization": f"Bearer {token_with_forged_role}"},
    )
    # Backend authorization must query the database user and reject with 403
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]
