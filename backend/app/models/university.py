from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class University(TenantScopedBase):
    """Admin-managed university option scoped to a country (E14 master data)."""

    __tablename__ = "universities"

    country_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("countries.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
