# Grocery Mart Inventory Manager

A local-first desktop grocery inventory and sales manager built with Python, Tkinter, ttkbootstrap, and SQLite.

## Features

- Inventory: products, stock levels, expiry, barcode, supplier, GST% and Tax% per product
- Sales: multi-item invoices, live invoice preview, PDF generation, invoice browser + print last invoice
- Analytics: KPIs, stock breakdown, sales trend, top products, exportable sales report
- Exports: Excel/CSV for products, sales, suppliers
- Activity monitor (audit log) with CSV export
- Session lock mode
- Optional barcode scanning mode (manual entry + camera preview)
- Global and page-level keyboard shortcuts (press `F1` in the app)

## Requirements

- Python **3.11+** (3.12 recommended)

## Setup

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Initialize / migrate the database (optional; the app auto-creates tables on first run):
   - `python init_db.py`
3. Run the app:
   - `python main.py`

## Demo dataset (optional)

Seed sample suppliers/products/sales:

- `python scripts/seed_demo.py`

Recreate the database and seed clean demo data:

- `python scripts/seed_demo.py --reset`

## Camera barcode scanning (optional)

The Inventory screen supports camera barcode scanning. It is optional because camera + barcode libraries can pull in
native dependencies (and may upgrade NumPy in some environments).

Install the base app first:
- `pip install -r requirements.txt`

Then (optional) install camera scanning deps:
- `pip install -r requirements-camera.txt`

Notes:
- Windows `pyzbar` may also require the ZBar library available on PATH.
- If installing camera deps upgrades NumPy and breaks other compiled packages (e.g. matplotlib), use a clean virtual
  environment/conda environment for this app.

## Login

- Default admin user: `admin`
- Default admin password: `admin`

After logging in, change the password in **Settings -> Change Password**.

## Docs

- `docs/USAGE.md` – how to use each screen + shortcuts
- `docs/DESCRIPTION.md` – architecture, modules, and troubleshooting notes

## Data & privacy

This is a local-first app:
- Data is stored on your machine in `grocery_inventory.db`
- Generated invoices are saved under `invoices/`

## Contributing

See `CONTRIBUTING.md`. CI runs via GitHub Actions in `.github/workflows/ci.yml`.

