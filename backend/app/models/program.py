from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase


class Program(TenantScopedBase):
    """Admin-managed program option scoped to a university (E14 master data)."""

    __tablename__ = "programs"

    university_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("universities.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
