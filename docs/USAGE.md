# Usage Guide

## Start / Login

1. Run the app: `python main.py`
2. Default credentials:
   - Username: `admin`
   - Password: `admin`
3. After first login, change the admin password in **Settings -> Change Password**.

## Global keyboard shortcuts

- `F1` – show shortcut help
- `F5` – refresh current page (if supported)
- `Ctrl+1..0` – navigate: Home, Inventory, Sales, Suppliers, Analytics, Export, Invoices, Search, Monitor, Settings
- `Ctrl+L` – lock session
- `Ctrl+Shift+Q` – logout

## Page shortcuts (depends on screen)

Common:
- `Ctrl+F` – focus the page search/filter box (if present)
- `Ctrl+Enter` – primary page action (if supported)
- `Delete` – delete selected row/item (if supported)
- `Ctrl+E` – export (if supported)
- `Ctrl+N` – new/clear form (if supported)
- `Ctrl+P` – print (if supported)
- `Ctrl+R` – record/run main action (if supported)

## Inventory screen

Use **Inventory** to maintain your product catalog and stock.

Typical workflow:
- Add a product (name, barcode, category, supplier, unit, price, GST%, Tax%, quantity, expiry)
- Update price/stock and supplier data
- Search/filter the table

Barcode scan mode:
- Toggle **Scan Mode**
- Enter/scan a barcode into the barcode field
- Choose action: `Receive (+)`, `Dispatch (-)`, `Set Qty`
- Enter Qty
- Apply

Shortcut highlights:
- `Ctrl+F` focuses the search box
- `Ctrl+Enter` applies barcode action (only when Scan Mode is ON)
- `Ctrl+E` export inventory
- `Ctrl+N` clear the form
- `Delete` delete selected product (when a row is selected)

## Sales screen

Use **Sales** to build an invoice (multiple items) and record the sale.

Workflow:
- Enter Buyer Name and Mobile
- Select a product, set Quantity Sold
- Use **Add Item** (repeat for multiple items)
- Use **Update Qty / Delete Item / Clear Items** as needed
- Use **Record Sale** to generate the PDF invoice
- Use **Print Last Invoice** to print the most recent invoice

Taxes:
- GST% and Tax% are fetched from the product record
- Totals and tax amounts are calculated per line and in the invoice summary

Shortcut highlights:
- `Ctrl+Enter` add item to invoice
- `Ctrl+R` record sale
- `Ctrl+P` print last invoice
- `Delete` delete selected invoice item

## Analytics screen

Use **Analytics** for KPIs and charts:
- Revenue, Sales count, Items sold, Average sale amount, Tax collected, Low stock count
- Stock breakdown by category
- Sales trend (daily/weekly/monthly)
- Top products by revenue

Filters:
- Choose a preset range (Today / Last 7 / Last 30 / etc.) or a custom date range.

Shortcut highlights:
- `F5` refresh charts
- `Ctrl+E` export report for the selected range

## Monitor screen

Use **Monitor** to view an activity feed (auto-refresh) and export it to CSV.

Shortcut highlights:
- `Ctrl+F` focus search
- `Ctrl+E` export CSV

## Lock mode

When you lock the session:
- Navigation and logout are disabled
- Only the unlock screen is accessible until you enter the correct password

