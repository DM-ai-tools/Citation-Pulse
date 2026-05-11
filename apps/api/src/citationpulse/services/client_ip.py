"""Resolve the real client IP behind reverse proxies (Railway, Fly, Cloudflare, etc.).

``X-Forwarded-For`` often lists internal hops first (e.g. ``100.64.x, 203.0.113.5``).
Taking only the first token buckets all users behind the same edge into one rate limit.
"""

from __future__ import annotations

import ipaddress
import re

from starlette.requests import Request

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _parse_ip_token(token: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    t = token.strip().strip('"').strip("'")
    if not t or t.lower() in ("unknown", "null", "-"):
        return None
    if t.startswith("[") and "]" in t:
        t = t[1 : t.index("]")]
    if "%" in t:
        t = t.split("%", 1)[0]
    # IPv4 with port: 203.0.113.1:12345
    if t.count(":") == 1 and "." in t:
        host, _, maybe_port = t.rpartition(":")
        if maybe_port.isdigit():
            t = host
    try:
        return ipaddress.ip_address(t)
    except ValueError:
        return None


def _is_visible_client(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_private:
        return False
    if ip.version == 4 and ip in _CGNAT:
        return False
    return True


def _direct_peer_host(request: Request) -> str | None:
    if request.client and request.client.host:
        return request.client.host
    return None


def _peer_suggests_reverse_proxy(peer: str | None) -> bool:
    if not peer:
        return False
    ip = _parse_ip_token(peer)
    if ip is None:
        return False
    return bool(ip.is_loopback or ip.is_link_local or ip.is_private or (ip.version == 4 and ip in _CGNAT))


def _first_visible_in_xff(xff: str) -> str | None:
    for part in xff.split(","):
        tok = _parse_ip_token(part)
        if tok and _is_visible_client(tok):
            return str(tok)
    return None


def _last_visible_in_xff(xff: str) -> str | None:
    """Some proxies append the original client at the end of the chain."""
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    for part in reversed(parts):
        tok = _parse_ip_token(part)
        if tok and _is_visible_client(tok):
            return str(tok)
    return None


_forwarded_for_re = re.compile(r"\bfor=\s*([^;,\s]+)", re.IGNORECASE)


def _first_visible_in_forwarded(header_value: str) -> str | None:
    for m in _forwarded_for_re.finditer(header_value):
        raw = m.group(1).strip('"').strip("'")
        if raw.startswith("_") or raw.startswith(":"):
            continue
        tok = _parse_ip_token(raw.removeprefix("IPv6:").removeprefix("IPv4:"))
        if tok and _is_visible_client(tok):
            return str(tok)
    return None


def effective_client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting and logs."""
    peer = _direct_peer_host(request)
    hs = request.headers
    trust = _peer_suggests_reverse_proxy(peer)

    if trust:
        for key in ("cf-connecting-ip", "true-client-ip", "fly-client-ip", "x-real-ip"):
            v = (hs.get(key) or "").strip()
            if not v or v.lower() == "unknown":
                continue
            tok = _parse_ip_token(v.split(",")[0])
            if tok and _is_visible_client(tok):
                return str(tok)

        xff = (hs.get("x-forwarded-for") or "").strip()
        if xff:
            hit = _first_visible_in_xff(xff)
            if hit:
                return hit
            hit = _last_visible_in_xff(xff)
            if hit:
                return hit

        fwd = (hs.get("forwarded") or "").strip()
        if fwd:
            hit = _first_visible_in_forwarded(fwd)
            if hit:
                return hit

    if peer:
        tok = _parse_ip_token(peer)
        if tok and _is_visible_client(tok):
            return str(tok)
        return peer
    return "unknown"


def is_mesh_or_unresolved_client_ip(ip: str) -> bool:
    """True when we cannot see a real internet client — shared infra (Railway 100.64/10) or missing IP.

    Rate limits keyed only on these addresses collapse many users into one bucket; callers
    should use a dedicated high cap or a synthetic key (see scans router).
    """
    if not ip or ip == "unknown":
        return True
    tok = _parse_ip_token(ip)
    if tok is None:
        return True
    if tok.version == 4 and tok in _CGNAT:
        return True
    return False
