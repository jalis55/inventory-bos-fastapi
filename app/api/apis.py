from fastapi import APIRouter
from .endpoints import (auth,
                        users,
                        brand,
                        category,
                        party,
                        product,
                        product_variant,
                        product_batch,
                        purchase,
                        stock_movement,
                        sale
                        )


router = APIRouter()
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(brand.router)
router.include_router(category.router)
router.include_router(party.router)
router.include_router(product.router)
router.include_router(product_variant.router)
router.include_router(product_batch.router)
router.include_router(purchase.router)
router.include_router(stock_movement.router)
router.include_router(sale.router)
