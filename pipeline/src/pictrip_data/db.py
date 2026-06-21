"""Database connection for the pipeline (psycopg, separate from backend engine)."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from pictrip_data.config import settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Yield a short-lived connection to the shared prod DB (CT110)."""
    with psycopg.connect(settings.database_url) as conn:
        yield conn
