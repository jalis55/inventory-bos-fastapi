from typing import List
from app.core import BaseSkeleton
from sqlalchemy.orm import Mapped, relationship


class Category(BaseSkeleton):
    __tablename__ = "categories"

    # back_populates must match the attribute Product actually declares
    # ("category", singular) - it previously pointed at "categories",
    # which doesn't exist on Product and fails at mapper configuration time.
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category"
    )

    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name})>"
