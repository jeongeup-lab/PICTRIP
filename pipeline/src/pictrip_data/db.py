"""Database connection for the pipeline (psycopg, separate from backend engine)."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from pictrip_data.config import settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """One psycopg connection, autocommit off (caller commits per page)."""
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        yield conn
    finally:
        conn.close()
