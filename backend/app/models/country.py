from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class Country(TenantScopedBase):
    """Admin-managed target country option (E14 master data; Journey J7)."""

    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
