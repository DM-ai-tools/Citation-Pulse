from __future__ import annotations

import uuid

import typer
from sqlalchemy import select

from citationpulse.tasks.geo import fan_out_brand
from citationpulse.db.session import SessionLocal
from citationpulse.models.domain import Brand, PlanType, Prompt, Tenant

app = typer.Typer(no_args_is_help=True)


@app.command()
def add_brand(name: str, domain: str = "") -> None:
    """Create default tenant (if needed) and a brand with optional primary domain."""
    db = SessionLocal()
    try:
        tenant = db.scalars(select(Tenant).order_by(Tenant.created_at.asc())).first()
        if not tenant:
            tenant = Tenant(name="Default", plan=PlanType.SAAS.value)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        domains = [domain] if domain else []
        b = Brand(tenant_id=tenant.id, name=name, domains=domains, competitors=[])
        db.add(b)
        db.commit()
        db.refresh(b)
        typer.echo(f"brand_id={b.id}")
    finally:
        db.close()


@app.command()
def add_prompts(brand_id: str, file: typer.FileText | None = None, text: str | None = None) -> None:
    """Add prompts from --text (one) or stdin/file (one prompt per line)."""
    db = SessionLocal()
    try:
        b = db.get(Brand, uuid.UUID(brand_id))
        if not b:
            raise typer.BadParameter("brand not found")
        lines: list[str] = []
        if text:
            lines = [text]
        elif file:
            lines = [ln.strip() for ln in file if ln.strip()]
        else:
            raise typer.BadParameter("provide --text or --file")
        for line in lines:
            db.add(Prompt(brand_id=b.id, text=line, locale="en-US", enabled=True))
        db.commit()
        typer.echo(f"added {len(lines)} prompts")
    finally:
        db.close()


@app.command()
def trigger_run(brand_id: str) -> None:
    fan_out_brand.delay(brand_id, None)
    typer.echo("enqueued fan_out_brand")


if __name__ == "__main__":
    app()
