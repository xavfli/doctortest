"""Authentication and user management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, require_admin
from server.core.database import get_db
from server.core.security import create_access_token, hash_password, verify_password
from server.models import ROLE_ADMIN, ROLE_STUDENT, STATUS_SUBMITTED, Attempt, User
from server.schemas import (
    PasswordChange,
    TokenOut,
    UserCreate,
    UserLogin,
    UserOut,
    UserUpdate,
)
from server.services import audit
from server.services.settings import get_bool, get_str

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(db: Session, user: User) -> UserOut:
    """Build the user payload with attempt statistics attached."""
    row = db.execute(
        select(
            func.count(Attempt.id),
            func.avg(Attempt.score_percent),
        ).where(
            Attempt.user_id == user.id,
            Attempt.status == STATUS_SUBMITTED,
        )
    ).one()
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        attempts_count=int(row[0] or 0),
        average_score=round(float(row[1]), 1) if row[1] is not None else None,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenOut:
    """Self-service registration (can be disabled from the admin panel)."""
    if not get_bool(db, "allow_registration", True):
        raise HTTPException(status_code=403, detail="Ro'yxatdan o'tish yopilgan")
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Bu e-pochta allaqachon ro'yxatdan o'tgan")
    # Self-registration may only create students; staff is created by an admin.
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=ROLE_STUDENT,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit.record(db, user, "user.register", "user", user.id, f"email={user.email}")
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=_user_out(db, user))


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # Say the account is unknown but not that the password was wrong.
        raise HTTPException(status_code=401, detail="Bunday hisob topilmadi")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Parol noto‘g‘ri. Uni kiritishda bo‘sh joy qolmasligiga e’tibor bering."
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Hisobingiz bloklangan")
    token = create_access_token(user.id, user.role)
    return TokenOut(access_token=token, user=_user_out(db, user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return _user_out(db, user)


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Self-service password update: the user must prove the current one."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Joriy parol noto‘g‘ri")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Yangi parol joriy paroldan farq qilishi kerak")
    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    audit.record(db, user, "user.change_password", "user", user.id)
    db.commit()
    return {"ok": True}
