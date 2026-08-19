from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.brand import BrandOut
from app.schemas.category import CategoryOut


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    category_id: int = Field(..., description="Category this product belongs to")
    brand_id: int = Field(..., description="Brand this product belongs to")


class ProductUpdate(BaseModel):
    # All fields optional so a partial update (exclude_unset=True in the
    # route) only touches what was actually sent - see the fix in the
    # router for why this matters.
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    category: CategoryOut
    brand: BrandOut
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductPaginate(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProductOut]
