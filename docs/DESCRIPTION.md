# Description

**Grocery Mart Inventory Manager** is a local-first desktop app for small shops to manage:

- Product catalog + stock quantity
- Suppliers
- Sales / invoice generation (PDF) with live preview
- Taxes per product (GST% and Tax%) and tax calculation during sales
- Exports (Excel/CSV) and basic analytics
- Activity monitor / audit trail
- Session lock

## Tech stack

- UI: Python `tkinter` + `ttkbootstrap`
- Database: SQLite (`grocery_inventory.db`)
- Charts: `matplotlib` (Analytics screen)
- Exports: `pandas` + `openpyxl` (Excel)
- PDF: `fpdf2`
- Optional barcode scanning: `opencv-contrib-python` + `pyzbar` (plus system ZBar on some platforms)

## Data layout

- `grocery_inventory.db` – main SQLite database (products, suppliers, sales, activity log, settings)
- `invoices/` – generated invoice PDFs
- `logo/` – UI images (app/login background and login logo)
- `styles/` – theme + app settings JSON

## High-level modules

- `main.py` – app bootstrap, theme load, switches between login and dashboard
- `user_auth.py` – login UI
- `dashboard.py` – main shell (sidebar + content area), app background, global shortcuts
- `inventory_manager.py` – inventory screen (CRUD, search/table, barcode scan mode)
- `sales_manager.py` – sales screen (cart, taxes, invoice preview, PDF generation)
- `analytics_dashboard.py` – analytics screen (KPIs + charts + report export)
- `supplier_manager.py` – supplier management
- `settings_manager.py` – UI/theme + backup/restore + password + system settings
- `extra_panel.py` – export center, invoices browser, search panel, monitor panel, lock panel
- `database.py` – DB connect + schema helpers + activity logging
- `utils/app_settings.py` – persisted settings read/write
- `utils/helpers.py` – shared validators/helpers

## Notes / troubleshooting

- If installing camera/scanner dependencies upgrades NumPy to 2.x and breaks packages compiled against NumPy 1.x
  (e.g. some `matplotlib` wheels), use a clean virtual environment dedicated to this app and keep `numpy<2`.
- If you see `You have both PyFPDF & fpdf2 installed`, uninstall the legacy package:
  - `pip uninstall --yes pypdf`
  - `pip install --upgrade fpdf2`

