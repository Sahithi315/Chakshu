"""Server-only PostgreSQL connection for Supabase-hosted Chakshu data."""

from datetime import datetime
from functools import lru_cache
import os
from pathlib import Path
import re

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def settings():
    return {**dotenv_values(ROOT / ".env"), **os.environ}


def database_url():
    return settings().get("SUPABASE_DB_URL")


def _json_rows(cursor):
    from psycopg.rows import dict_row

    factory = dict_row(cursor)

    def make_row(values):
        row = factory(values)
        return {key: value.isoformat(sep=" ") if isinstance(value, datetime) else value
                for key, value in row.items()}

    return make_row


def connect():
    from psycopg import ClientCursor
    from psycopg import connect as pg_connect
    from psycopg.conninfo import conninfo_to_dict

    config = conninfo_to_dict(database_url())
    if config.get("host") not in {"localhost", "127.0.0.1", "::1"}:
        if config.get("sslmode") not in {"verify-ca", "verify-full", "require"}:
            config["sslmode"] = "verify-full"
    config.setdefault("connect_timeout", "8")
    connection = pg_connect(
        **config, cursor_factory=ClientCursor,
        row_factory=_json_rows, prepare_threshold=None,
    )
    try:
        connection.execute("SET LOCAL search_path TO chakshu, pg_catalog")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
    except Exception:
        connection.close()
        raise
    return connection


def _postgres_sql(query, has_params):
    ignore = re.search(r"\bINSERT OR IGNORE INTO\b", query, re.IGNORECASE)
    if ignore:
        query = query[:ignore.start()] + "INSERT INTO" + query[ignore.end():]
        query = query.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    query = query.replace("date('now')", "CURRENT_DATE")
    return query.replace("%", "%%").replace("?", "%s") if has_params else query


class Database:
    is_postgres = True

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        return self.connection.execute(_postgres_sql(query, params is not None), params)

    def executemany(self, query, rows):
        with self.connection.cursor() as cursor:
            cursor.executemany(_postgres_sql(query, True), rows)

    def lock(self, key):
        self.execute("SELECT pg_advisory_xact_lock(?)", (key,))
