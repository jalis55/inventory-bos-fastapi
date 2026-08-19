from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Numeric, Enum, Text, DateTime, Integer, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import LedgerRefType
from app.utils.helpers import generate_uuid
from app.db.base import Base


class PartyLedgerEntry(Base):
    __tablename__ = "party_ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    party_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.id"), nullable=False)

    ref_type: Mapped[LedgerRefType] = mapped_column(
        Enum(LedgerRefType, name="ledger_ref_type"), nullable=False
    )
    ref_id: Mapped[str] = mapped_column(String(36), nullable=False)

    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")

    # Snapshot of party.balance_cached immediately after this entry -
    # written once, at insert time, by write_ledger_entry() in
    # app/services/party_ledger.py. Never recomputed after the fact.
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    party: Mapped["Party"] = relationship("Party", back_populates="ledger_entries")

    __table_args__ = (
        Index("idx_ledger_party_id", "party_id"),
        Index("idx_ledger_ref", "ref_type", "ref_id"),
        Index("idx_ledger_entry_date", "entry_date"),
    )

    def __repr__(self):
        return f"<PartyLedgerEntry(id={self.id}, party_id={self.party_id}, balance_after={self.balance_after})>"
