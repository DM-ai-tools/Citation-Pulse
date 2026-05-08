from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import tldextract


def canonicalize_url(url: str) -> str:
    """Strip UTM-like params, normalize host/path (TDD §6.3)."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if not host and parsed.path:
        parsed = urlparse("https://" + url.strip())
        host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    path = re.sub(r"/+", "/", path).rstrip("/") or "/"
    drop_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
    }
    qs = parse_qs(parsed.query, keep_blank_values=True)
    q = [(k, v) for k in sorted(qs) if k.lower() not in drop_keys for v in qs[k]]
    query = urlencode(q) if q else ""
    return urlunparse(("https", host, path, "", query, ""))


def registrable_domain(url: str) -> str:
    ext = tldextract.extract(url)
    if ext.registered_domain:
        return ext.registered_domain.lower()
    host = urlparse(url).hostname or ""
    return host.lower()


def citation_dedupe_key(url_canonical: str, snippet: str | None) -> str:
    h = hashlib.sha256()
    h.update(url_canonical.encode())
    h.update(b"|")
    h.update((snippet or "").encode())
    return h.hexdigest()[:64]
