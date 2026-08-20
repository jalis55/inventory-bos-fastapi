from decimal import Decimal
from typing import Optional
from datetime import date, datetime
from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, Integer, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.utils.helpers import generate_uuid

# NOTE: unlike Party/Product/ProductVariant, this does NOT extend
# BaseSkeleton. A batch has no meaningful "name" and no is_active toggle -
# it's an append-only ledger record that's either consumed down to zero
# or it isn't. If your BaseSkeleton is just a thin id/created_at/updated_at
# mixin with no forced name/is_active columns, feel free to extend it
# instead for consistency - swap the import below.
from app.db.base import Base  # adjust to your project's actual declarative base import


class ProductBatch(Base):
    __tablename__ = "product_batches"

    # Eagerly fetch server-generated created_at during flush so it's never
    # left "expired" after commit (async + expired attr = MissingGreenlet).
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # unique=True is what enforces the strict rule: one batch per
    # PurchaseLine, always - never merged, never shared across two
    # purchase lines even if variant/cost/supplier all match.
    purchase_line_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_lines.id"), nullable=False, unique=True
    )

    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.id"), nullable=False)

    # Locked at creation - never edited after the batch exists.
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Derived snapshot: qty_remaining's value immediately BEFORE the most
    # recent movement. NULL until the first sale/return touches this batch.
    # NEVER set this directly - it is only ever written by
    # record_batch_movement() in app/services/product_batch.py, in the same
    # transaction as the qty_remaining change and the stock_movement insert.
    previous_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)

    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    variant: Mapped["ProductVariant"] = relationship(
        "ProductVariant", back_populates="batches"
    )
    supplier: Mapped["Party"] = relationship(
        "Party", back_populates="product_batches"
    )
    purchase_line: Mapped["PurchaseLine"] = relationship(
        "PurchaseLine", back_populates="batch"
    )

    __table_args__ = (
        Index("idx_batch_variant_id", "variant_id"),
        Index("idx_batch_supplier_id", "supplier_id"),
        Index("idx_batch_expiry_date", "expiry_date"),
        CheckConstraint("cost_price > 0", name="check_cost_price_positive"),
        CheckConstraint("qty_received > 0", name="check_qty_received_positive"),
        CheckConstraint("qty_remaining >= 0", name="check_qty_remaining_nonneg"),
        CheckConstraint(
            "qty_remaining <= qty_received", name="check_qty_remaining_not_exceed_received"
        ),
    )

    # Readable supplier name for API consumers - relies on the caller having
    # eager-loaded `supplier` (see the batch endpoints), otherwise it lazy-loads.
    @property
    def supplier_name(self) -> str | None:
        return self.supplier.name if self.supplier else None

    # Variant info for the UI - relies on the caller having eager-loaded
    # `variant` (see the batch endpoints), otherwise it lazy-loads.
    @property
    def variant_name(self) -> str | None:
        return self.variant.name if self.variant else None

    @property
    def variant_sku(self) -> str | None:
        return self.variant.sku if self.variant else None

    def __repr__(self):
        return (
            f"<ProductBatch(id={self.id}, variant_id={self.variant_id}, "
            f"remaining={self.qty_remaining}/{self.qty_received})>"
        )
