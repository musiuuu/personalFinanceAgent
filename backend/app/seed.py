"""Seed the demo with sample statements on first boot.

Free-tier hosts have an ephemeral filesystem, so the SQLite DB resets when the
service restarts. Seeding on startup (env-gated, only when the ledger is empty)
keeps the live demo populated without any manual upload.
"""
from pathlib import Path

from sqlmodel import select

from .config import get_settings
from .db import session_scope
from .ingestion.router import ingest_file
from .models import Transaction


def seed_if_empty() -> None:
    settings = get_settings()
    if not settings.seed_on_startup:
        return
    with session_scope() as session:
        if session.exec(select(Transaction)).first() is not None:
            return  # already has data
        data_dir = Path(settings.seed_data_dir)
        if not data_dir.is_dir():
            return
        for csv_path in sorted(data_dir.glob("hbl_statement_*.csv")):
            try:
                ingest_file(session, csv_path)
            except Exception:
                # A bad sample file must never crash startup.
                continue
