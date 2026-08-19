from typing import List
from app.core import BaseSkeleton
from sqlalchemy.orm import Mapped, relationship


class Brand(BaseSkeleton):
    __tablename__ = "brands"

    # back_populates must match the attribute Product actually declares
    # ("brand", singular) - it previously pointed at "brands", which
    # doesn't exist on Product and fails at mapper configuration time.
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="brand"
    )

    def __repr__(self):
        return f"<Brand(id={self.id}, name={self.name})>"
