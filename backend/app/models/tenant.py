from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Tenant(Base):
    """Consultancy tenant record (E8 tenant management; ADR-0001 root entity).

    Tenant profile / branding columns (E10; Journey J3; Requirements §1
    White-labeling + Currency) live on this same row to keep the tenant
    root entity self-contained:

    * ``logo_url`` -- URL of the uploaded tenant logo (E10 task #111 owns the
      upload endpoint). Nullable because the platform seeds tenants before
      any logo is provided.
    * ``brand_color`` -- primary brand color used by the frontend shell to
      theme the app (E10 task #113). Stored as a 7-char ``#RRGGBB`` string.
      Nullable for tenants that have not picked one yet.
    * ``currency`` -- ISO 4217 display/reporting currency code (no live FX
      conversion per Requirements §1 Currency). Defaults to ``"INR"``
      because the home market is India; the helper in :mod:`app.i18n.currency`
      validates the shape when callers (the future PATCH endpoint, task #110)
      need to write to it.
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
<<<<<<< HEAD
    # White-labeling fields (E10 tenant branding & profile; Journey J3;
    # Requirements §1: "Each tenant can upload a logo + set a primary brand color").
    # ``logo_url`` is nullable so a freshly-created tenant has no logo yet.
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # ``brand_color`` stores a CSS hex colour in the canonical "#RRGGBB" form.
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # ``currency`` stores an ISO 4217 three-letter uppercase code; the canonical
    # defaults are validated through ``app.i18n.currency.normalize_currency_code``
    # by the PATCH /tenants/{id}/branding schema.
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
=======
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="INR"
    )
>>>>>>> origin/main
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
