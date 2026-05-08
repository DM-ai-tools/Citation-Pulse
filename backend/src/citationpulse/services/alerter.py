from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from citationpulse.core.config import get_settings
from citationpulse.models.domain import Alert, WebhookSubscription

_log = logging.getLogger(__name__)


def _dedupe_key(rule: str, entity_id: str, day: str) -> str:
    return hashlib.sha256(f"{rule}:{entity_id}:{day}".encode()).hexdigest()[:48]


def send_slack(text: str) -> None:
    s = get_settings()
    if not s.slack_webhook_url:
        return
    try:
        httpx.post(s.slack_webhook_url, json={"text": text}, timeout=15.0)
    except Exception as exc:  # noqa: BLE001
        _log.warning("slack failed: %s", exc)


def send_resend_email(subject: str, html: str) -> None:
    s = get_settings()
    if not s.resend_api_key:
        return
    try:
        httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
            json={
                "from": s.alerts_from_email,
                "to": [s.alerts_from_email],
                "subject": subject,
                "html": html,
            },
            timeout=30.0,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("resend failed: %s", exc)


def fire_alert(
    db: Session,
    brand_id: UUID,
    rule: str,
    payload: dict[str, Any],
    channel: str,
) -> Alert | None:
    """Dedupe by (rule, brand, UTC day) per TDD §6.5."""
    day = date.today().isoformat()
    dk = _dedupe_key(rule, str(brand_id), day)
    existing = db.query(Alert).filter(Alert.brand_id == brand_id, Alert.rule == rule).order_by(Alert.fired_at.desc()).first()
    if existing and existing.fired_at.date().isoformat() == day:
        return None
    row = Alert(brand_id=brand_id, rule=rule, payload=payload, channel=channel, fired_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()
    db.refresh(row)
    if channel == "slack":
        send_slack(f"*{rule}* — {json.dumps(payload)[:1500]}")
    if channel == "email":
        send_resend_email(f"CitationPulse: {rule}", f"<pre>{json.dumps(payload, indent=2)}</pre>")
    return row


def dispatch_partner_webhooks(db: Session, tenant_id: UUID, event: str, body: dict[str, Any]) -> None:
    subs = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.tenant_id == tenant_id, WebhookSubscription.active.is_(True))
        .all()
    )
    for sub in subs:
        if event not in (sub.events or []):
            continue
        payload = json.dumps({"event": event, "data": body}).encode()
        sig = hmac.new(sub.secret.encode(), payload, hashlib.sha256).hexdigest()
        try:
            httpx.post(
                sub.url,
                content=payload,
                headers={"X-CitationPulse-Signature": sig, "Content-Type": "application/json"},
                timeout=15.0,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("webhook %s failed: %s", sub.id, exc)
