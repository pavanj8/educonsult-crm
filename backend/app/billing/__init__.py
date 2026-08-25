"""Billing & subscription functionality (E9, E45, E46, E47).

This package contains:
- Razorpay SDK integration and config (E46 task #222)
- Order creation API for plan upgrades (E46 task #223)
- Webhook handler for payment confirmation (E46 task #224)
- Plan change application on confirmed payment (E46 task #225)
"""

from app.billing.config import razorpay_key_id, razorpay_key_secret
from app.billing.plan_change import (
    BillingError,
    PlanChangeResult,
    PlanInactive,
    PlanNotFound,
    TenantNotFound,
    apply_plan_change,
)
from app.billing.razorpay_client import (
    create_order,
    get_client,
    verify_webhook_signature,
)

__all__ = [
    "razorpay_key_id",
    "razorpay_key_secret",
    "get_client",
    "create_order",
    "verify_webhook_signature",
    "apply_plan_change",
    "PlanChangeResult",
    "BillingError",
    "TenantNotFound",
    "PlanNotFound",
    "PlanInactive",
]
