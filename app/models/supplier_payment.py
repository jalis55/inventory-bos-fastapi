from sqlalchemy import String, Date, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.db.base import Base


class SupplierPayment(Base):
    """An immutable payment made to a supplier, tied to a received batch.

    The payable balance is derived, not stored:
        outstanding = total_cost - returned_value - paid
    where total_cost = batch.received_quantity * batch.unit_price,
    returned_value comes from supplier returns on that batch, and paid is the
    sum of these entries. Payments are append-only; corrections are made with
    reversing entries.
    """

    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False, index=True
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="supplier_payments"
    )
    batch: Mapped["Batch"] = relationship("Batch", back_populates="supplier_payments")
    user: Mapped["User"] = relationship("User", back_populates="supplier_payments")
