from sqlalchemy import String, Date, DateTime, ForeignKey, Integer, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
import enum
from app.db.base import Base


class SupplierReturnStatus(str, enum.Enum):
    COMPLETED = "completed"


class SupplierReturn(Base):
    """Header document for a return of goods to a supplier.

    Creating a supplier return immutably posts an ``OUT`` stock movement for
    each returned line atomically, so returns are first-class ledger sources.
    """

    __tablename__ = "supplier_returns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    return_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False, index=True
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SupplierReturnStatus] = mapped_column(
        Enum(SupplierReturnStatus, name="supplier_return_status"),
        default=SupplierReturnStatus.COMPLETED,
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
    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="supplier_returns"
    )
    user: Mapped["User"] = relationship("User", back_populates="supplier_returns")
    items: Mapped[list["SupplierReturnItem"]] = relationship(
        "SupplierReturnItem", back_populates="return_", cascade="all, delete-orphan"
    )


class SupplierReturnItem(Base):
    """A single returned line: how many units of a batch are returned."""

    __tablename__ = "supplier_return_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    return_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_returns.id"), nullable=False, index=True
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
    return_: Mapped["SupplierReturn"] = relationship(
        "SupplierReturn", back_populates="items"
    )
    batch: Mapped["Batch"] = relationship("Batch", back_populates="supplier_return_items")
