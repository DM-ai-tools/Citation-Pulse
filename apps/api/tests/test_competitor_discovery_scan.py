"""Scan lifecycle: discovery-before-citations ordering."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from citationpulse.services.competitor_discovery_scan import (  # noqa: E402
    auto_discover_enabled,
    competitor_discovery_pending,
)


class _Scan:
    status = "running"
    competitor_discovery = None
    discovery_params: dict = {"auto_discover": True, "discovery_status": "pending"}


def test_discovery_pending_while_running_before_engines():
    assert competitor_discovery_pending(_Scan()) is True


def test_discovery_not_pending_after_done():
    scan = _Scan()
    scan.discovery_params = {"auto_discover": True, "discovery_status": "done"}
    scan.competitor_discovery = {"target_company": {"name": "x", "domain": "x.com"}}
    assert competitor_discovery_pending(scan) is False


def test_auto_discover_always_enabled_even_when_stored_false():
    scan = _Scan()
    scan.discovery_params = {"auto_discover": False, "discovery_status": "pending"}
    assert auto_discover_enabled(scan) is True
    assert competitor_discovery_pending(scan) is False
