from __future__ import annotations

import csv
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from ttkbootstrap import Button, Checkbutton, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview

from database import connect, log_event
from auth_service import verify_credentials
from utils.app_settings import get_setting, update_settings

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


class ExportDataPanel(Frame):
    def __init__(self, master, current_user: str | None = None):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.pack(fill=tk.BOTH, expand=True)

        self.export_format = StringVar(value="Excel (.xlsx)")
        self.include_taxes = tk.BooleanVar(value=True)
        self.include_barcodes = tk.BooleanVar(value=True)
        self.date_from = StringVar(value="")
        self.date_to = StringVar(value="")
        self.status = StringVar(value="")

        Label(self, text="Export Center", font=("Helvetica", 20, "bold")).pack(pady=(10, 2))
        Label(
            self,
            text="Export Grocery Mart data for accounting, stock checks, and reporting.",
            bootstyle="secondary",
        ).pack(pady=(0, 12))

        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=6, pady=(0, 10))
        top.grid_columnconfigure(1, weight=1)

        cfg = tk.LabelFrame(top, text="Export Options", padx=10, pady=8)
        cfg.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        cfg.grid_columnconfigure(1, weight=1)

        Label(cfg, text="Format:").grid(row=0, column=0, sticky="w", pady=4)
        Combobox(
            cfg,
            textvariable=self.export_format,
            values=["Excel (.xlsx)", "CSV (.csv)"],
            state="readonly",
            width=14,
        ).grid(row=0, column=1, sticky="w", pady=4)

        Checkbutton(cfg, text="Include barcodes", variable=self.include_barcodes).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=4
        )
        Checkbutton(cfg, text="Include GST/Tax columns", variable=self.include_taxes).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=4
        )

        Label(cfg, text="Sales date from (YYYY-MM-DD):").grid(row=3, column=0, sticky="w", pady=(10, 4))
        Entry(cfg, textvariable=self.date_from, width=18).grid(row=3, column=1, sticky="w", pady=(10, 4))
        Label(cfg, text="to:").grid(row=4, column=0, sticky="w", pady=4)
        Entry(cfg, textvariable=self.date_to, width=18).grid(row=4, column=1, sticky="w", pady=4)

        tips = tk.LabelFrame(top, text="Tips", padx=10, pady=8)
        tips.grid(row=0, column=1, sticky="nsew")
        tips.grid_columnconfigure(0, weight=1)
        Label(
            tips,
            text=(
                "• Use CSV for quick sharing.\n"
                "• Use Excel for accounting and formatting.\n"
                "• Sales export can be filtered by date range.\n"
                "• For backups/restores, use Settings → System."
            ),
            justify="left",
            bootstyle="secondary",
        ).grid(row=0, column=0, sticky="w")

        actions = tk.LabelFrame(self, text="Quick Exports", padx=10, pady=10)
        actions.pack(padx=6, pady=(0, 10))

        Button(actions, text="Products (Catalog)", bootstyle="success", width=20, command=self.export_products).grid(
            row=0, column=0, padx=8, pady=6
        )
        Button(actions, text="Inventory (Stock)", bootstyle="success-outline", width=20, command=self.export_inventory).grid(
            row=0, column=1, padx=8, pady=6
        )
        Button(actions, text="Sales (Invoices)", bootstyle="info", width=20, command=self.export_sales).grid(
            row=0, column=2, padx=8, pady=6
        )
        Button(actions, text="Suppliers", bootstyle="secondary", width=20, command=self.export_suppliers).grid(
            row=0, column=3, padx=8, pady=6
        )

        Label(self, textvariable=self.status, bootstyle="secondary").pack(anchor="w", padx=10, pady=(0, 6))
        Label(
            self,
            text="Tip: Excel export requires openpyxl installed (pip install openpyxl).",
            font=("Helvetica", 9, "italic"),
        ).pack(pady=(6, 0))

    def _save_path(self, default_name: str) -> Path | None:
        want_csv = self.export_format.get().lower().startswith("csv")
        if want_csv:
            default_name = Path(default_name).with_suffix(".csv").name
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=default_name,
                filetypes=[("CSV", "*.csv")],
            )
        else:
            default_name = Path(default_name).with_suffix(".xlsx").name
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                initialfile=default_name,
                filetypes=[("Excel Workbook", "*.xlsx"), ("CSV", "*.csv")],
            )
        return Path(path) if path else None

    def _export_df(self, df: pd.DataFrame, default_name: str, event_label: str) -> None:
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return
        out = self._save_path(default_name)
        if not out:
            return
        try:
            if out.suffix.lower() == ".csv":
                df.to_csv(out, index=False)
            else:
                df.to_excel(out, index=False)
            log_event("export", f"{event_label} exported to {out.name}", self.current_user)
            messagebox.showinfo("Exported", f"Saved: {out}")
            self.status.set(f"Exported {event_label}: {out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def export_products(self) -> None:
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return
        cols = ["id", "name"]
        if self.include_barcodes.get():
            cols.append("barcode")
        cols += ["category", "unit", "price"]
        if self.include_taxes.get():
            cols += ["gst_percent", "tax_percent"]
        cols += ["quantity", "expiry", "supplier_id"]
        with connect() as conn:
            rows = conn.execute(f"SELECT {', '.join(cols)} FROM products ORDER BY id DESC").fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        self._export_df(df, f"Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "Products")

    def export_inventory(self) -> None:
        self.export_products()

    def export_sales(self) -> None:
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return
        where = ""
        params: list[object] = []
        df_raw = self.date_from.get().strip()
        dt_raw = self.date_to.get().strip()
        if df_raw:
            where += " AND DATE(sale_date) >= DATE(?)"
            params.append(df_raw)
        if dt_raw:
            where += " AND DATE(sale_date) <= DATE(?)"
            params.append(dt_raw)

        cols = ["id", "product_name", "quantity", "unit_price", "subtotal"]
        if self.include_taxes.get():
            cols += ["gst_percent", "tax_percent", "tax_amount"]
        cols += ["total_price", "buyer_name", "buyer_mobile", "sale_date", "invoice_path"]

        with connect() as conn:
            rows = conn.execute(
                f"""SELECT {', '.join(cols)}
                    FROM sales
                    WHERE 1=1 {where}
                    ORDER BY sale_date DESC""",
                tuple(params),
            ).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        self._export_df(df, f"Sales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "Sales")

    def export_suppliers(self) -> None:
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return
        with connect() as conn:
            rows = conn.execute("SELECT id, name, contact FROM suppliers ORDER BY id DESC").fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        self._export_df(df, f"Suppliers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "Suppliers")


class InvoiceManagerPanel(Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.pack(fill=tk.BOTH, expand=True)
        self.query = StringVar(value="")
        self.date_from = StringVar(value="")
        self.date_to = StringVar(value="")
        self.status = StringVar(value="")
        self._query_entry: Entry | None = None

        Label(self, text="Invoices", font=("Helvetica", 20, "bold")).pack(pady=(10, 2))
        Label(
            self,
            text="Browse and open invoices generated from Sales. Filter by customer or date.",
            bootstyle="secondary",
        ).pack(pady=(0, 12))

        controls = tk.LabelFrame(self, text="Find Invoices", padx=10, pady=8)
        controls.pack(fill=tk.X, padx=6, pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)

        Label(controls, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self._query_entry = Entry(controls, textvariable=self.query, width=40)
        self._query_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)
        Button(controls, text="Refresh", bootstyle="primary-outline", command=self.refresh).grid(
            row=0, column=2, sticky="e", padx=(0, 8), pady=4
        )
        Button(controls, text="Open Folder", bootstyle="info-outline", command=self.open_folder).grid(
            row=0, column=3, sticky="e", pady=4
        )

        Label(controls, text="From (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        Entry(controls, textvariable=self.date_from, width=16).grid(row=1, column=1, sticky="w", pady=4)
        Label(controls, text="To:").grid(row=1, column=2, sticky="w", padx=(0, 6), pady=4)
        Entry(controls, textvariable=self.date_to, width=16).grid(row=1, column=3, sticky="w", pady=4)

        actions = tk.Frame(self)
        actions.pack(fill=tk.X, padx=6, pady=(0, 10))
        Button(actions, text="Open Selected", bootstyle="success", command=self.open_selected).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        Button(actions, text="Open Containing Folder", bootstyle="secondary-outline", command=self.open_selected_folder).pack(
            side=tk.LEFT, padx=8
        )
        Button(actions, text="Copy Path", bootstyle="secondary-outline", command=self.copy_selected_path).pack(
            side=tk.LEFT, padx=8
        )

        Label(self, textvariable=self.status, bootstyle="secondary").pack(anchor="w", padx=10, pady=(0, 6))

        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.tree = Treeview(
            table_frame,
            columns=("sale_date", "buyer", "mobile", "total", "invoice_path"),
            show="headings",
        )
        self.tree.heading("sale_date", text="Date")
        self.tree.heading("buyer", text="Buyer")
        self.tree.heading("mobile", text="Mobile")
        self.tree.heading("total", text="Total")
        self.tree.heading("invoice_path", text="Invoice File")

        self.tree.column("sale_date", anchor="w", width=160, stretch=False)
        self.tree.column("buyer", anchor="w", width=180, stretch=False)
        self.tree.column("mobile", anchor="center", width=130, stretch=False)
        self.tree.column("total", anchor="e", width=110, stretch=False)
        self.tree.column("invoice_path", anchor="w", width=520)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = Scrollbar(table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        self.query.trace_add("write", lambda *_: self.refresh())
        self.date_from.trace_add("write", lambda *_: self.refresh())
        self.date_to.trace_add("write", lambda *_: self.refresh())

        self.refresh()

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("refresh",):
                self.refresh()
                return True
            if action in ("focus_search",):
                if self._query_entry is not None:
                    self._query_entry.focus_set()
                    return True
                return False
            if action in ("primary",):
                self.open_selected()
                return True
            if action in ("delete",):
                return False
        except Exception:
            return False
        return False

    def open_folder(self) -> None:
        invoices = Path("invoices").resolve()
        invoices.mkdir(parents=True, exist_ok=True)
        try:
            import os

            os.startfile(invoices)  # Windows
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def refresh(self) -> None:
        q = self.query.get().strip().lower()
        df_raw = self.date_from.get().strip()
        dt_raw = self.date_to.get().strip()

        where = "WHERE invoice_path IS NOT NULL AND invoice_path <> ''"
        params: list[object] = []
        if df_raw:
            where += " AND DATE(sale_date) >= DATE(?)"
            params.append(df_raw)
        if dt_raw:
            where += " AND DATE(sale_date) <= DATE(?)"
            params.append(dt_raw)

        with connect() as conn:
            rows = conn.execute(
                f"""SELECT buyer_name, buyer_mobile, sale_date, total_price, invoice_path
                    FROM sales
                    {where}
                    ORDER BY sale_date DESC
                    LIMIT 500""",
                tuple(params),
            ).fetchall()

        # De-duplicate by invoice_path (one invoice may have multiple sales rows).
        seen: set[str] = set()
        results: list[dict[str, str]] = []
        for r in rows:
            path = str(r["invoice_path"] or "")
            if not path or path in seen:
                continue
            seen.add(path)
            buyer = str(r["buyer_name"] or "")
            mobile = str(r["buyer_mobile"] or "")
            sale_date = str(r["sale_date"] or "")
            total = r["total_price"]
            try:
                total_s = f"{float(total):.2f}" if total is not None else ""
            except Exception:
                total_s = str(total or "")

            hay = f"{buyer} {mobile} {sale_date} {path} {total_s}".lower()
            if q and q not in hay:
                continue
            results.append(
                {
                    "sale_date": sale_date,
                    "buyer": buyer,
                    "mobile": mobile,
                    "total": total_s,
                    "invoice_path": path,
                }
            )

        self.tree.delete(*self.tree.get_children())
        for r in results:
            filename = Path(r["invoice_path"]).name
            self.tree.insert(
                "",
                tk.END,
                values=(r["sale_date"], r["buyer"] or "-", r["mobile"] or "-", r["total"], filename),
                tags=(r["invoice_path"],),
            )

        self.status.set(f"Showing {len(results)} invoice(s). Double-click to open.")

    def _selected_invoice_path(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0]).get("tags") or ()
        if tags:
            return str(tags[0])
        return None

    def open_selected(self) -> None:
        path = self._selected_invoice_path()
        if not path:
            messagebox.showinfo("Invoices", "Select an invoice first.")
            return
        p = Path(path)
        if not p.exists():
            messagebox.showerror("Open", f"File not found:\n{p}")
            return
        try:
            import os

            os.startfile(p)  # Windows
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def open_selected_folder(self) -> None:
        path = self._selected_invoice_path()
        if not path:
            messagebox.showinfo("Invoices", "Select an invoice first.")
            return
        p = Path(path).resolve()
        if not p.exists():
            messagebox.showerror("Open", f"File not found:\n{p}")
            return
        try:
            import os

            os.startfile(str(p.parent))
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def copy_selected_path(self) -> None:
        path = self._selected_invoice_path()
        if not path:
            messagebox.showinfo("Invoices", "Select an invoice first.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(path)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))


class SearchProductPanel(Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.pack(fill=tk.BOTH, expand=True)
        self.query = StringVar(value="")
        self._query_entry: Entry | None = None

        Label(self, text="Search Products", font=("Helvetica", 18, "bold")).pack(pady=(10, 5))

        top = tk.Frame(self)
        top.pack(fill=tk.X, pady=10)

        self._query_entry = Entry(top, textvariable=self.query, width=40)
        self._query_entry.pack(side=tk.LEFT, padx=(0, 8))
        Button(top, text="Search", bootstyle="primary-outline", command=self.refresh).pack(side=tk.LEFT)
        Button(top, text="Clear", bootstyle="secondary-outline", command=self.clear).pack(side=tk.LEFT, padx=8)

        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.tree = Treeview(
            table_frame, columns=("id", "name", "category", "unit", "price", "quantity", "expiry"), show="headings"
        )
        headers = ["ID", "Name", "Category", "Unit", "Price", "Qty", "Expiry"]
        for col, text in zip(self.tree["columns"], headers):
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor="center", width=120)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = Scrollbar(table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        self.query.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("refresh",):
                self.refresh()
                return True
            if action in ("focus_search",):
                if self._query_entry is not None:
                    self._query_entry.focus_set()
                    return True
                return False
            if action in ("primary",):
                self.refresh()
                return True
        except Exception:
            return False
        return False

    def clear(self) -> None:
        self.query.set("")

    def refresh(self) -> None:
        q = self.query.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, name, category, unit, price, quantity, expiry FROM products ORDER BY id DESC"
            ).fetchall()
        for r in rows:
            if not q or q in r["name"].lower() or q in r["category"].lower():
                self.tree.insert(
                    "",
                    tk.END,
                    values=(r["id"], r["name"], r["category"], r["unit"], r["price"], r["quantity"], r["expiry"]),
                )


class MonitorPanel(Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.pack(fill=tk.BOTH, expand=True)
        self.query = StringVar(value="")
        self.type_filter = StringVar(value="All")
        self.auto_refresh = tk.BooleanVar(value=bool(get_setting("monitor_auto_refresh", True)))
        interval_ms = int(get_setting("monitor_refresh_interval_ms", 2000) or 2000)
        self.interval_var = StringVar(value=f"{max(1, int(round(interval_ms / 1000)))}s")
        self._after_id: str | None = None
        self._all_rows_count = 0
        self._query_entry: Entry | None = None

        Label(self, text="Activity Monitor", font=("Helvetica", 18, "bold")).pack(pady=(10, 2))
        Label(self, text="Recent actions in the system (auto-refresh).", bootstyle="secondary").pack(pady=(0, 10))

        controls = tk.LabelFrame(self, text="Filters & Controls", padx=10, pady=8)
        controls.pack(fill=tk.X, padx=5, pady=(0, 10))

        Label(controls, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self._query_entry = Entry(controls, textvariable=self.query, width=40)
        self._query_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=4)

        Label(controls, text="Type:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.type_combo = Combobox(
            controls,
            textvariable=self.type_filter,
            values=["All", "auth", "product", "sale", "export", "settings"],
            state="readonly",
            width=12,
        )
        self.type_combo.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=4)

        Checkbutton(controls, text="Auto-refresh", variable=self.auto_refresh).grid(
            row=0, column=4, sticky="w", padx=(0, 10), pady=4
        )

        Label(controls, text="Every:").grid(row=0, column=5, sticky="w", padx=(0, 6), pady=4)
        interval = Combobox(controls, textvariable=self.interval_var, values=["1s", "2s", "5s", "10s"], width=6)
        interval.configure(state="readonly")
        interval.grid(row=0, column=6, sticky="w", padx=(0, 12), pady=4)

        Button(controls, text="Refresh", bootstyle="primary-outline", command=self.refresh).grid(
            row=0, column=7, sticky="e", padx=(0, 8), pady=4
        )
        Button(controls, text="Copy Selected", bootstyle="secondary-outline", command=self.copy_selected).grid(
            row=0, column=8, sticky="e", padx=(0, 8), pady=4
        )
        Button(controls, text="Export CSV", bootstyle="success-outline", command=self.export_csv).grid(
            row=0, column=9, sticky="e", pady=4
        )

        controls.grid_columnconfigure(1, weight=1)

        self.status = StringVar(value="")
        Label(self, textvariable=self.status, bootstyle="secondary").pack(anchor="w", padx=5, pady=(0, 6))

        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = Treeview(
            table_frame,
            columns=("time", "type", "user", "message"),
            show="headings",
        )
        self.tree.heading("time", text="Time")
        self.tree.heading("type", text="Type")
        self.tree.heading("user", text="User")
        self.tree.heading("message", text="Message")

        self.tree.column("time", anchor="w", width=170, stretch=False)
        self.tree.column("type", anchor="center", width=90, stretch=False)
        self.tree.column("user", anchor="center", width=110, stretch=False)
        self.tree.column("message", anchor="w", width=700)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = Scrollbar(table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        # Subtle row highlighting by type.
        self.tree.tag_configure("auth", background="#e7f1ff")
        self.tree.tag_configure("product", background="#e8f7ee")
        self.tree.tag_configure("sale", background="#fff4e5")
        self.tree.tag_configure("export", background="#f1f1f1")
        self.tree.tag_configure("settings", background="#f3e8ff")

        self.query.trace_add("write", lambda *_: self.refresh())
        self.type_filter.trace_add("write", lambda *_: self.refresh())
        self.auto_refresh.trace_add("write", lambda *_: self.refresh())
        self.interval_var.trace_add("write", lambda *_: self.refresh())
        self.bind("<Destroy>", self._on_destroy, add=True)

        self.refresh()

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("refresh",):
                self.refresh()
                return True
            if action in ("focus_search",):
                if self._query_entry is not None:
                    self._query_entry.focus_set()
                    return True
                return False
            if action in ("primary",):
                self.copy_selected()
                return True
            if action in ("export",):
                self.export_csv()
                return True
        except Exception:
            return False
        return False

    def refresh(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        with connect() as conn:
            rows = conn.execute(
                "SELECT event_type, message, username, created_at FROM activity_log ORDER BY id DESC LIMIT 500"
            ).fetchall()

        self._all_rows_count = len(rows)
        q = self.query.get().strip().lower()
        t = self.type_filter.get().strip().lower()

        self.tree.delete(*self.tree.get_children())
        shown = 0
        for r in rows:
            event_type = str(r["event_type"] or "").lower().strip()
            username = str(r["username"] or "")
            message = str(r["message"] or "")
            created_at = str(r["created_at"] or "")

            if t != "all" and event_type != t:
                continue
            if q:
                hay = f"{event_type} {username} {message} {created_at}".lower()
                if q not in hay:
                    continue

            tag = event_type if event_type in ("auth", "product", "sale", "export", "settings") else ""
            self.tree.insert("", tk.END, values=(created_at, event_type.upper(), username or "-", message), tags=(tag,))
            shown += 1

        self.status.set(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}  |  Showing {shown} of {self._all_rows_count}"
        )

        if bool(self.auto_refresh.get()):
            self._after_id = self.after(self._interval_ms(), self.refresh)

    def _interval_ms(self) -> int:
        raw = str(self.interval_var.get()).strip().lower().replace(" ", "")
        try:
            if raw.endswith("s"):
                ms = max(500, int(float(raw[:-1]) * 1000))
                update_settings({"monitor_refresh_interval_ms": ms, "monitor_auto_refresh": bool(self.auto_refresh.get())})
                return ms
        except Exception:
            pass
        return 2000

    def _selected_row_text(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0]).get("values") or []
        if len(values) < 4:
            return None
        created_at, etype, user, msg = (str(values[0]), str(values[1]), str(values[2]), str(values[3]))
        return f"[{created_at}] {etype} ({user}): {msg}"

    def copy_selected(self) -> None:
        text = self._selected_row_text()
        if not text:
            messagebox.showinfo("Copy", "Select a row first.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))

    def export_csv(self) -> None:
        out = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"Activity_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not out:
            return

        with connect() as conn:
            rows = conn.execute(
                "SELECT event_type, message, username, created_at FROM activity_log ORDER BY id DESC LIMIT 5000"
            ).fetchall()

        try:
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["created_at", "event_type", "username", "message"])
                for r in rows[::-1]:
                    writer.writerow([r["created_at"], r["event_type"], r["username"], r["message"]])
            messagebox.showinfo("Exported", f"Saved: {out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _on_destroy(self, event) -> None:
        if event.widget is self and self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None


class LockSessionPanel(Frame):
    def __init__(self, master, current_user: str, on_unlock):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.on_unlock = on_unlock
        self.password = StringVar(value="")

        self.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(self)
        card.place(relx=0.5, rely=0.42, anchor="center")
        Label(card, text="Session Locked", font=("Helvetica", 20, "bold"), bootstyle="danger").pack(pady=(0, 6))
        Label(
            card,
            text="Enter your password to unlock Grocery Mart.",
            bootstyle="secondary",
        ).pack(pady=(0, 14))

        Label(card, text=f"User: {current_user}", font=("Helvetica", 10, "italic")).pack(pady=(0, 10))
        entry = Entry(card, show="*", textvariable=self.password, width=34)
        entry.pack(pady=(0, 12), ipady=5)
        Button(card, text="Unlock", bootstyle="success", width=18, command=self.unlock_session).pack(pady=(0, 8))
        entry.focus_set()

    def unlock_session(self) -> None:
        if verify_credentials(self.current_user, self.password.get()):
            log_event("auth", "Session unlocked", self.current_user)
            self.on_unlock()
            return
        messagebox.showerror("Error", "Invalid password.")
