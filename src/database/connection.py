from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from config import config

DEFAULT_DB_PATH = config.data_dir / "aqi_monitoring.db"


class DatabaseError(Exception):
    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.original = original


def resolve_db_path(db_path: Path | str | None = None) -> Path:
    if db_path is None:
        target = DEFAULT_DB_PATH
    elif isinstance(db_path, str):
        if db_path == ":memory:":
            return Path(":memory:")
        target = Path(db_path)
    else:
        target = db_path

    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


@contextmanager
def get_connection(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    resolved = resolve_db_path(db_path)
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(resolved), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if str(resolved) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError(f"SQLite operation failed: {exc}", original=exc) from exc
    finally:
        if conn is not None:
            conn.close()