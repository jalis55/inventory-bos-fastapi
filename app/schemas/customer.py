from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
from enum import Enum
from app.schemas.auth import UserMinimal   # or wherever you put it


class CustomerTypeEnum(str, Enum):
    walk_in = "walk_in"
    registered = "registered"


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str = Field(..., min_length=5, max_length=20)
    nid: str | None = Field(None, max_length=50)
    customer_type: CustomerTypeEnum = CustomerTypeEnum.walk_in
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, min_length=5, max_length=20)
    nid: str | None = Field(None, max_length=50)
    customer_type: CustomerTypeEnum | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerOut(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str
    nid: str | None
    customer_type: CustomerTypeEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested user info
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedCustomers(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[CustomerOut]

    model_config = ConfigDict(from_attributes=True)