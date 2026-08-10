from fastapi import APIRouter, Depends, Response, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.database import get_db
from app.schemas.auth import UserCreate, UserLogin, UserOut, TokenResponse
from app.services.auth import create_user, authenticate_user, get_user_by_email
from app.utils.security import (create_access_token,
                                create_refresh_token,
                                decode_token,
                                set_auth_cookies,
                                clear_auth_cookies)
from app.api.deps import get_current_user, require_superadmin
from app.models.user import User
from app.core.config import settings
from app.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(
        get_current_user)
):

    user = await create_user(db, user_in, current_user)

    return {
        "message": "User registered successfully",
        "user": UserOut.model_validate(user)
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    user_in: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, user_in.email, user_in.password)
    if not user:
        raise HTTPException(
            status_code=401, detail="Incorrect email or password")

    access = create_access_token({"sub": user.email, "role": user.role})
    refresh = create_refresh_token({"sub": user.email})

    set_auth_cookies(response, access, refresh)
    return TokenResponse(
        access_token=access,
        token_type="bearer"
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    # Get and validate refresh token
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Issue new access token only
    new_access = create_access_token({"sub": user.email, "role": user.role})

    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=new_access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )

    return TokenResponse(
        access_token=new_access,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
