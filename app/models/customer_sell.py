from sqlalchemy import String, Date, DateTime, ForeignKey, Integer, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum
from app.db.base import Base


class CustomerSellStatus(str, enum.Enum):
    COMPLETED = "completed"


class CustomerSell(Base):
    """Header document for a sale of goods to a customer.

    Creating a sell immutably posts an ``OUT`` stock movement for each returned
    line atomically (deducting the batch) and increases the customer's
    receivable, so sells are first-class ledger sources.
    """

    __tablename__ = "customer_sells"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sell_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    sell_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CustomerSellStatus] = mapped_column(
        Enum(CustomerSellStatus, name="customer_sell_status"),
        default=CustomerSellStatus.COMPLETED,
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
    customer: Mapped["Customer"] = relationship(back_populates="customer_sells")
    user: Mapped["User"] = relationship(back_populates="customer_sells")
    items: Mapped[list["CustomerSellItem"]] = relationship(
        "CustomerSellItem", back_populates="sell", cascade="all, delete-orphan"
    )


class CustomerSellItem(Base):
    """A single sold line: how many units of a batch were sold."""

    __tablename__ = "customer_sell_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sell_id: Mapped[int] = mapped_column(
        ForeignKey("customer_sells.id"), nullable=False, index=True
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    sell: Mapped["CustomerSell"] = relationship("CustomerSell", back_populates="items")
    batch: Mapped["Batch"] = relationship("Batch", back_populates="customer_sell_items")
