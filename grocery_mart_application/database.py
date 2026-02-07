from __future__ import annotations

import sqlite3
from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterable

_DEFAULT_DB_PATH = Path.cwd() / "grocery_inventory.db"
DB_PATH = Path(os.environ.get("GROCERY_MART_DB_PATH", str(_DEFAULT_DB_PATH))).expanduser().resolve()


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    """
    Backwards-compatible helper.

    Prefer `connect()` to ensure connections are always closed.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _add_columns_if_missing(conn: sqlite3.Connection, table: str, columns_sql: Iterable[str]) -> None:
    existing = _table_columns(conn, table)
    cur = conn.cursor()
    for col in columns_sql:
        col_name = col.split()[0].strip()
        if col_name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col}")


def setup_database() -> None:
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                expiry TEXT,
                supplier_id INTEGER,
                barcode TEXT,
                gst_percent REAL DEFAULT 0,
                tax_percent REAL DEFAULT 0
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        # Lightweight migrations for older DBs.
        _add_columns_if_missing(
            conn,
            "sales",
            [
                "buyer_name TEXT",
                "buyer_mobile TEXT",
                "unit_price REAL",
                "subtotal REAL",
                "gst_percent REAL",
                "tax_percent REAL",
                "tax_amount REAL",
                "total_price REAL",
                "invoice_path TEXT",
            ],
        )
        _add_columns_if_missing(
            conn,
            "products",
            [
                "supplier_id INTEGER",
                "barcode TEXT",
                "gst_percent REAL DEFAULT 0",
                "tax_percent REAL DEFAULT 0",
            ],
        )

        # Barcode lookup should be fast and (ideally) unique. If a DB already contains duplicates,
        # creating a unique index would fail; keep startup resilient by ignoring that error.
        try:
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode
                   ON products(barcode)
                   WHERE barcode IS NOT NULL AND barcode <> ''"""
            )
        except Exception:
            pass

        conn.commit()


def log_event(event_type: str, message: str, username: str | None = None) -> None:
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (event_type, message, username) VALUES (?, ?, ?)",
                (event_type, message, username),
            )
            conn.commit()
    except Exception:
        # Logging must never crash the UI.
        return
