from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class Branch(TenantScopedBase):
    """Branch record under a consultancy tenant (E11 branch management; ADR-0001 tenant-scoped)."""

    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
