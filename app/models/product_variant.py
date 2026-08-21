from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Numeric, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import BaseSkeleton
from app.utils.helpers import generate_uuid


class ProductVariant(BaseSkeleton):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Matches Product.id's type (String(36) UUID) - keep these consistent.
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False
    )

    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    barcode: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )

    # Override the base `name` (which is globally unique) - the SAME variant
    # name is allowed across different products (e.g. "SATA SSD 240GB" from
    # Samsung and Adata). Uniqueness is enforced on the combination
    # (product_id, name) below, matching Product's own per-brand/category
    # policy.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # `variant_name` = just the distinguishing part, e.g. "250ml".
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)

    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pack_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    # Used for low-stock alerts once stock_movement/product_batch exist -
    # compare SUM(product_batch.qty_remaining) for this variant against this.
    reorder_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    batches: Mapped[List["ProductBatch"]] = relationship(
        "ProductBatch", back_populates="variant"
    )

    __table_args__ = (
        Index("idx_variant_product_id", "product_id"),
        UniqueConstraint(
            "product_id", "name",
            name="uq_variant_product_name",
        ),
        CheckConstraint("pack_size IS NULL OR pack_size > 0", name="check_pack_size_positive"),
        CheckConstraint(
            "reorder_level IS NULL OR reorder_level >= 0", name="check_reorder_level_nonneg"
        ),
    )

    def __repr__(self):
        return f"<ProductVariant(id={self.id}, sku={self.sku}, variant_name={self.variant_name})>"
