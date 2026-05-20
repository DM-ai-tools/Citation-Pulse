"""Database URL normalization for SQLAlchemy + Celery (Railway Postgres)."""

from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """Force psycopg v3 driver — plain ``postgresql://`` defaults to psycopg2 in SQLAlchemy."""
    s = (url or "").strip()
    if not s:
        return s
    if s.startswith("postgres://"):
        return "postgresql+psycopg://" + s[len("postgres://") :]
    if s.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + s[len("postgresql+psycopg2://") :]
    if s.startswith("postgresql://"):
        return "postgresql+psycopg://" + s[len("postgresql://") :]
    return s
