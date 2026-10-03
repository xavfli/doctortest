"""Admin endpoints for managing user accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.api.deps import require_admin
from server.core.database import get_db
from server.core.security import hash_password
from server.models import ROLE_ADMIN, ROLE_STUDENT, STATUS_SUBMITTED, Attempt, User
from server.schemas import UserCreate, UserOut, UserUpdate
from server.services import audit

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


def _out(db: Session, user: User) -> UserOut:
    row = db.execute(
        select(func.count(Attempt.id), func.avg(Attempt.score_percent)).where(
            Attempt.user_id == user.id, Attempt.status == STATUS_SUBMITTED
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


@router.get("", response_model=list[UserOut])
def list_users(
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[UserOut]:
    stmt = select(User)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(like) | func.lower(User.full_name).like(like)
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    users = db.scalars(stmt.order_by(User.id)).all()
    return [_out(db, u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Bu e-pochta band")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit.record(db, admin, "user.create", "user", user.id, f"role={user.role}")
    db.commit()
    db.refresh(user)
    return _out(db, user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if user.id == admin.id and payload.role and payload.role != ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="O'z rolingizni pasaytira olmaysiz")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="O'z hisobingizni bloklay olmaysiz")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    db.flush()
    audit.record(db, admin, "user.update", "user", user.id)
    db.commit()
    db.refresh(user)
    return _out(db, user)


@router.delete("/{user_id}", status_code=200)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="O'zini o'chira olmaysiz")
    email = user.email
    db.delete(user)
    audit.record(db, admin, "user.delete", "user", user_id, f"email={email}")
    db.commit()
    return {"deleted": user_id, "email": email}
