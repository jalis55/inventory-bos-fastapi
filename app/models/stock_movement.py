from sqlalchemy import String, DateTime, ForeignKey, Integer, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.db.base import Base


class MovementType(str, enum.Enum):
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"


class StockMovement(Base):
    """An immutable, append-only ledger entry for stock movement.

    Each row records a permanent movement against a batch. The batch's
    ``quantity`` is the running balance derived from these entries. Entries are
    never edited or deleted; corrections are recorded as a new reversing entry
    (``reverses_id``), bank-statement style.
    """

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id"), nullable=False, index=True
    )

    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # delta, always >= 0

    # Audit trail: balance before/after this entry
    prev_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    current_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Points to the entry this movement reverses (bank-style correction)
    reverses_id: Mapped[int | None] = mapped_column(
        ForeignKey("stock_movements.id"), nullable=True
    )

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    batch: Mapped["Batch"] = relationship("Batch", back_populates="stock_movements")
    user: Mapped["User"] = relationship("User", back_populates="stock_movements")
    supplier: Mapped["Supplier"] = relationship(
        "Supplier", back_populates="stock_movements"
    )
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="stock_movements"
    )

    # Self-referential: the entry this reverses, and entries reversing this one
    reverses: Mapped["StockMovement | None"] = relationship(
        "StockMovement", remote_side=[id], back_populates="reversals"
    )
    reversals: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="reverses"
    )
