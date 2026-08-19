"""
Central import point - every model MUST be imported here (even if unused
directly) so SQLAlchemy's mapper registry can resolve the string-based
forward references (e.g. relationship("ProductVariant")) used throughout
these models. Missing an import here is the #1 cause of
InvalidRequestError / NoReferencedTableError at startup.
"""
from app.models.enums import (
    PartyType, MovementType, LedgerRefType, PaymentDirection,
    PurchaseStatus, SaleStatus,
)
from app.models.user import User, Role
from app.models.brand import Brand
from app.models.category import Category
from app.models.party import Party
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.purchase import Purchase, PurchaseLine
from app.models.product_batch import ProductBatch
from app.models.stock_movement import StockMovement
from app.models.sale import Sale, SaleLine
from app.models.purchase_return import PurchaseReturn, PurchaseReturnLine
from app.models.sales_return import SalesReturn, SalesReturnLine
from app.models.party_ledger_entry import PartyLedgerEntry
from app.models.payment import Payment

__all__ = [
    "PartyType", "MovementType", "LedgerRefType", "PaymentDirection",
    "PurchaseStatus", "SaleStatus",
    "User", "Role",
    "Brand", "Category", "Party",
    "Product", "ProductVariant", "ProductBatch",
    "Purchase", "PurchaseLine",
    "StockMovement",
    "Sale", "SaleLine",
    "PurchaseReturn", "PurchaseReturnLine",
    "SalesReturn", "SalesReturnLine",
    "PartyLedgerEntry", "Payment",
]
