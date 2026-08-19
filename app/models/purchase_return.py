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


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    supplier_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.id"), nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    supplier: Mapped["Party"] = relationship("Party", back_populates="purchase_returns")
    lines: Mapped[List["PurchaseReturnLine"]] = relationship(
        "PurchaseReturnLine", back_populates="purchase_return", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_purchase_return_supplier_id", "supplier_id"),)

    def __repr__(self):
        return f"<PurchaseReturn(id={self.id}, supplier_id={self.supplier_id})>"


class PurchaseReturnLine(Base):
    __tablename__ = "purchase_return_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    purchase_return_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_returns.id"), nullable=False
    )
    purchase_line_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_lines.id"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_batches.id"), nullable=False
    )

    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Copied from batch.cost_price at return time - never client-supplied.
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_return: Mapped["PurchaseReturn"] = relationship(
        "PurchaseReturn", back_populates="lines"
    )
    purchase_line: Mapped["PurchaseLine"] = relationship("PurchaseLine")
    batch: Mapped["ProductBatch"] = relationship("ProductBatch")

    __table_args__ = (
        Index("idx_pr_line_return_id", "purchase_return_id"),
        Index("idx_pr_line_purchase_line_id", "purchase_line_id"),
        CheckConstraint("qty > 0", name="check_pr_line_qty_positive"),
    )
