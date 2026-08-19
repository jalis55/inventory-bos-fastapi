from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class BaseModelConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class Brand(BaseModelConfig):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True

class BrandUpdate(BaseModelConfig):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None

class BrandOut(BaseModelConfig):
    name: str
    id: int
    created_at: datetime
    updated_at: datetime

class PaginateResponse(BaseModelConfig):
    total: int
    page: int
    size: int
    items: list[BrandOut]
