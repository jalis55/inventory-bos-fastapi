from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.user import User
from app.utils.security import decode_token
from app.core.config import settings
from app.services.auth import get_user_by_email

# Create security scheme for Bearer token
security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    token = None
    
    # First try to get token from cookie
    token = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    
    # If no cookie, try Bearer token
    if not token and credentials:
        token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    email: str | None = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user

def require_roles(*allowed_roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {allowed_roles}",
            )
        return current_user
    return role_checker




# Convenience shortcuts
require_superadmin = require_roles("super_admin")
require_admin = require_roles("super_admin", "admin")
require_superadmin_and_admin = require_roles("super_admin", "admin")
require_superadmin_and_admin_and_store_keeper = require_roles("super_admin", "admin", "store_keeper")