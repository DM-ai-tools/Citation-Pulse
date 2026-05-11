from __future__ import annotations

import json
import logging
from typing import Any, BinaryIO

import boto3
from botocore.config import Config

from citationpulse.core.config import get_settings

_log = logging.getLogger(__name__)


def get_r2_client():
    s = get_settings()
    if not s.r2_access_key_id or not s.r2_secret_access_key or not s.r2_account_id:
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_raw_payload(key: str, body: bytes | BinaryIO, content_type: str = "application/json") -> str | None:
    client = get_r2_client()
    if not client:
        _log.debug("R2 not configured; skipping raw upload for %s", key)
        return None
    s = get_settings()
    client.put_object(Bucket=s.r2_bucket_raw_payloads, Key=key, Body=body, ContentType=content_type)
    if s.r2_public_base_url:
        return f"{s.r2_public_base_url.rstrip('/')}/{key}"
    return key


def upload_openrouter_response_raw(key: str, raw: dict[str, Any]) -> None:
    """Best-effort store of OpenRouter JSON for debugging. Never raises."""
    try:
        body = json.dumps(raw, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _log.debug("OpenRouter raw not fully JSON-serializable for %s: %s", key, exc)
        body = json.dumps(
            {"_note": "serialization fallback", "error": str(exc), "top_keys": list(raw.keys())[:80]},
            default=str,
        ).encode("utf-8")
    upload_raw_payload(key, body, "application/json")
