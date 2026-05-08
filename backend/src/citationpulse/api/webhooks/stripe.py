from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from citationpulse.core.config import get_settings

_log = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=501, detail="Stripe webhook not configured")
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=settings.stripe_webhook_secret,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("stripe webhook invalid: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    et = event.get("type")
    _log.info("stripe event: %s", et)
    # TODO: sync subscription state to tenants.settings / plan
    return {"received": True}
