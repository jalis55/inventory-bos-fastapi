from typing import List, Optional
from app.core import BaseSkeleton
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.utils.helpers import generate_uuid


class Product(BaseSkeleton):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid)

    # Override the base `name` (which is globally unique) - the SAME product
    # name is allowed across different brands/categories. Uniqueness is
    # enforced on the combination (name, brand_id, category_id) below.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=False)
    brand_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("brands.id"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    category: Mapped["Category"] = relationship(
        "Category", back_populates="products")
    brand: Mapped["Brand"] = relationship("Brand", back_populates="products")

    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )

    # A product is only considered a duplicate when name + brand + category
    # all match - the same name can exist under different brands/categories.
    __table_args__ = (
        UniqueConstraint(
            "name", "brand_id", "category_id",
            name="uq_products_name_brand_category",
        ),
    )

    # NOTE: intentionally no direct Product <-> Party (supplier)
    # relationship. A supplier is attached per-batch
    # (ProductBatch.supplier_id), not per-product - the same product can
    # legitimately come from different suppliers at different times, at
    # different costs. A "preferred suppliers for this product" feature,
    # if you want one later, needs its own many-to-many association table
    # rather than a direct FK here.

    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name})>"
