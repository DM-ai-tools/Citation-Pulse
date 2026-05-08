"""Write OpenAPI schema to packages/shared-types/openapi.json (run from repo root or apps/api)."""

from __future__ import annotations

import json
from pathlib import Path

from citationpulse.main import app

def main() -> None:
    root = Path(__file__).resolve().parents[3]
    out = root / "packages" / "shared-types" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
