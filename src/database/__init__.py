"""Database package for persistent storage of patients, visits, reports, and summaries."""
from .schema import init_db, get_db_path
from .connection import get_db

__all__ = ["init_db", "get_db_path", "get_db"]
