from app.models.base import Base, TenantScopedBase
from app.models.branch import Branch
from app.models.country import Country
from app.models.program import Program
from app.models.tenant import Tenant
from app.models.university import University
from app.models.user import User

__all__ = [
    "Base",
    "TenantScopedBase",
    "Branch",
    "Country",
    "Program",
    "Tenant",
    "University",
    "User",
]
