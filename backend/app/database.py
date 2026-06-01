"""
Database connection pool + RLS context manager.

CRITICAL: Every DB access MUST go through rls_cursor(property_id).
- Uses SET LOCAL so the scope is the transaction only (connection-pool-safe).
- The app role (app_user) is a non-superuser so Postgres enforces RLS.
- Superusers bypass RLS — never connect as postgres/superuser in app code.
"""
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from app.config import DATABASE_URL

_pool: pool.ThreadedConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    global _pool
    _pool = pool.ThreadedConnectionPool(minconn, maxconn, DATABASE_URL)


def close_pool() -> None:
    if _pool:
        _pool.closeall()


@contextmanager
def rls_cursor(property_id: str):
    """
    Yields a psycopg2 cursor scoped to property_id via SET LOCAL.

    Usage:
        with rls_cursor("hotel_a") as cur:
            cur.execute("SELECT * FROM bookings")
            rows = cur.fetchall()

    The SET LOCAL only survives the current transaction.
    If anything raises, the transaction is rolled back.
    """
    assert _pool is not None, "DB pool not initialised — call init_pool() first"
    conn = _pool.getconn()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SET LOCAL app.current_property_id = %s", (property_id,)
            )
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True
        _pool.putconn(conn)


@contextmanager
def raw_cursor():
    """
    A cursor WITHOUT RLS scope — only for superuser/admin operations
    (schema setup, health checks). Never use for tenant data queries.
    """
    assert _pool is not None, "DB pool not initialised"
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
