from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User,Role
from app.schemas.auth import UserCreate
from app.utils.security import hash_password, verify_password
from app.core.config import settings


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate, current_user: User) -> User:
    # 1. Check if email already exists
    if await get_user_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # 2. Check if current user has permission to create users
    if current_user.role not in [Role.SUPER_ADMIN, Role.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin and admin can create users"
        )

    requested_role = user_in.role

    # 3. Role-based restrictions
    if current_user.role == Role.SUPER_ADMIN:
        # Super Admin can create everyone EXCEPT Super Admin
        if requested_role == Role.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create super admin user"
            )
        # Super Admin can create any other role
        role_to_create = requested_role

    elif current_user.role == Role.ADMIN:
        # Admin can create STORE_KEEPER and SELLER only
        if requested_role == Role.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create super admin user"
            )
        if requested_role == Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin cannot create another admin user"
            )
        if requested_role not in [Role.STORE_KEEPER, Role.SELLER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Admin can only create store keeper or seller users"
            )
        role_to_create = requested_role

    else:
        # This should never happen due to the check above, but just in case
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create users"
        )

    # 4. Create the user
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=role_to_create,
        is_active=True
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return user
