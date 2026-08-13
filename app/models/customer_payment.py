from sqlalchemy import String, Date, DateTime, ForeignKey, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum
from app.db.base import Base


class CustomerPaymentType(str, enum.Enum):
    """Direction of a customer cash transaction.

    ``COLLECTION`` is cash we receive from the customer (reduces their
    receivable); ``REFUND`` is cash we return to the customer (increases their
    receivable / settles a credit we owe them).
    """

    COLLECTION = "collection"
    REFUND = "refund"


class CustomerPayment(Base):
    """An immutable cash transaction with a customer (collection or refund).

    The account balance is derived, not stored, at the customer level:
        balance = total_sold - total_returned - total_collected + total_refunded
    A positive balance means the customer owes us; a negative balance means we
    owe the customer (a credit). ``batch_id`` is optional so a transaction can
    be recorded at the customer level without being tied to a single batch.
    """

    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id"), nullable=True, index=True
    )
    payment_type: Mapped[CustomerPaymentType] = mapped_column(
        Enum(CustomerPaymentType, name="customer_payment_type"),
        default=CustomerPaymentType.COLLECTION,
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
    customer: Mapped["Customer"] = relationship(back_populates="customer_payments")
    batch: Mapped["Batch"] = relationship("Batch", back_populates="customer_payments")
    user: Mapped["User"] = relationship(back_populates="customer_payments")
