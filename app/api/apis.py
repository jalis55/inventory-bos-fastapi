from fastapi import APIRouter
from .endpoints import (
    auth,
    users,
    category,
    company,
    product_variant,
    product
)


router = APIRouter()
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(category.router)
router.include_router(company.router)
router.include_router(product_variant.router)
router.include_router(product.router)
