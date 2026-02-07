from __future__ import annotations

import tkinter as tk
from datetime import datetime

from ttkbootstrap import Button, Frame, Label

from database import connect
from utils.app_settings import get_setting


DEFAULT_LOW_STOCK_THRESHOLD = 5


class HomePanel(Frame):
    def __init__(self, master, switch_panel_callback=None):
        super().__init__(master, padding=10)
        self.switch_panel_callback = switch_panel_callback
        self.pack(fill=tk.BOTH, expand=True)
        self.stats: dict[str, Label] = {}
        self.create_widgets()
        self.update_time()
        self.refresh_stats()

    def create_widgets(self):
        title_frame = tk.Frame(self)
        title_frame.pack(pady=15)

        Label(title_frame, text="Grocery Inventory Dashboard", font=("Helvetica", 22, "bold")).pack()
        self.time_label = Label(title_frame, text="", font=("Helvetica", 12))
        self.time_label.pack(pady=5)

        stats_wrapper = tk.Frame(self)
        stats_wrapper.pack(pady=25)

        stat_titles = ["Total Products", "Low Stock Items", "Today's Sales (Revenue)"]

        for idx, title in enumerate(stat_titles):
            box = tk.Frame(stats_wrapper, relief=tk.RIDGE, borderwidth=2, padx=20, pady=15)
            box.grid(row=0, column=idx, padx=18)
            Label(box, text=title, font=("Helvetica", 11)).pack()
            stat_label = Label(box, text="0", font=("Helvetica", 20, "bold"))
            stat_label.pack()
            self.stats[title] = stat_label

        nav = tk.Frame(self)
        nav.pack(pady=25)
        Button(
            nav, text="Inventory", bootstyle="info-outline", width=16, command=lambda: self.switch_panel("Inventory")
        ).pack(side=tk.LEFT, padx=10)
        Button(nav, text="Sales", bootstyle="success-outline", width=16, command=lambda: self.switch_panel("Sales")).pack(
            side=tk.LEFT, padx=10
        )
        Button(
            nav, text="Analytics", bootstyle="warning-outline", width=16, command=lambda: self.switch_panel("Analytics")
        ).pack(side=tk.LEFT, padx=10)

    def update_time(self):
        now = datetime.now().strftime("%A, %d %B %Y | %H:%M:%S")
        self.time_label.config(text=now)
        self.after(1000, self.update_time)

    def refresh_stats(self):
        threshold = int(get_setting("inventory_low_stock_threshold", DEFAULT_LOW_STOCK_THRESHOLD) or DEFAULT_LOW_STOCK_THRESHOLD)
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM products")
            total_products = int(cur.fetchone()["c"])

            cur.execute("SELECT COUNT(*) AS c FROM products WHERE quantity <= ?", (threshold,))
            low_stock = int(cur.fetchone()["c"])

            cur.execute(
                """SELECT COALESCE(SUM(COALESCE(total_price, 0)), 0) AS revenue
                   FROM sales
                   WHERE DATE(sale_date) = DATE('now')"""
            )
            revenue = float(cur.fetchone()["revenue"] or 0)

        self.stats["Total Products"].config(text=str(total_products))
        self.stats["Low Stock Items"].config(text=str(low_stock))
        self.stats["Today's Sales (Revenue)"].config(text=f"{revenue:.2f}")

    def switch_panel(self, name):
        if self.switch_panel_callback:
            self.switch_panel_callback(name)
