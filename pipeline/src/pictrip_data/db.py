from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from pictrip_data.config import settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        yield conn
    finally:
        conn.close()
