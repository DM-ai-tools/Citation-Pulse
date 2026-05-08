from __future__ import annotations

import logging
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, status

from citationpulse.api.deps import CurrentTenant, DbSession, get_auth_context
from citationpulse.core.config import get_settings

_log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_auth_context)])


@router.post("/billing/checkout-saas")
def checkout_saas(_db: DbSession, tenant: CurrentTenant) -> dict[str, Any]:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_price_saas:
        raise HTTPException(status_code=501, detail="Stripe not configured")
    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_saas, "quantity": 1}],
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        metadata={"tenant_id": str(tenant.id)},
    )
    return {"url": session.url}


@router.post("/billing/checkout-dfy")
def checkout_dfy(_db: DbSession, tenant: CurrentTenant) -> dict[str, Any]:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_price_dfy:
        raise HTTPException(status_code=501, detail="Stripe DFY price not configured")
    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_dfy, "quantity": 1}],
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        metadata={"tenant_id": str(tenant.id), "plan": "dfy"},
    )
    return {"url": session.url}


@router.post("/billing/portal")
def billing_portal(db: DbSession, tenant: CurrentTenant) -> dict[str, Any]:
    settings = get_settings()
    if not settings.stripe_secret_key or not tenant.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on tenant")
    stripe.api_key = settings.stripe_secret_key
    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url="https://example.com/account",
    )
    return {"url": session.url}
