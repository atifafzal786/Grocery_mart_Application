from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox

from ttkbootstrap import Button, Combobox, Entry, Frame, Label, StringVar

from .database import connect
from .utils.app_settings import get_setting

try:
    import matplotlib.pyplot as plt  # type: ignore
    from matplotlib.figure import Figure  # type: ignore
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # type: ignore
except Exception:  # pragma: no cover
    plt = None
    Figure = None  # type: ignore
    FigureCanvasTkAgg = None  # type: ignore

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


class AnalyticsDashboard(Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)
        self.period = StringVar(value="Daily")
        self.range_mode = StringVar(value="Last 30 days")
        self.date_from = StringVar(value="")
        self.date_to = StringVar(value="")
        self.status = StringVar(value="")
        self.canvas = None
        self.fig = None
        self.ax_pie = None
        self.ax_trend = None
        self.ax_top = None
        self._resize_after_id: str | None = None
        self._kpi_labels: dict[str, Label] = {}
        self.build_widgets()

    def build_widgets(self):
        Label(self, text="Analytics", font=("Helvetica", 20, "bold")).pack(pady=(10, 2))
        Label(self, text="Stock insights and sales trends for Grocery Mart.", bootstyle="secondary").pack(
            pady=(0, 10)
        )

        if plt is None or Figure is None or FigureCanvasTkAgg is None:
            Label(
                self,
                text="Analytics requires matplotlib.\nInstall dependencies with: pip install -r requirements.txt",
                justify="center",
            ).pack(pady=30)
            return

        control_frame = tk.LabelFrame(self, text="Controls", padx=10, pady=8)
        control_frame.pack(fill=tk.X, padx=6, pady=(0, 10))
        control_frame.grid_columnconfigure(9, weight=1)

        Label(control_frame, text="Sales period:").grid(row=0, column=0, sticky="w", padx=(2, 6), pady=4)
        combo = Combobox(control_frame, textvariable=self.period, state="readonly", width=10)
        combo["values"] = ["Daily", "Weekly", "Monthly"]
        combo.grid(row=0, column=1, sticky="w", padx=(0, 14), pady=4)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_charts())

        Label(control_frame, text="Range:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        range_combo = Combobox(control_frame, textvariable=self.range_mode, state="readonly", width=14)
        range_combo["values"] = [
            "All time",
            "Today",
            "Last 7 days",
            "Last 30 days",
            "This month",
            "This year",
            "Custom",
        ]
        range_combo.grid(row=0, column=3, sticky="w", padx=(0, 14), pady=4)
        range_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_range_mode())

        Label(control_frame, text="From (YYYY-MM-DD):").grid(row=0, column=4, sticky="w", padx=(0, 6), pady=4)
        self._from_entry = Entry(control_frame, textvariable=self.date_from, width=12)
        self._from_entry.grid(row=0, column=5, sticky="w", padx=(0, 12), pady=4)

        Label(control_frame, text="To:").grid(row=0, column=6, sticky="w", padx=(0, 6), pady=4)
        self._to_entry = Entry(control_frame, textvariable=self.date_to, width=12)
        self._to_entry.grid(row=0, column=7, sticky="w", padx=(0, 14), pady=4)

        Button(control_frame, text="Refresh", bootstyle="secondary-outline", command=self.refresh_charts).grid(
            row=0, column=8, sticky="w", padx=(0, 10), pady=4
        )
        Button(control_frame, text="Export report", bootstyle="success", command=self.export_report).grid(
            row=0, column=9, sticky="w", pady=4
        )

        kpi = tk.LabelFrame(self, text="Key Metrics", padx=10, pady=8)
        kpi.pack(fill=tk.X, padx=6, pady=(0, 10))
        for i in range(6):
            kpi.grid_columnconfigure(i, weight=1)

        self._kpi_labels.clear()
        for col, (label, key) in enumerate(
            [
                ("Revenue", "revenue"),
                ("Sales", "sales"),
                ("Items Sold", "items"),
                ("Avg Sale", "avg_sale"),
                ("Tax Collected", "tax"),
                ("Low Stock", "low_stock"),
            ]
        ):
            cell = Frame(kpi)
            cell.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)
            Label(cell, text=label, bootstyle="secondary").pack()
            val = Label(cell, text="—", font=("Helvetica", 14, "bold"))
            val.pack()
            self._kpi_labels[key] = val

        # Create a self-contained figure (avoid pyplot global state issues).
        self.fig = Figure(figsize=(11, 6), dpi=100)
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1.0, 1.15], width_ratios=[1.0, 1.35], hspace=0.35, wspace=0.25)
        self.ax_pie = self.fig.add_subplot(gs[0, 0])
        self.ax_trend = self.fig.add_subplot(gs[0, 1])
        self.ax_top = self.fig.add_subplot(gs[1, :])
        self.fig.suptitle("Stock and Sales Overview", fontsize=12, fontweight="bold")

        charts = Frame(self)
        charts.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.canvas = FigureCanvasTkAgg(self.fig, master=charts)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.get_tk_widget().bind("<Configure>", self._on_canvas_resize)

        Label(self, textvariable=self.status, bootstyle="secondary").pack(anchor="w", padx=10, pady=(0, 2))

        self._apply_range_mode(initial=True)
        self.refresh_charts()

    def _apply_range_mode(self, initial: bool = False) -> None:
        mode = str(self.range_mode.get() or "").strip()
        today = date.today()

        df: date | None = None
        dt: date | None = None
        if mode == "All time":
            df, dt = None, None
        elif mode == "Today":
            df, dt = today, today
        elif mode == "Last 7 days":
            df, dt = today - timedelta(days=6), today
        elif mode == "Last 30 days":
            df, dt = today - timedelta(days=29), today
        elif mode == "This month":
            df, dt = today.replace(day=1), today
        elif mode == "This year":
            df, dt = today.replace(month=1, day=1), today
        elif mode == "Custom":
            # Leave entries as-is (user provided).
            pass

        if mode != "Custom":
            self.date_from.set(df.isoformat() if df else "")
            self.date_to.set(dt.isoformat() if dt else "")

        # Disable entries unless Custom (keeps UI clean and prevents invalid edits).
        editable = mode == "Custom"
        try:
            self._from_entry.configure(state="normal" if editable else "disabled")
            self._to_entry.configure(state="normal" if editable else "disabled")
        except Exception:
            pass

        if not initial:
            self.refresh_charts()

    def _parse_date(self, raw: str) -> date | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    def _date_filters(self) -> tuple[str, list[object]]:
        df = self._parse_date(self.date_from.get())
        dt = self._parse_date(self.date_to.get())
        if df is None and dt is None:
            return "", []
        if df is None:
            df = dt
        if dt is None:
            dt = df
        if df and dt and dt < df:
            df, dt = dt, df
        return " AND DATE(sale_date) BETWEEN DATE(?) AND DATE(?)", [df.isoformat(), dt.isoformat()]

    def _money(self, value: float) -> str:
        try:
            return f"{value:,.2f}"
        except Exception:
            return str(value)

    def _on_canvas_resize(self, _e=None) -> None:
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
            self._resize_after_id = None
        self._resize_after_id = self.after(140, self._resize_figure_to_widget)

    def _resize_figure_to_widget(self) -> None:
        self._resize_after_id = None
        if self.canvas is None or self.fig is None:
            return
        widget = self.canvas.get_tk_widget()
        w = max(1, int(widget.winfo_width()))
        h = max(1, int(widget.winfo_height()))
        try:
            dpi = float(self.fig.get_dpi() or 100)
            self.fig.set_size_inches(w / dpi, h / dpi, forward=True)
            self.canvas.draw_idle()
        except Exception:
            pass

    def refresh_charts(self):
        if self.ax_pie is None or self.ax_trend is None or self.ax_top is None:
            return

        self.ax_pie.clear()
        self.ax_trend.clear()
        self.ax_top.clear()

        where, params = self._date_filters()

        with connect() as conn:
            stock_data = conn.execute(
                "SELECT category, SUM(quantity) AS qty FROM products GROUP BY category ORDER BY qty DESC"
            ).fetchall()

            kpi_row = conn.execute(
                f"""SELECT
                        COALESCE(SUM(COALESCE(total_price,0)),0) AS revenue,
                        COUNT(*) AS sales,
                        COALESCE(SUM(COALESCE(quantity,0)),0) AS items,
                        COALESCE(SUM(COALESCE(tax_amount,0)),0) AS tax
                    FROM sales
                    WHERE 1=1 {where}""",
                tuple(params),
            ).fetchone()

            threshold = int(get_setting("inventory_low_stock_threshold", 5) or 5)
            low_stock = conn.execute(
                "SELECT COUNT(*) AS c FROM products WHERE COALESCE(quantity,0) <= ?",
                (threshold,),
            ).fetchone()

            if self.period.get() == "Daily":
                sales_data = conn.execute(
                    f"""SELECT DATE(sale_date) AS k, COALESCE(SUM(COALESCE(total_price,0)),0) AS v
                        FROM sales
                        WHERE 1=1 {where}
                        GROUP BY DATE(sale_date)
                        ORDER BY DATE(sale_date)""",
                    tuple(params),
                ).fetchall()
            elif self.period.get() == "Weekly":
                sales_data = conn.execute(
                    f"""SELECT strftime('%Y-W%W', sale_date) AS k, COALESCE(SUM(COALESCE(total_price,0)),0) AS v
                        FROM sales
                        WHERE 1=1 {where}
                        GROUP BY strftime('%Y-W%W', sale_date)
                        ORDER BY strftime('%Y-W%W', sale_date)""",
                    tuple(params),
                ).fetchall()
            else:
                sales_data = conn.execute(
                    f"""SELECT strftime('%Y-%m', sale_date) AS k, COALESCE(SUM(COALESCE(total_price,0)),0) AS v
                        FROM sales
                        WHERE 1=1 {where}
                        GROUP BY strftime('%Y-%m', sale_date)
                        ORDER BY strftime('%Y-%m', sale_date)""",
                    tuple(params),
                ).fetchall()

            top_products = conn.execute(
                f"""SELECT product_name,
                        COALESCE(SUM(COALESCE(quantity,0)),0) AS qty,
                        COALESCE(SUM(COALESCE(total_price,0)),0) AS revenue
                    FROM sales
                    WHERE 1=1 {where}
                    GROUP BY product_name
                    ORDER BY revenue DESC
                    LIMIT 10""",
                tuple(params),
            ).fetchall()

        # KPIs
        try:
            revenue = float(kpi_row["revenue"] or 0) if kpi_row else 0.0
            sales = int(kpi_row["sales"] or 0) if kpi_row else 0
            items = int(kpi_row["items"] or 0) if kpi_row else 0
            tax = float(kpi_row["tax"] or 0) if kpi_row else 0.0
            avg_sale = revenue / sales if sales else 0.0
            low_stock_count = int(low_stock["c"] or 0) if low_stock else 0

            if "revenue" in self._kpi_labels:
                self._kpi_labels["revenue"].configure(text=self._money(revenue))
            if "sales" in self._kpi_labels:
                self._kpi_labels["sales"].configure(text=str(sales))
            if "items" in self._kpi_labels:
                self._kpi_labels["items"].configure(text=str(items))
            if "avg_sale" in self._kpi_labels:
                self._kpi_labels["avg_sale"].configure(text=self._money(avg_sale))
            if "tax" in self._kpi_labels:
                self._kpi_labels["tax"].configure(text=self._money(tax))
            if "low_stock" in self._kpi_labels:
                self._kpi_labels["low_stock"].configure(text=str(low_stock_count))
        except Exception:
            pass

        # Stock breakdown (donut)
        if stock_data:
            categories = [str(row["category"]) for row in stock_data]
            quantities = [float(row["qty"] or 0) for row in stock_data]

            # Keep the pie readable: show top 6, group the rest.
            pairs = sorted(zip(categories, quantities), key=lambda x: x[1], reverse=True)
            top = pairs[:6]
            rest_sum = sum(q for _c, q in pairs[6:])
            if rest_sum > 0:
                top.append(("Other", rest_sum))

            cats = [c for c, _q in top]
            qtys = [q for _c, q in top]
            self.ax_pie.pie(
                qtys,
                labels=cats,
                autopct="%1.1f%%",
                startangle=90,
                pctdistance=0.75,
                wedgeprops={"width": 0.42, "edgecolor": "white"},
            )
            self.ax_pie.set_title("Stock by Category", fontsize=11)
        else:
            self.ax_pie.text(0.5, 0.5, "No Stock Data", ha="center", va="center")
            self.ax_pie.set_title("Stock by Category", fontsize=11)

        # Sales trend
        if sales_data:
            labels = [str(row["k"]) for row in sales_data]
            values = [float(row["v"] or 0) for row in sales_data]

            max_points = 40
            if len(labels) > max_points:
                labels = labels[-max_points:]
                values = values[-max_points:]

            x = list(range(len(labels)))
            self.ax_trend.plot(x, values, color="#2b7cff", linewidth=2.0, marker="o", markersize=3.5)
            self.ax_trend.fill_between(x, values, color="#2b7cff", alpha=0.12)
            self.ax_trend.set_title(f"{self.period.get()} Sales (Revenue)", fontsize=11)

            if len(labels) > 10:
                step = max(1, len(labels) // 10)
                ticks = list(range(0, len(labels), step))
                self.ax_trend.set_xticks(ticks)
                self.ax_trend.set_xticklabels([labels[i] for i in ticks], rotation=0, ha="center", fontsize=8)
            else:
                self.ax_trend.set_xticks(x)
                self.ax_trend.set_xticklabels(labels, rotation=0, ha="center", fontsize=8)

            self.ax_trend.grid(axis="y", linestyle="--", alpha=0.35)
            self.ax_trend.margins(x=0.02)
        else:
            self.ax_trend.text(0.5, 0.5, "No Sales Data", ha="center", va="center")
            self.ax_trend.set_title(f"{self.period.get()} Sales (Revenue)", fontsize=11)

        # Top products
        if top_products:
            names = [str(r["product_name"] or "") for r in top_products][::-1]
            revs = [float(r["revenue"] or 0) for r in top_products][::-1]
            qtys = [int(r["qty"] or 0) for r in top_products][::-1]

            y = list(range(len(names)))
            self.ax_top.barh(y, revs, color="#7ec8e3", edgecolor="#5aa8c6", linewidth=0.8)
            self.ax_top.set_yticks(y)
            self.ax_top.set_yticklabels(names, fontsize=9)
            self.ax_top.set_title("Top Products (Revenue)", fontsize=11)
            self.ax_top.grid(axis="x", linestyle="--", alpha=0.25)
            for i, (rv, q) in enumerate(zip(revs, qtys)):
                self.ax_top.text(rv, i, f"  {q} pcs", va="center", fontsize=8, color="#2a4256")
        else:
            self.ax_top.text(0.5, 0.5, "No Sales Data for Top Products", ha="center", va="center")
            self.ax_top.set_title("Top Products (Revenue)", fontsize=11)

        # Status line
        try:
            mode = str(self.range_mode.get() or "").strip()
            self.status.set(f"View: {mode}  |  Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            pass

        if self.canvas:
            self.canvas.draw_idle()

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("refresh", "primary"):
                self.refresh_charts()
                return True
            if action in ("export",):
                self.export_report()
                return True
            return False
        except Exception:
            return False

    def export_report(self):
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return

        where, params = self._date_filters()
        with connect() as conn:
            rows = conn.execute(
                f"""SELECT id, product_name, quantity, unit_price, subtotal, gst_percent, tax_percent, tax_amount, total_price,
                          buyer_name, buyer_mobile, sale_date, invoice_path
                   FROM sales
                   WHERE 1=1 {where}
                   ORDER BY sale_date DESC""",
                tuple(params),
            ).fetchall()

        if not rows:
            messagebox.showwarning("No data", "No sales data found to export.")
            return

        df = pd.DataFrame([dict(r) for r in rows])
        out = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Sales_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            filetypes=[("Excel Workbook", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not out:
            return
        try:
            if out.lower().endswith(".csv"):
                df.to_csv(out, index=False)
            else:
                df.to_excel(out, index=False)
            messagebox.showinfo("Exported", f"Saved: {out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
