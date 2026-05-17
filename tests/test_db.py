import sqlite3
import tempfile
from pathlib import Path

import pytest

from db import db_connection, db_transaction


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

    yield db_path

    db_path.unlink(missing_ok=True)


class TestDbConnection:
    def test_connection_works(self, temp_db):
        with db_connection(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            assert cursor.fetchone()[0] == 0

    def test_connection_closed_after_context(self, temp_db):
        with db_connection(temp_db) as conn:
            conn.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))

        with db_connection(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            assert cursor.fetchone()[0] == 1

    def test_connection_on_error(self, temp_db):
        with pytest.raises(sqlite3.OperationalError), db_connection(temp_db) as conn:
            conn.execute("SELECT * FROM nonexistent_table")


class TestDbTransaction:
    def test_transaction_commit(self, temp_db):
        with db_transaction(temp_db) as conn:
            conn.execute("INSERT INTO test_table (name) VALUES (?)", ("committed",))

        with db_connection(temp_db) as conn:
            cursor = conn.execute("SELECT name FROM test_table")
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "committed"

    def test_transaction_rollback_on_error(self, temp_db):
        try:
            with db_transaction(temp_db) as conn:
                conn.execute("INSERT INTO test_table (name) VALUES (?)", ("rollback_test",))
                raise ValueError("force rollback")
        except ValueError:
            pass

        with db_connection(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            assert cursor.fetchone()[0] == 0

    def test_transaction_multiple_operations(self, temp_db):
        with db_transaction(temp_db) as conn:
            conn.execute("INSERT INTO test_table (name) VALUES (?)", ("row1",))
            conn.execute("INSERT INTO test_table (name) VALUES (?)", ("row2",))

        with db_connection(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            assert cursor.fetchone()[0] == 2
