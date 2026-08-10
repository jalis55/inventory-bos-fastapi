from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User,Role
from app.schemas.auth import UserCreate
from app.utils.security import hash_password, verify_password
from app.core.config import settings
from datetime import datetime, timedelta, timezone


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
    if not user:
        return None

    now = datetime.now(timezone.utc)

    # Currently locked out
    if user.locked_until and user.locked_until > now:
        remaining_minutes = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked due to failed login attempts. Try again in {remaining_minutes} minute(s)."
        )

    # Lock has expired naturally — reset before evaluating this attempt
    if user.locked_until and user.locked_until <= now:
        user.failed_login_attempts = 0
        user.locked_until = None

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        db.add(user)
        await db.commit()
        return None

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Successful login — clear any prior failure state
    if user.failed_login_attempts > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.add(user)
        await db.commit()

    return user
