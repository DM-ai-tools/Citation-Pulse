"""Resolve monorepo vs Docker (/app) layout for config and .env discovery."""

from __future__ import annotations

from pathlib import Path


def resolve_app_roots(config_file: Path | None = None) -> tuple[Path, Path]:
    """Return (repo_root, api_root) for ``.../citationpulse/core/config.py`` or similar."""
    cfg = (config_file or Path(__file__).resolve().parent / "config.py").resolve()
    if cfg.name != "config.py":
        cfg = Path(__file__).resolve()
    # .../src/citationpulse/core/config.py -> api root is parents[3] (/app or apps/api)
    api_root = cfg.parents[3]

    if api_root.name == "api" and api_root.parent.name == "apps":
        repo_root = api_root.parent.parent
    else:
        repo_root = api_root
        for candidate in (api_root.parent, api_root):
            if (candidate / ".env").is_file():
                repo_root = candidate
                break

    return repo_root, api_root
