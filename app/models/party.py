from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Numeric, Enum, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import PartyType
from app.core import BaseSkeleton


class Party(BaseSkeleton):
    __tablename__ = "parties"

    party_type: Mapped[PartyType] = mapped_column(
        Enum(
            PartyType,
            name="partytype",       # ← must match the existing Postgres type
            native_enum=True,
            create_type=False,      # don’t try to create the type again
        ),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    credit_limit: Mapped[Decimal] = mapped_column(
            Numeric(12, 2),
            nullable=False,
            default=Decimal("0"),
            server_default="0",
        )

    # Derived/cached value - SUM(credit - debit) from party_ledger_entry.
    # Can legitimately be NEGATIVE (e.g. a supplier owes you money after
    # a return that happened post-payment, or a customer overpaid).
    # NEVER set this directly from client input or an arbitrary admin edit -
    # it must only ever be mutated inside the same transaction as a new
    # party_ledger_entry insert, so every change stays traceable.
    balance_cached: Mapped[Decimal] = mapped_column(
            Numeric(12, 2),
            nullable=False,
            default=Decimal("0"),
            server_default="0",
        )

    # Batches this party supplied, when party_type == SUPPLIER. There's no
    # DB-level way to restrict a relationship to a subset of rows by
    # party_type - enforce "only a SUPPLIER can be chosen here" in the
    # purchase-receiving service instead, not at the model level.
    product_batches: Mapped[List["ProductBatch"]] = relationship(
        "ProductBatch", back_populates="supplier"
    )
    purchases: Mapped[List["Purchase"]] = relationship(
        "Purchase", back_populates="supplier"
    )
    purchase_returns: Mapped[List["PurchaseReturn"]] = relationship(
        "PurchaseReturn", back_populates="supplier"
    )
    sales: Mapped[List["Sale"]] = relationship(
        "Sale", back_populates="party"
    )
    sales_returns: Mapped[List["SalesReturn"]] = relationship(
        "SalesReturn", back_populates="party"
    )
    ledger_entries: Mapped[List["PartyLedgerEntry"]] = relationship(
        "PartyLedgerEntry", back_populates="party"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="party"
    )

    __table_args__ = (
        Index("idx_party_name", "name"),
        Index("idx_party_type", "party_type"),
        CheckConstraint("credit_limit >= 0",
                        name="check_credit_limit_positive"),
        # NOTE: intentionally NO check constraint on balance_cached.
        # A negative balance is a valid, meaningful state (they owe you).
    )

    def __repr__(self):
        return f"<Party(id={self.id}, name={self.name}, type={self.party_type})>"
