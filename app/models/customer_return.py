from sqlalchemy import String, Date, DateTime, ForeignKey, Integer, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum
from app.db.base import Base


class CustomerReturnStatus(str, enum.Enum):
    COMPLETED = "completed"


class CustomerReturn(Base):
    """Header document for goods returned by a customer.

    Creating a customer return immutably posts an ``IN`` stock movement for each
    returned line (restocking the batch) and reduces the customer's receivable.
    """

    __tablename__ = "customer_returns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    return_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CustomerReturnStatus] = mapped_column(
        Enum(CustomerReturnStatus, name="customer_return_status"),
        default=CustomerReturnStatus.COMPLETED,
        nullable=False,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="customer_returns")
    user: Mapped["User"] = relationship(back_populates="customer_returns")
    items: Mapped[list["CustomerReturnItem"]] = relationship(
        "CustomerReturnItem", back_populates="return_", cascade="all, delete-orphan"
    )


class CustomerReturnItem(Base):
    """A single returned line: how many units of a batch are returned."""

    __tablename__ = "customer_return_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    return_id: Mapped[int] = mapped_column(
        ForeignKey("customer_returns.id"), nullable=False, index=True
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    return_: Mapped["CustomerReturn"] = relationship(
        "CustomerReturn", back_populates="items"
    )
    batch: Mapped["Batch"] = relationship("Batch", back_populates="customer_return_items")
