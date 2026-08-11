from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
from app.schemas.auth import UserMinimal   # or wherever UserMinimal is


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str = Field(..., min_length=5, max_length=20)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class SupplierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, min_length=5, max_length=20)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class SupplierOut(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested user
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedSuppliers(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[SupplierOut]

    model_config = ConfigDict(from_attributes=True)