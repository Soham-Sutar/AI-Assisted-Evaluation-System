from datetime import timedelta
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.models.user import UserRole


def test_password_hashing_and_verification():
    raw_password = "SecurePassword@2026!"
    hashed = get_password_hash(raw_password)

    # Hash should not equal plain text
    assert hashed != raw_password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    # Correct verification
    assert verify_password(raw_password, hashed) is True

    # Incorrect verification
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_creation_and_decoding():
    user_id = "test-uuid-12345"
    role = UserRole.ADMIN.value

    token = create_access_token(subject=user_id, role=role)
    assert isinstance(token, str)
    assert len(token) > 20

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired_token():
    user_id = "test-uuid-expired"
    role = UserRole.FACULTY.value

    # Token that expired 5 minutes ago
    expired_token = create_access_token(
        subject=user_id,
        role=role,
        expires_delta=timedelta(minutes=-5),
    )

    payload = decode_access_token(expired_token)
    assert payload is None


def test_jwt_invalid_token_tampering():
    user_id = "test-uuid-tampered"
    token = create_access_token(subject=user_id, role=UserRole.REVIEWER.value)

    # Tamper with token string
    tampered_token = token[:-5] + "abcde"
    payload = decode_access_token(tampered_token)
    assert payload is None

    # Completely invalid string
    assert decode_access_token("invalid.token.structure") is None
