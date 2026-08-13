from fastapi import APIRouter
from .endpoints import (
    auth,
    users,
    category,
    company,
    product_variant,
    product,
    customer,
    supplier,
    batch,
    stock_movement,
    supplier_return,
    supplier_payment,
    customer_sell,
    customer_return,
    customer_payment,
)


router = APIRouter()
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(category.router)
router.include_router(company.router)
router.include_router(product_variant.router)
router.include_router(product.router)
router.include_router(customer.router)
router.include_router(supplier.router)
router.include_router(batch.router)
router.include_router(stock_movement.router)
router.include_router(supplier_return.router)
router.include_router(supplier_payment.router)
router.include_router(customer_sell.router)
router.include_router(customer_return.router)
router.include_router(customer_payment.router)
