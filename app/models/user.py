
from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column,relationship
from datetime import datetime
from enum import Enum
from app.db.base import Base


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    STORE_KEEPER = "store_keeper"
    SELLER = "seller"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(
        SQLEnum(Role, name="user_role", values_callable=lambda r: [e.value for e in r]),
        default=Role.SELLER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


    #Relationships

    customers: Mapped[list["Customer"]] = relationship(
        "Customer", back_populates="user"
    )

    suppliers: Mapped[list["Supplier"]] = relationship(
        "Supplier", back_populates="user"
    )

    batches: Mapped[list["Batch"]] = relationship(
        "Batch", back_populates="user"
    )

    stock_movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="user"
    )

    supplier_returns: Mapped[list["SupplierReturn"]] = relationship(
        "SupplierReturn", back_populates="user"
    )

    supplier_payments: Mapped[list["SupplierPayment"]] = relationship(
        "SupplierPayment", back_populates="user"
    )

    batches: Mapped[list["Batch"]] = relationship("Batch", back_populates="user")
