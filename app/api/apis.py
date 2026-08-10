from fastapi import APIRouter
from .endpoints import auth, users,category



router=APIRouter()
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(category.router)
