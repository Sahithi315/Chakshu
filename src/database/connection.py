"""Database connection management and helper utilities."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from .schema import get_db_path, init_db


@contextmanager
def get_db(db_path=None, conn=None):
    """Context manager for SQLite connection with row factories and automatic commit/rollback.
    If an existing connection `conn` is provided, it is yielded directly without re-opening."""
    if conn is not None:
        yield conn
        return

    path = Path(db_path) if db_path else get_db_path()
    if not path.exists():
        init_db(path)
    # Set timeout to 30s to prevent transient locks under concurrent access
    c = sqlite3.connect(str(path), timeout=30.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
