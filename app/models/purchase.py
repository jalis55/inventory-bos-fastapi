from decimal import Decimal
from typing import List, Optional
from datetime import date
from sqlalchemy import String, Numeric, Date, Text, ForeignKey, Integer, Enum, Index, CheckConstraint, func, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import PurchaseStatus
from app.utils.helpers import generate_uuid

# Same reasoning as ProductBatch: neither Purchase nor PurchaseLine has a
# meaningful "name" or is_active toggle, so they extend the raw Base
# rather than BaseSkeleton.
from app.db.base import Base


class Purchase(Base):
    __tablename__ = "purchases"

    # Eagerly fetch server-generated created_at/updated_at during flush so
    # they're never left "expired" after commit (reading an expired attr in
    # an async context raises MissingGreenlet).
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid)

    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parties.id"), nullable=False)

    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status"),
        nullable=False,
        default=PurchaseStatus.DRAFT,
    )

    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_no: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[date] = mapped_column(Date, server_default=func.now())
    updated_at: Mapped[date] = mapped_column(
        Date, server_default=func.now(), onupdate=func.now()
    )

    # Amount paid against THIS purchase invoice. Bumped by record_payment()
    # (app/services/payment.py) in the same transaction that writes the
    # Payment row - never set directly. Per-invoice due = SUM(line_total) -
    # amount_paid, so a supplier's outstanding is shown invoice-by-invoice
    # instead of only against their overall running balance.
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Value of goods returned against THIS invoice (created by
    # app/services/purchase_return.py in the same transaction as the
    # return). Keeps per-invoice state correct after full payment: a
    # fully-paid invoice that gets X returned shows a credit (X still owed
    # to you by the supplier) rather than a blank "fully paid" while only
    # the supplier's running balance quietly goes negative.
    returned_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    # Relationships
    supplier: Mapped["Party"] = relationship(
        "Party", back_populates="purchases")
    lines: Mapped[List["PurchaseLine"]] = relationship(
        "PurchaseLine", back_populates="purchase", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_purchase_supplier_id", "supplier_id"),
        Index("idx_purchase_status", "status"),
    )

    def __repr__(self):
        return f"<Purchase(id={self.id}, supplier_id={self.supplier_id}, status={self.status})>"


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid)

    purchase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchases.id"), nullable=False
    )
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id"), nullable=False
    )

    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Database-generated column – never set this from Python
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        Computed("qty * unit_cost", persisted=True),
    )

    # Relationships
    purchase: Mapped["Purchase"] = relationship(
        "Purchase", back_populates="lines")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")

    batch: Mapped[Optional["ProductBatch"]] = relationship(
        "ProductBatch", back_populates="purchase_line", uselist=False
    )

    __table_args__ = (
        Index("idx_purchase_line_purchase_id", "purchase_id"),
        Index("idx_purchase_line_variant_id", "variant_id"),
        CheckConstraint("qty > 0", name="check_purchase_line_qty_positive"),
        CheckConstraint("unit_cost > 0",
                        name="check_purchase_line_unit_cost_positive"),
    )

    # How much of this line is still in inventory (batch.qty_remaining).
    # Lets the purchase-return UI hide lines that are sold out - you can
    # only return goods that still exist in stock. Requires the caller to
    # have eager-loaded `batch` (the endpoints do), otherwise it lazy-loads.
    @property
    def qty_remaining(self) -> Decimal | None:
        return self.batch.qty_remaining if self.batch else None

    def __repr__(self):
        return f"<PurchaseLine(id={self.id}, variant_id={self.variant_id}, qty={self.qty})>"
