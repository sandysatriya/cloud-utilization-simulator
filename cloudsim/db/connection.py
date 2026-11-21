import sqlite3
from contextlib import contextmanager
from pathlib import Path

from cloudsim.config import env_db_path


def connect(db_path=None) -> sqlite3.Connection:
    path = Path(db_path or env_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def transaction(db_path=None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def read_connection(db_path=None):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
