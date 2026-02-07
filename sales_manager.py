from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from ttkbootstrap import Button, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview

from database import connect, log_event
from invoice_generator import InvoiceGenerator


class SalesManager(Frame):
    def __init__(self, master, *, current_user: str | None = None):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.pack(fill=tk.BOTH, expand=True)

        self.product_var = StringVar()
        self.qty_var = StringVar()
        self.available_var = StringVar()
        self.unit_price_var = StringVar()
        self.gst_percent_var = StringVar()
        self.tax_percent_var = StringVar()
        self.buyer_name_var = StringVar()
        self.buyer_mobile_var = StringVar()
        self.last_invoice_path = ""
        self.cart: dict[str, dict[str, object]] = {}
        self._preview_after_id: str | None = None
        self._preview_text: tk.Text | None = None
        self._print_btn: Button | None = None
        self._cart_tree: Treeview | None = None
        self._entries: dict[str, Entry] = {}

        self.invoice_maker = InvoiceGenerator("Grocery Mart")
        self.create_form()
        self.load_products()
        self._setup_live_preview()
        self._update_preview()

    def create_form(self):
        Label(self, text="Sales", font=("Helvetica", 20, "bold")).pack(pady=(10, 12))

        shell = tk.Frame(self)
        shell.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 8))
        shell.grid_columnconfigure(0, weight=1)

        form = tk.LabelFrame(shell, text="Sale Entry", padx=14, pady=12)
        form.grid(row=0, column=0, sticky="ew")
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        field_pad = {"padx": 10, "pady": 8}

        def add_field(row: int, col: int, label_text: str, var: StringVar, *, readonly: bool = False) -> Entry:
            Label(form, text=label_text).grid(row=row, column=col, sticky="e", **field_pad)
            state = "readonly" if readonly else "normal"
            entry = Entry(form, textvariable=var, state=state)
            entry.grid(row=row, column=col + 1, sticky="ew", **field_pad)
            self._entries[label_text] = entry
            return entry

        add_field(0, 0, "Buyer Name", self.buyer_name_var)
        add_field(1, 0, "Mobile Number", self.buyer_mobile_var)

        Label(form, text="Select Product").grid(row=0, column=2, sticky="e", **field_pad)
        self.product_menu = Combobox(form, textvariable=self.product_var, state="readonly")
        self.product_menu.grid(row=0, column=3, sticky="ew", **field_pad)
        self.product_menu.bind("<<ComboboxSelected>>", self.display_available_stock)

        add_field(1, 2, "Available Stock", self.available_var, readonly=True)
        add_field(2, 2, "Unit Price", self.unit_price_var, readonly=True)
        add_field(2, 0, "Quantity Sold", self.qty_var)
        add_field(3, 2, "GST %", self.gst_percent_var, readonly=True)
        add_field(3, 0, "Tax %", self.tax_percent_var, readonly=True)

        btn_frame = tk.Frame(shell)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(14, 10))

        item_actions = tk.Frame(btn_frame)
        item_actions.pack(side=tk.LEFT)
        Button(item_actions, text="Add Item", bootstyle="primary", width=14, command=self.add_item).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        Button(item_actions, text="Update Qty", bootstyle="warning", width=14, command=self.update_item_qty).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        Button(item_actions, text="Delete Item", bootstyle="danger", width=14, command=self.delete_item).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        Button(item_actions, text="Clear Items", bootstyle="secondary", width=14, command=self.clear_items).pack(
            side=tk.LEFT
        )

        invoice_actions = tk.Frame(btn_frame)
        invoice_actions.pack(side=tk.RIGHT)
        Button(invoice_actions, text="Record Sale", bootstyle="success", width=18, command=self.record_sale).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        Button(invoice_actions, text="View Invoices", bootstyle="info", width=18, command=self.view_invoices).pack(
            side=tk.LEFT, padx=10
        )
        self._print_btn = Button(
            invoice_actions,
            text="Print Last Invoice",
            bootstyle="secondary",
            width=18,
            command=self.print_last_invoice,
            state="disabled",
        )
        self._print_btn.pack(side=tk.LEFT, padx=10)

        items_frame = tk.LabelFrame(shell, text="Invoice Items", padx=14, pady=12)
        items_frame.grid(row=2, column=0, sticky="ew")
        items_frame.grid_columnconfigure(0, weight=1)

        self._cart_tree = Treeview(
            items_frame,
            columns=("product", "qty", "unit_price", "gst", "tax", "total"),
            show="headings",
            height=6,
        )
        self._cart_tree.heading("product", text="Product")
        self._cart_tree.heading("qty", text="Qty")
        self._cart_tree.heading("unit_price", text="Unit Price")
        self._cart_tree.heading("gst", text="GST%")
        self._cart_tree.heading("tax", text="Tax%")
        self._cart_tree.heading("total", text="Total")
        self._cart_tree.column("product", anchor="w", width=380)
        self._cart_tree.column("qty", anchor="center", width=80)
        self._cart_tree.column("unit_price", anchor="e", width=120)
        self._cart_tree.column("gst", anchor="center", width=70)
        self._cart_tree.column("tax", anchor="center", width=70)
        self._cart_tree.column("total", anchor="e", width=140)
        self._cart_tree.grid(row=0, column=0, sticky="ew")
        self._cart_tree.bind("<<TreeviewSelect>>", self._on_cart_select)

        item_scroll = Scrollbar(items_frame, command=self._cart_tree.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self._cart_tree.configure(yscrollcommand=item_scroll.set)

        preview = tk.LabelFrame(shell, text="Live Invoice Preview", padx=14, pady=12)
        preview.grid(row=3, column=0, sticky="nsew")
        shell.grid_rowconfigure(3, weight=1)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(0, weight=1)

        self._preview_text = tk.Text(preview, height=12, wrap="word", font=("Consolas", 10))
        self._preview_text.grid(row=0, column=0, sticky="nsew")
        scroll = tk.Scrollbar(preview, command=self._preview_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._preview_text.configure(yscrollcommand=scroll.set)
        self._preview_text.configure(state="disabled")

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("refresh",):
                self.load_products()
                self.display_available_stock()
                self._update_preview()
                return True

            if action in ("primary",):
                # Ctrl+Enter -> Add item (most common action)
                self.add_item()
                return True

            if action in ("delete",):
                self.delete_item()
                return True

            if action in ("record",):
                self.record_sale()
                return True

            if action in ("print",):
                self.print_last_invoice()
                return True

            if action in ("focus_search",):
                # Best-effort: focus Quantity Sold (fast data entry)
                entry = self._entries.get("Quantity Sold") or self._entries.get("Buyer Name")
                if entry is not None:
                    entry.focus_set()
                    return True
                return False
        except Exception:
            return False
        return False

    def load_products(self):
        with connect() as conn:
            rows = conn.execute("SELECT name FROM products ORDER BY name ASC").fetchall()
        self.product_menu["values"] = [r["name"] for r in rows]

    def _get_product_info(self, name: str) -> tuple[int, int, float, float, float] | None:
        with connect() as conn:
            row = conn.execute(
                "SELECT id, quantity, price, gst_percent, tax_percent FROM products WHERE name = ?",
                (name,),
            ).fetchone()
        if not row:
            return None
        gst = float(row["gst_percent"] or 0)
        tax = float(row["tax_percent"] or 0)
        return int(row["id"]), int(row["quantity"]), float(row["price"]), gst, tax

    def display_available_stock(self, _event=None):
        name = self.product_var.get()
        info = self._get_product_info(name) if name else None
        if not info:
            self.available_var.set("N/A")
            self.unit_price_var.set("")
            self.gst_percent_var.set("")
            self.tax_percent_var.set("")
        else:
            _pid, stock, price, gst, tax = info
            reserved = int(self.cart.get(name, {}).get("qty", 0) or 0)
            remaining = max(0, stock - reserved)
            self.available_var.set(str(remaining))
            self.unit_price_var.set(f"{price:.2f}")
            self.gst_percent_var.set(f"{gst:g}")
            self.tax_percent_var.set(f"{tax:g}")
        self._update_preview()

    def _setup_live_preview(self) -> None:
        def on_change(_a=None, _b=None, _c=None) -> None:
            self._update_preview()

        for var in (
            self.product_var,
            self.qty_var,
            self.available_var,
            self.unit_price_var,
            self.gst_percent_var,
            self.tax_percent_var,
            self.buyer_name_var,
            self.buyer_mobile_var,
        ):
            try:
                var.trace_add("write", on_change)
            except Exception:
                pass

    def _format_money(self, value: float | None) -> str:
        if value is None:
            return "—"
        return f"{value:,.2f}"

    def _render_preview_text(self) -> str:
        if not self.cart:
            return self._render_preview_text_single()

        now = datetime.now()
        buyer = self.buyer_name_var.get().strip() or "-"
        mobile = self.buyer_mobile_var.get().strip() or "-"

        lines = [
            "Grocery Mart",
            "Invoice Receipt (Preview)",
            now.strftime("%A, %d %B %Y | %H:%M:%S"),
            "",
            "Customer Details",
            f"  Name  : {buyer}",
            f"  Mobile: {mobile}",
            "",
            "Sale Details",
            "  Items:",
        ]

        grand_total = 0.0
        grand_subtotal = 0.0
        grand_tax = 0.0
        for name, item in self.cart.items():
            qty = int(item.get("qty", 0) or 0)
            unit_price = float(item.get("unit_price", 0.0) or 0.0)
            gst = float(item.get("gst_percent", 0.0) or 0.0)
            tax = float(item.get("tax_percent", 0.0) or 0.0)
            subtotal = qty * unit_price
            tax_amount = subtotal * (gst + tax) / 100.0
            line_total = subtotal + tax_amount
            grand_subtotal += subtotal
            grand_tax += tax_amount
            grand_total += line_total
            lines.append(
                f"    - {name}  x{qty}  @ {self._format_money(unit_price)}"
                f"  (GST {gst:g}%, Tax {tax:g}%)  = {self._format_money(line_total)}"
            )

        lines.extend(
            [
                "",
                f"  Subtotal       : {self._format_money(grand_subtotal)}",
                f"  Tax Amount     : {self._format_money(grand_tax)}",
                f"  Total Amount   : {self._format_money(grand_total)}",
                "",
                "Tip: Use 'Add Item' to build an invoice, then 'Record Sale' to generate a PDF.",
            ]
        )
        return "\n".join(lines)

    def _render_preview_text_single(self) -> str:
        now = datetime.now()
        product = self.product_var.get().strip() or "—"
        buyer = self.buyer_name_var.get().strip() or "—"
        mobile = self.buyer_mobile_var.get().strip() or "—"

        try:
            qty = int(self.qty_var.get().strip())
        except Exception:
            qty = 0

        try:
            unit_price = float(self.unit_price_var.get().strip())
        except Exception:
            unit_price = None

        try:
            gst = float(self.gst_percent_var.get().strip() or 0)
        except Exception:
            gst = 0.0
        try:
            tax = float(self.tax_percent_var.get().strip() or 0)
        except Exception:
            tax = 0.0

        subtotal = (qty * unit_price) if (qty > 0 and unit_price is not None) else None
        tax_amount = (subtotal * (gst + tax) / 100.0) if subtotal is not None else None
        total = (subtotal + tax_amount) if (subtotal is not None and tax_amount is not None) else None

        available = self.available_var.get().strip() or "—"
        if available != "—" and available != "N/A":
            try:
                available_int = int(float(available))
                if qty > 0:
                    if qty > available_int:
                        available = f"{available}  (insufficient)"
                    else:
                        available = f"{available}  (after sale: {available_int - qty})"
            except Exception:
                pass

        lines = [
            "Grocery Mart",
            "Invoice Receipt (Preview)",
            now.strftime("%A, %d %B %Y | %H:%M:%S"),
            "",
            "Customer Details",
            f"  Name  : {buyer}",
            f"  Mobile: {mobile}",
            "",
            "Sale Details",
            f"  Product        : {product}",
            f"  Available Stock: {available}",
            f"  Quantity       : {qty if qty > 0 else '—'}",
            f"  Unit Price     : {self._format_money(unit_price)}",
            f"  GST% / Tax%    : {gst:g}% / {tax:g}%",
            f"  Subtotal       : {self._format_money(subtotal)}",
            f"  Tax Amount     : {self._format_money(tax_amount)}",
            f"  Total Amount   : {self._format_money(total)}",
            "",
            "Tip: Click 'Record Sale' to generate a PDF invoice.",
        ]
        return "\n".join(lines)

    def _update_preview(self) -> None:
        if self._preview_after_id is not None:
            try:
                self.after_cancel(self._preview_after_id)
            except Exception:
                pass
            self._preview_after_id = None

        def run() -> None:
            self._preview_after_id = None
            if self._preview_text is None:
                return
            text = self._render_preview_text()
            try:
                self._preview_text.configure(state="normal")
                self._preview_text.delete("1.0", tk.END)
                self._preview_text.insert("1.0", text)
                self._preview_text.configure(state="disabled")
            except Exception:
                pass

        self._preview_after_id = self.after(80, run)

    def _valid_mobile(self, mobile: str) -> bool:
        digits = "".join(ch for ch in mobile if ch.isdigit())
        return len(digits) >= 8

    def _refresh_cart(self) -> None:
        if self._cart_tree is None:
            return
        self._cart_tree.delete(*self._cart_tree.get_children())
        for name, item in self.cart.items():
            qty = int(item.get("qty", 0) or 0)
            unit_price = float(item.get("unit_price", 0.0) or 0.0)
            gst = float(item.get("gst_percent", 0.0) or 0.0)
            tax = float(item.get("tax_percent", 0.0) or 0.0)
            subtotal = qty * unit_price
            tax_amount = subtotal * (gst + tax) / 100.0
            total = subtotal + tax_amount
            self._cart_tree.insert(
                "",
                tk.END,
                values=(name, qty, f"{unit_price:.2f}", f"{gst:g}", f"{tax:g}", f"{total:.2f}"),
            )

    def _on_cart_select(self, _event=None) -> None:
        if self._cart_tree is None:
            return
        sel = self._cart_tree.selection()
        if not sel:
            return
        values = self._cart_tree.item(sel[0]).get("values", [])
        if not values:
            return
        name = str(values[0])
        qty = str(values[1]) if len(values) > 1 else ""
        self.product_var.set(name)
        self.qty_var.set(qty)
        self.display_available_stock()

    def add_item(self) -> None:
        name = self.product_var.get().strip()
        if not name:
            messagebox.showwarning("Select product", "Select a product first.")
            return
        try:
            qty = int(self.qty_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Quantity must be an integer.")
            return
        if qty <= 0:
            messagebox.showwarning("Quantity", "Quantity must be greater than 0.")
            return

        info = self._get_product_info(name)
        if not info:
            messagebox.showerror("Product not found", "This product does not exist.")
            return
        _pid, stock, price, gst, tax = info
        existing = int(self.cart.get(name, {}).get("qty", 0) or 0)
        if existing + qty > stock:
            messagebox.showerror("Insufficient stock", f"Only {stock} units available (already in invoice: {existing}).")
            return

        self.cart[name] = {
            "qty": existing + qty,
            "unit_price": price,
            "gst_percent": gst,
            "tax_percent": tax,
        }
        self._refresh_cart()
        self.display_available_stock()
        self._update_preview()

    def update_item_qty(self) -> None:
        if self._cart_tree is None:
            return
        sel = self._cart_tree.selection()
        if not sel:
            messagebox.showwarning("Select item", "Select an item from the list first.")
            return
        values = self._cart_tree.item(sel[0]).get("values", [])
        if not values:
            return
        name = str(values[0])

        try:
            qty = int(self.qty_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Quantity must be an integer.")
            return

        if qty <= 0:
            self.cart.pop(name, None)
            self._refresh_cart()
            self.display_available_stock()
            self._update_preview()
            return

        info = self._get_product_info(name)
        if not info:
            messagebox.showerror("Product not found", "This product does not exist.")
            return
        _pid, stock, price, gst, tax = info
        if qty > stock:
            messagebox.showerror("Insufficient stock", f"Only {stock} units available.")
            return

        self.cart[name] = {"qty": qty, "unit_price": price, "gst_percent": gst, "tax_percent": tax}
        self._refresh_cart()
        self.display_available_stock()
        self._update_preview()

    def delete_item(self) -> None:
        if self._cart_tree is None:
            return
        sel = self._cart_tree.selection()
        if not sel:
            messagebox.showwarning("Select item", "Select an item from the list first.")
            return
        values = self._cart_tree.item(sel[0]).get("values", [])
        if not values:
            return
        name = str(values[0])
        self.cart.pop(name, None)
        self._refresh_cart()
        self.display_available_stock()
        self._update_preview()

    def clear_items(self) -> None:
        self.cart.clear()
        self._refresh_cart()
        self.display_available_stock()
        self._update_preview()

    def record_sale(self):
        buyer_name = self.buyer_name_var.get().strip()
        buyer_mobile = self.buyer_mobile_var.get().strip()
        if not buyer_name or not buyer_mobile:
            messagebox.showerror("Missing info", "Please enter buyer name and mobile number.")
            return

        if not self._valid_mobile(buyer_mobile):
            messagebox.showwarning("Mobile number", "Mobile number looks invalid.")

        if not self.cart:
            name = self.product_var.get().strip()
            qty_raw = self.qty_var.get().strip()
            if name and qty_raw:
                self.add_item()
            if not self.cart:
                messagebox.showerror("No items", "Add at least one item to the invoice first.")
                return

        sale_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sale_ids: list[int] = []
        invoice_items: list[dict[str, object]] = []
        grand_total = 0.0

        try:
            with connect() as conn:
                cur = conn.cursor()
                for name, item in self.cart.items():
                    qty = int(item.get("qty", 0) or 0)
                    if qty <= 0:
                        continue

                    cur.execute(
                        "SELECT id, quantity, price, gst_percent, tax_percent FROM products WHERE name = ?",
                        (name,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise RuntimeError(f"Product not found: {name}")

                    product_id = int(row["id"])
                    current_qty = int(row["quantity"])
                    unit_price = float(row["price"])
                    gst_percent = float(row["gst_percent"] or 0)
                    tax_percent = float(row["tax_percent"] or 0)
                    if qty > current_qty:
                        raise RuntimeError(f"Insufficient stock for {name}. Only {current_qty} units available.")

                    subtotal = qty * unit_price
                    tax_amount = subtotal * (gst_percent + tax_percent) / 100.0
                    total_price = subtotal + tax_amount
                    new_qty = current_qty - qty
                    grand_total += total_price

                    cur.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, product_id))
                    cur.execute(
                        """INSERT INTO sales
                           (product_name, quantity, sale_date, buyer_name, buyer_mobile,
                            unit_price, subtotal, gst_percent, tax_percent, tax_amount, total_price, invoice_path)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            name,
                            qty,
                            sale_dt,
                            buyer_name,
                            buyer_mobile,
                            unit_price,
                            subtotal,
                            gst_percent,
                            tax_percent,
                            tax_amount,
                            total_price,
                            None,
                        ),
                    )
                    sale_ids.append(int(cur.lastrowid))
                    invoice_items.append(
                        {
                            "product": name,
                            "qty": qty,
                            "unit_price": unit_price,
                            "gst_percent": gst_percent,
                            "tax_percent": tax_percent,
                            "subtotal": subtotal,
                            "tax_amount": tax_amount,
                            "total": total_price,
                        }
                    )

                conn.commit()
        except Exception as e:
            messagebox.showerror("Sale failed", str(e))
            return

        if not sale_ids:
            messagebox.showerror("No items", "Nothing to record.")
            return

        invoice_folder = "invoices"
        os.makedirs(invoice_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        invoice_path = os.path.join(invoice_folder, f"Invoice_{sale_ids[0]}_{timestamp}.pdf")
        try:
            self.invoice_maker.generate_invoice(
                filepath=invoice_path,
                invoice_no=str(sale_ids[0]),
                items=invoice_items,
                total=grand_total,
                buyer_name=buyer_name,
                buyer_mobile=buyer_mobile,
            )
        except Exception as e:
            messagebox.showerror("Invoice failed", str(e))
            invoice_path = ""

        if invoice_path:
            with connect() as conn:
                conn.executemany(
                    "UPDATE sales SET invoice_path = ? WHERE id = ?",
                    [(invoice_path, sale_id) for sale_id in sale_ids],
                )
                conn.commit()
            self.last_invoice_path = invoice_path
            if self._print_btn is not None:
                try:
                    self._print_btn.configure(state="normal")
                except Exception:
                    pass

        log_event(
            "sale",
            f"Recorded invoice: {len(invoice_items)} item(s) (total {grand_total:.2f})",
            self.current_user,
        )
        self.clear_form()
        self.load_products()
        self._refresh_cart()
        self._update_preview()
        messagebox.showinfo("Sale recorded", "Sale recorded successfully.")

    def clear_form(self):
        self.product_var.set("")
        self.qty_var.set("")
        self.available_var.set("")
        self.unit_price_var.set("")
        self.gst_percent_var.set("")
        self.tax_percent_var.set("")
        self.buyer_name_var.set("")
        self.buyer_mobile_var.set("")
        self.cart.clear()
        self._update_preview()

    def view_invoices(self):
        os.makedirs("invoices", exist_ok=True)
        os.startfile(os.path.abspath("invoices"))

    def print_last_invoice(self):
        if not self.last_invoice_path or not os.path.exists(self.last_invoice_path):
            messagebox.showwarning("No invoice", "No invoice found to print.")
            return
        os.startfile(self.last_invoice_path, "print")
