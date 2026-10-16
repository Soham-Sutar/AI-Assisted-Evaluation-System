from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.models.user import User, UserRole
from app.models.faculty_subject import FacultySubject
from app.schemas.auth import LoginRequest, TokenResponse, UserRead, UserRegisterRequest
from app.api.deps import get_current_active_user, require_roles

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user with email and password and return a JWT access token."""
    normalized_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == normalized_email)
    user = db.scalars(stmt).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserRead:
    """Return the profile of the currently authenticated user."""
    return current_user


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserRead:
    """Admin only: register a new user (faculty or reviewer) and assign subject eligibility."""
    normalized_email = payload.email.strip().lower()

    existing = db.scalars(select(User).where(User.email == normalized_email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{normalized_email}' already exists",
        )

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    if payload.subject_ids and payload.role == UserRole.FACULTY:
        for subj_id in set(payload.subject_ids):
            db.add(FacultySubject(faculty_id=user.id, subject_id=subj_id))

    db.commit()
    db.refresh(user)
    return user

