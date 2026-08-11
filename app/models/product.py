from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .category import Category
from .company import Company
from .product_variant import ProductVariant
from datetime import datetime
from app.db.base import Base


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    company_id: Mapped[int] = mapped_column(
        ForeignKey('companies.id'), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey('categories.id'), nullable=False)
    product_variant_id: Mapped[int] = mapped_column(
        ForeignKey('product_variants.id'), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(
        "Company", back_populates="products")
    category: Mapped["Category"] = relationship(
        "Category", back_populates="products")
    product_variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant", back_populates="products")
