"""Import every model so tables and relationships are registered in one place."""

from app.models.category import Category
from app.models.company import Company
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.supplier import Supplier
from app.models.user import Role, User
from app.models.batch import Batch
from app.models.stock_movement import StockMovement, MovementType
from app.models.supplier_return import SupplierReturn, SupplierReturnItem, SupplierReturnStatus
from app.models.supplier_payment import SupplierPayment

__all__ = [
    "Category",
    "Company",
    "Customer",
    "Product",
    "ProductVariant",
    "Role",
    "Supplier",
    "User",
    "Batch",
    "StockMovement",
    "MovementType",
    "SupplierReturn",
    "SupplierReturnItem",
    "SupplierReturnStatus",
    "SupplierPayment",
]