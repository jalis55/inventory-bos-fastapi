from decimal import Decimal
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import (
    String, Numeric, Date, DateTime, ForeignKey, Integer, Enum, Index,
    CheckConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import SaleStatus
from app.utils.helpers import generate_uuid
from app.db.base import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    party_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("parties.id"), nullable=True
    )  # null = walk-in/cash
    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, name="sale_status"), nullable=False, default=SaleStatus.DRAFT
    )
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="sales")
    lines: Mapped[List["SaleLine"]] = relationship(
        "SaleLine", back_populates="sale", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sale_party_id", "party_id"),
        Index("idx_sale_status", "status"),
    )

    def __repr__(self):
        return f"<Sale(id={self.id}, party_id={self.party_id}, status={self.status})>"


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sale_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales.id"), nullable=False)
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_variants.id"), nullable=False
    )

    # Both NULL while the sale is DRAFT - only set by complete_sale()'s
    # FIFO allocation (app/services/sale.py). A single client-submitted
    # line can end up as MULTIPLE persisted SaleLine rows if it has to
    # draw from more than one batch, which is why these live here rather
    # than being required at creation.
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("product_batches.id"), nullable=True
    )
    unit_cost_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Known at creation (qty * unit_price) - doesn't depend on batch choice.
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship("Sale", back_populates="lines")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")
    batch: Mapped[Optional["ProductBatch"]] = relationship("ProductBatch")

    __table_args__ = (
        Index("idx_sale_line_sale_id", "sale_id"),
        Index("idx_sale_line_variant_id", "variant_id"),
        CheckConstraint("qty > 0", name="check_sale_line_qty_positive"),
        CheckConstraint("unit_price >= 0", name="check_sale_line_unit_price_nonneg"),
    )

    def __repr__(self):
        return f"<SaleLine(id={self.id}, variant_id={self.variant_id}, qty={self.qty})>"
