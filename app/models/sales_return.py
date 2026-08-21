from decimal import Decimal
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import (
    String, Numeric, Date, DateTime, Text, Integer, ForeignKey, Index,
    CheckConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.utils.helpers import generate_uuid
from app.db.base import Base


class SalesReturn(Base):
    __tablename__ = "sales_returns"

    # Eagerly fetch server-generated created_at during flush so it's never
    # left "expired" after commit (async + expired attr = MissingGreenlet).
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # Null for a walk-in return - see app/services/sales_return.py for how
    # that's handled (a Payment refund instead of a ledger entry).
    party_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("parties.id"), nullable=True
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    party: Mapped[Optional["Party"]] = relationship("Party", back_populates="sales_returns")
    lines: Mapped[List["SalesReturnLine"]] = relationship(
        "SalesReturnLine", back_populates="sales_return", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_sales_return_party_id", "party_id"),)

    def __repr__(self):
        return f"<SalesReturn(id={self.id}, party_id={self.party_id})>"

    # Readable party name for API consumers - requires the caller to have
    # eager-loaded `party` (the endpoints do), otherwise it lazy-loads.
    @property
    def party_name(self) -> str | None:
        return self.party.name if self.party else None


class SalesReturnLine(Base):
    __tablename__ = "sales_return_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sales_return_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sales_returns.id"), nullable=False
    )
    sale_line_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sale_lines.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_batches.id"), nullable=False
    )  # stock goes back into the SAME batch it left

    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Copied from sale_line.unit_price at return time - never client-supplied.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Per-line reason for the return (e.g. "damaged", "wrong size", "expired").
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sales_return: Mapped["SalesReturn"] = relationship("SalesReturn", back_populates="lines")
    sale_line: Mapped["SaleLine"] = relationship("SaleLine")
    batch: Mapped["ProductBatch"] = relationship("ProductBatch")

    __table_args__ = (
        Index("idx_sr_line_return_id", "sales_return_id"),
        Index("idx_sr_line_sale_line_id", "sale_line_id"),
        CheckConstraint("qty > 0", name="check_sr_line_qty_positive"),
    )

    # Variant info for the UI, derived from the batch - requires the caller
    # to have eager-loaded `batch` -> `variant` (the endpoints do).
    @property
    def variant_id(self) -> str | None:
        return self.batch.variant_id if self.batch else None

    @property
    def variant_name(self) -> str | None:
        return self.batch.variant.name if self.batch and self.batch.variant else None

    @property
    def variant_sku(self) -> str | None:
        return self.batch.variant.sku if self.batch and self.batch.variant else None
