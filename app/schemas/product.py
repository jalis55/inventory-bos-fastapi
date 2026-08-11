from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from app.schemas.company import CompanyOut
from app.schemas.category import CategoryOut
from app.schemas.product_variant import ProductVariantOut


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    company_id: int
    category_id: int
    product_variant_id: int
    unit_of_measure: str = Field(..., min_length=1, max_length=50)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    company_id: int | None = None
    category_id: int | None = None
    product_variant_id: int | None = None
    unit_of_measure: str | None = Field(None, min_length=1, max_length=50)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseModel):
    id: int
    name: str
    company_id: int
    category_id: int
    product_variant_id: int
    unit_of_measure: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductOutWithRelations(BaseModel):
    id: int
    name: str
    unit_of_measure: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    company: CompanyOut
    category: CategoryOut
    product_variant: ProductVariantOut

    model_config = ConfigDict(from_attributes=True)


class PaginatedProducts(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ProductOutWithRelations]

    model_config = ConfigDict(from_attributes=True)