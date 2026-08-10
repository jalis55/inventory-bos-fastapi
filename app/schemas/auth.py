
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
import re

from app.models.user import Role


def validate_password_strength(v: str) -> str:
    """Validate that a password meets the strength requirements."""
    if len(v) < 8:
        raise ValueError('Password must be at least 8 characters')
    if not re.search(r'[A-Z]', v):
        raise ValueError('Password must contain at least one uppercase letter')
    if not re.search(r'[a-z]', v):
        raise ValueError('Password must contain at least one lowercase letter')
    if not re.search(r'\d', v):
        raise ValueError('Password must contain at least one number')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
        raise ValueError('Password must contain at least one special character')
    return v


# User Create Schema
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: Role = Role.SELLER

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        return validate_password_strength(v)


# User Login Schema
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# User Update Schema
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


# Password Reset Schema
class PasswordReset(BaseModel):
    email: EmailStr
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength"""
        return validate_password_strength(v)

    @field_validator('old_password')
    @classmethod
    def validate_old_password(cls, v: str) -> str:
        """Validate old password is not empty"""
        if not v or len(v) < 1:
            raise ValueError('Old password is required')
        return v


# User Out Schema (Response)
class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: Role
    is_active: bool
    created_at: datetime

    # ✅ Pydantic V2 config
    model_config = ConfigDict(from_attributes=True)


# Paginated Users Schema
class PaginatedUsers(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[UserOut]

    model_config = ConfigDict(from_attributes=True)


# Token Response Schema
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Token Data Schema (for internal use)
class TokenData(BaseModel):
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
