from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from auth_service import ensure_default_admin
from database import DB_PATH, connect, setup_database


def _maybe_reset_db(reset: bool) -> None:
    if not reset:
        return
    if DB_PATH.exists():
        DB_PATH.unlink()


def seed_demo(reset: bool = False) -> None:
    """
    Populate the database with a small demo dataset.

    Safe by default:
    - If the DB already has products, it won't insert duplicates (unless --reset is used).
    """
    _maybe_reset_db(reset=reset)
    setup_database()
    ensure_default_admin()

    with connect() as conn:
        cur = conn.cursor()

        has_products = int(cur.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]) > 0
        if has_products and not reset:
            print("Demo seed skipped: products already exist (use --reset to recreate DB).")
            return

        # Suppliers
        cur.execute("DELETE FROM suppliers")
        suppliers = [
            ("Fresh Farms", "fresh-farms@example.com"),
            ("Daily Dairy", "daily-dairy@example.com"),
            ("Snack Hub", "snack-hub@example.com"),
        ]
        cur.executemany("INSERT INTO suppliers (name, contact) VALUES (?, ?)", suppliers)
        supplier_ids = {r["name"]: int(r["id"]) for r in cur.execute("SELECT id, name FROM suppliers").fetchall()}

        # Products
        cur.execute("DELETE FROM products")
        products = [
            ("Dal", "Pulses", "kg", 120.0, 64, "2026-12-20", supplier_ids["Fresh Farms"], "8901000000001", 0.0, 0.0),
            ("Parley", "Snacks", "pcs", 5.0, 148, "2026-11-10", supplier_ids["Snack Hub"], "8901000000002", 5.0, 0.0),
            ("Milk", "Dairy", "ltr", 55.0, 22, "2026-02-25", supplier_ids["Daily Dairy"], "8901000000003", 0.0, 0.0),
        ]
        cur.executemany(
            """INSERT INTO products
               (name, category, unit, price, quantity, expiry, supplier_id, barcode, gst_percent, tax_percent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            products,
        )

        # Sales history
        cur.execute("DELETE FROM sales")
        now = datetime.now()
        sample_sales = []
        for i in range(14):
            d = now - timedelta(days=i)
            sample_sales.append(
                (
                    "Dal",
                    2,
                    d.strftime("%Y-%m-%d %H:%M:%S"),
                    "Demo Customer",
                    "9000000000",
                    120.0,
                    240.0,
                    0.0,
                    0.0,
                    0.0,
                    240.0,
                    "",
                )
            )
        cur.executemany(
            """INSERT INTO sales
               (product_name, quantity, sale_date, buyer_name, buyer_mobile, unit_price, subtotal,
                gst_percent, tax_percent, tax_amount, total_price, invoice_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            sample_sales,
        )

        conn.commit()
        print(f"Demo data seeded into: {Path(DB_PATH).resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo data for Grocery Mart Inventory Manager.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing DB file and recreate it before inserting demo data.",
    )
    args = parser.parse_args()
    seed_demo(reset=bool(args.reset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

