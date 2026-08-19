"""
Unit tests for the pydantic request/response schemas (validation rules,
defaults and ORM serialisation).
"""
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.brand import Brand as BrandModel
from app.models.category import Category as CategoryModel
from app.models.user import Role
from app.schemas.auth import (
    PasswordReset,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserOut,
    UserUpdate,
)
from app.schemas.brand import Brand as BrandSchema
from app.schemas.brand import BrandOut, BrandUpdate, PaginateResponse as BrandPaginate
from app.schemas.category import Category as CategorySchema
from app.schemas.category import CategoryOut, CategoryUpdate, PaginateResponse as CategoryPaginate


# --------------------------------------------------------------------------- #
# UserCreate
# --------------------------------------------------------------------------- #
def test_user_create_valid():
    user = UserCreate(
        email="user@example.com",
        password="Password123!",
        full_name="John Doe",
    )
    assert user.email == "user@example.com"
    assert user.role == Role.SELLER  # default role


def test_user_create_password_too_short():
    with pytest.raises(ValidationError, match="at least 8 characters"):
        UserCreate(email="a@b.com", password="Short1!")


def test_user_create_password_requires_uppercase():
    with pytest.raises(ValidationError, match="uppercase"):
        UserCreate(email="a@b.com", password="lowercase1!")


def test_user_create_password_requires_lowercase():
    with pytest.raises(ValidationError, match="lowercase"):
        UserCreate(email="a@b.com", password="UPPERCASE1!")


def test_user_create_password_requires_number():
    with pytest.raises(ValidationError, match="number"):
        UserCreate(email="a@b.com", password="Password!X")


def test_user_create_password_requires_special_char():
    with pytest.raises(ValidationError, match="special character"):
        UserCreate(email="a@b.com", password="Password123")


def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="StrongPass1!")


def test_user_create_invalid_role():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="StrongPass1!", role="emperor")


# --------------------------------------------------------------------------- #
# UserLogin / UserUpdate / PasswordReset
# --------------------------------------------------------------------------- #
def test_user_login_valid():
    login = UserLogin(email="a@b.com", password="anything-goes-here")
    assert login.email == "a@b.com"
    assert login.password == "anything-goes-here"


def test_user_update_all_optional():
    update = UserUpdate()
    assert update.full_name is None
    assert update.role is None
    assert update.is_active is None


def test_user_update_partial_fields():
    update = UserUpdate(full_name="New Name")
    assert update.full_name == "New Name"
    assert update.role is None
    assert update.is_active is None


def test_password_reset_valid():
    reset = PasswordReset(
        email="a@b.com", old_password="OldPassword1!", new_password="NewPassword1!"
    )
    assert reset.old_password == "OldPassword1!"


def test_password_reset_new_password_weak():
    with pytest.raises(ValidationError, match="uppercase"):
        PasswordReset(email="a@b.com", old_password="OldPassword1!", new_password="weakpass1")


def test_password_reset_old_password_min_length():
    with pytest.raises(ValidationError):
        PasswordReset(email="a@b.com", old_password="short", new_password="NewPass1!")


# --------------------------------------------------------------------------- #
# TokenResponse / UserOut
# --------------------------------------------------------------------------- #
def test_token_response_default_token_type():
    token = TokenResponse(access_token="abc")
    assert token.access_token == "abc"
    assert token.token_type == "bearer"


@pytest.mark.asyncio
async def test_user_out_serializes_orm_model(db_session, create_user):
    user = await create_user("out@example.com", full_name="Out User", role=Role.ADMIN)
    out = UserOut.model_validate(user)
    assert out.id == user.id
    assert out.email == "out@example.com"
    assert out.full_name == "Out User"
    assert out.role == Role.ADMIN
    assert isinstance(out.created_at, datetime)


def test_user_out_plain_construction():
    user = UserOut(
        id=1,
        email="x@example.com",
        full_name=None,
        role=Role.SELLER,
        is_active=True,
        created_at=datetime.now(),
    )
    assert user.is_active is True


# --------------------------------------------------------------------------- #
# Brand schemas
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_brand_model_to_out(db_session, create_brand):
    brand = await create_brand("Samsonite")
    out = BrandOut.model_validate(brand)
    assert out.name == "Samsonite"
    assert isinstance(out.id, int)
    assert isinstance(out.created_at, datetime)


def test_brand_create_valid():
    brand = BrandSchema(name="Nike", is_active=False)
    assert brand.name == "Nike"
    assert brand.is_active is False


def test_brand_create_empty_name_rejected():
    with pytest.raises(ValidationError):
        BrandSchema(name="")


def test_brand_create_name_too_long_rejected():
    with pytest.raises(ValidationError):
        BrandSchema(name="x" * 256)


def test_brand_update_partial():
    update = BrandUpdate(name="New")
    assert update.name == "New"
    assert update.is_active is None


def test_brand_paginate_response():
    brand = BrandModel(
        id=1, name="Apple", is_active=True, created_at=datetime.now(), updated_at=datetime.now()
    )
    page = BrandPaginate(total=1, page=1, size=10, items=[brand])
    assert page.total == 1
    assert page.items[0].name == "Apple"


# --------------------------------------------------------------------------- #
# Category schemas
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_category_model_from(db_session, create_category):
    category = await create_category("Clothing")
    out = CategoryOut.model_validate(category)
    assert out.name == "Clothing"
    assert out.is_active is True


def test_category_create_valid():
    category = CategorySchema(name="Shoes")
    assert category.name == "Shoes"


def test_category_create_empty_name_rejected():
    with pytest.raises(ValidationError):
        CategorySchema(name="")


def test_category_update_partial():
    update = CategoryUpdate(is_active=False)
    assert update.is_active is False
    assert update.name is None


def test_category_paginate_response():
    cat = CategoryModel(
        name="Y", is_active=True, created_at=datetime.now(), updated_at=datetime.now()
    )
    cat.id = 5
    paginated = CategoryPaginate(total=1, page=1, size=1, items=[cat])
    assert paginated.items[0].id == 5


# --------------------------------------------------------------------------- #
# Role enum sanity
# --------------------------------------------------------------------------- #
def test_role_enum_values():
    assert Role.SUPER_ADMIN.value == "super_admin"
    assert Role.ADMIN.value == "admin"
    assert Role.STORE_KEEPER.value == "store_keeper"
    assert Role.SELLER.value == "seller"