from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User,Role
from app.schemas.auth import UserOut
from app.api.deps import require_admin, require_superadmin, get_current_user,require_roles
from typing import List

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[UserOut])
async def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = (await db.execute(select(User))).scalars().all()
    return users

@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN,Role.ADMIN) ),
):
    # user =await db.query(User).filter(User.id == user_id).first()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return user