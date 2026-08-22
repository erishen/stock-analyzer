import logging
import sqlite3
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .paths import get_asset_lens_db_path

_logger = logging.getLogger(__name__)


@contextmanager
def db_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    if db_path is None:
        db_path = get_asset_lens_db_path()
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        _logger.error("Database error, rolling back: %s", e)
        conn.rollback()
        raise
    except Exception as e:
        _logger.error("Unexpected error, rolling back: %s", e)
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def db_transaction(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    warnings.warn(
        "db_transaction is deprecated, use db_connection instead",
        DeprecationWarning,
        stacklevel=2,
    )
    with db_connection(db_path) as conn:
        yield conn
