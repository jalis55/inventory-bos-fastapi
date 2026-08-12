from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Float, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.db.base import Base


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    
    batch_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Packaging info (user input)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)          # e.g. 10
    received_unit: Mapped[str] = mapped_column(String(20), nullable=False)           # carton / box / pcs
    units_per_package: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Auto calculated & stored
    initial_quantity: Mapped[int] = mapped_column(Integer, nullable=False)           # total pcs received
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)                   # current remaining pcs

    # Pricing (per pcs)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    sell_price: Mapped[float] = mapped_column(Float, nullable=False)

    mfg_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exp_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="batches")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="batches")
    user: Mapped["User"] = relationship("User", back_populates="batches")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="batch"
    )