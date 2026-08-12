from sqlalchemy import String, Date, DateTime, ForeignKey, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum
from app.db.base import Base


class PaymentType(str, enum.Enum):
    """Direction of a supplier cash transaction.

    ``PAYMENT`` is cash we pay to the supplier (reduces what we owe).
    ``COLLECTION`` is cash we receive back from the supplier (a refund /
    settlement of a credit the supplier owes us).
    """

    PAYMENT = "payment"
    COLLECTION = "collection"


class SupplierPayment(Base):
    """An immutable cash transaction with a supplier (payment or collection).

    The account balance is derived, not stored, at the supplier level:
        balance = total_received - total_returned - total_paid + total_collected
    where total_received is the sum over all the supplier's batches of
    (received_quantity * unit_price), total_returned comes from supplier
    returns, and total_paid / total_collected are the sums of these entries by
    type. A positive balance means we owe the supplier; a negative balance means
    the supplier owes us (a credit). Entries are append-only; corrections are
    made with reversing entries. ``batch_id`` is optional so a transaction can
    be recorded at the supplier level without being tied to a single batch.
    """

    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id"), nullable=True, index=True
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="supplier_payment_type"),
        default=PaymentType.PAYMENT,
        nullable=False,
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
