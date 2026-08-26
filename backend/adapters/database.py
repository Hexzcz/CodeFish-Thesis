"""The Postgres/Supabase connection, when there is one.

The database is optional: without `DATABASE_URL` the app reads the bundled
GeoJSON instead (see ADR-0002). So the engine is built lazily and asking for a
connection when none is configured raises rather than pretending — the loaders
already treat that as "fall back to the files".
"""
from sqlalchemy import create_engine

from backend.core.config import DATABASE_URL


class DatabaseNotConfigured(RuntimeError):
    """No DATABASE_URL. Not an error on its own — the files are the fallback."""


_engine = None


def is_database_configured() -> bool:
    return bool(DATABASE_URL)


def get_db_connection():
    global _engine

    if not DATABASE_URL:
        raise DatabaseNotConfigured(
            "No DATABASE_URL is set, so there is no database to read from. "
            "The bundled GeoJSON in backend/data/ is used instead."
        )

    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    return _engine.connect()
