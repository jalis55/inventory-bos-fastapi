from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Numeric, Enum, DateTime, ForeignKey, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import MovementType
from app.utils.helpers import generate_uuid
from app.db.base import Base


class StockMovement(Base):
    __tablename__ = "stock_movements"

    # Eagerly fetch server-generated created_at during flush so it's never
    # left "expired" after commit (async + expired attr = MissingGreenlet).
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_batches.id"), nullable=False
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Polymorphic ref to whatever business event caused this movement
    # (purchase, sale, purchase_return, sales_return, adjustment).
    ref_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(36), nullable=False)

    qty_remaining_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    movement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships (read-only enrichment for the UI - always eager-load
    # these to avoid lazy-load errors in async context).
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")
    batch: Mapped["ProductBatch"] = relationship("ProductBatch")

    __table_args__ = (
        Index("idx_movement_variant_id", "variant_id"),
        Index("idx_movement_batch_id", "batch_id"),
        Index("idx_movement_ref", "ref_type", "ref_id"),
        CheckConstraint("qty > 0", name="check_movement_qty_positive"),
    )

    def __repr__(self):
        return f"<StockMovement(id={self.id}, type={self.movement_type}, qty={self.qty})>"
