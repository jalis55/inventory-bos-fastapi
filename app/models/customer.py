from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.db.base import Base


class CustomerType(str, enum.Enum):
    walk_in = "walk_in"
    registered = "registered"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType), default=CustomerType.walk_in, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="customers")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="customer"
    )

    customer_sells: Mapped[list["CustomerSell"]] = relationship(
        "CustomerSell", back_populates="customer"
    )
    customer_returns: Mapped[list["CustomerReturn"]] = relationship(
        "CustomerReturn", back_populates="customer"
    )
    customer_payments: Mapped[list["CustomerPayment"]] = relationship(
        "CustomerPayment", back_populates="customer"
    )