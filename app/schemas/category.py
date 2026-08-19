from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class CategoryConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Category(CategoryConfig):
    name: str = Field(..., min_length=1, max_length=255)


class CategoryUpdate(CategoryConfig):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class CategoryOut(CategoryConfig):
    name: str
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PaginateResponse(CategoryConfig):
    total: int
    page: int
    size: int
    items: list[CategoryOut]
