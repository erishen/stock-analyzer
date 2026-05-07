import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def db_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def db_transaction(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
