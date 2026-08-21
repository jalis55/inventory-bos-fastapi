from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional


class ProductVariantCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    barcode: Optional[str] = Field(None, max_length=64)
    variant_name: str = Field(..., min_length=1, max_length=100, description='e.g. "250ml"')
    unit_of_measure: Optional[str] = Field(
        None, max_length=20, description='e.g. "ml", "kg", "pcs"'
    )
    pack_size: Optional[Decimal] = Field(None, gt=0)
    reorder_level: Optional[Decimal] = Field(None, ge=0)
    # product_id is NOT included here - it comes from the URL path
    # (POST /products/{product_id}/variants), not the request body, so
    # there's no way to accidentally create a variant under the wrong
    # product by mismatching a body field against the path.


class ProductVariantUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=64)
    barcode: Optional[str] = Field(None, max_length=64)
    variant_name: Optional[str] = Field(None, min_length=1, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    pack_size: Optional[Decimal] = Field(None, gt=0)
    reorder_level: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    # product_id intentionally NOT updatable. Once a variant has batches,
    # sales, or stock movements attached, moving it to a different product
    # would corrupt cost/stock history. If it was miscategorized,
    # deactivate it and create a new one under the correct product.


class ProductVariantOut(BaseModel):
    id: str
    product_id: str
    sku: str
    barcode: Optional[str]
    name: str
    variant_name: str
    unit_of_measure: Optional[str]
    pack_size: Optional[Decimal]
    reorder_level: Optional[Decimal]
    is_active: bool
    # Total quantity available to sell / remove - sum of every batch's
    # qty_remaining. -1 when the caller didn't ask for stock (avoid the
    # ambiguity of 0 = "no stock" vs "not computed").
    qty_in_stock: Decimal = Field(
        default=Decimal("-1"), description="Sum of batch qty_remaining for this variant"
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductVariantOutPaginate(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProductVariantOut]
