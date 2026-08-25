"""Pydantic schemas for billing endpoints (E46; Journey J39).

Webhook schemas for Razorpay payment confirmation.
"""

from pydantic import BaseModel, Field


class WebhookErrorResponse(BaseModel):
    """Response returned when webhook validation fails."""

    detail: str = Field(description="Error message describing why the webhook was rejected")


__all__ = ["WebhookErrorResponse"]
