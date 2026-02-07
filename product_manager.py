from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from ttkbootstrap import Button, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview

from database import connect, log_event
from utils.helpers import validate_product_data


class ProductManager(Frame):
    def __init__(self, master, *, current_user: str | None = None):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.pack(fill=tk.BOTH, expand=True)
        self.fields: dict[str, StringVar] = {}
        self.selected_id: int | None = None
        self._supplier_name_to_id: dict[str, int] = {}

        self.create_form()
        self.create_table()
        self.refresh_suppliers()
        self.load_products()

    def create_form(self):
        Label(self, text="Product Manager", font=("Helvetica", 20, "bold")).pack(pady=(10, 10))

        form_frame = tk.Frame(self)
        form_frame.pack(pady=10, padx=30, fill=tk.X)

        labels = ["Product Name", "Category", "Supplier", "Unit", "Price", "Quantity", "Expiry Date (YYYY-MM-DD)"]
        keys = ["name", "category", "supplier", "unit", "price", "quantity", "expiry"]

        categories = ["Pulses", "Grains", "Snacks", "Drinks", "Toiletries", "Stationery", "Other"]

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            lbl = Label(form_frame, text=label_text, font=("Helvetica", 11))
            lbl.grid(row=i, column=0, sticky="w", pady=5)

            var = StringVar()
            if key == "category":
                entry = Combobox(form_frame, textvariable=var, values=categories, state="readonly", width=40)
            elif key == "supplier":
                entry = Combobox(form_frame, textvariable=var, values=[], state="readonly", width=40)
                self.supplier_combo = entry
            else:
                entry = Entry(form_frame, textvariable=var, width=43)

            entry.grid(row=i, column=1, padx=10, pady=4, sticky="w")
            self.fields[key] = var

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=12)

        Button(btn_frame, text="Add Product", bootstyle="success", width=14, command=self.add_product).pack(
            side=tk.LEFT, padx=6
        )
        Button(btn_frame, text="Update", bootstyle="warning", width=10, command=self.update_product).pack(
            side=tk.LEFT, padx=6
        )
        Button(btn_frame, text="Delete", bootstyle="danger", width=10, command=self.delete_product).pack(
            side=tk.LEFT, padx=6
        )
        Button(btn_frame, text="Clear", bootstyle="secondary", width=10, command=self.clear_form).pack(
            side=tk.LEFT, padx=6
        )
        Button(btn_frame, text="Refresh Suppliers", bootstyle="info-outline", width=16, command=self.refresh_suppliers).pack(
            side=tk.LEFT, padx=10
        )

    def create_table(self):
        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = Treeview(
            table_frame,
            columns=("id", "name", "category", "supplier", "unit", "price", "quantity", "expiry"),
            show="headings",
            height=12,
        )

        headers = ["ID", "Name", "Category", "Supplier", "Unit", "Price", "Quantity", "Expiry Date"]
        for col, name in zip(self.tree["columns"], headers):
            self.tree.heading(col, text=name)
            self.tree.column(col, anchor="center", width=120)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        scroll = Scrollbar(table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

    def refresh_suppliers(self) -> None:
        with connect() as conn:
            rows = conn.execute("SELECT id, name FROM suppliers ORDER BY name ASC").fetchall()
        self._supplier_name_to_id = {r["name"]: int(r["id"]) for r in rows}
        supplier_names = [""] + list(self._supplier_name_to_id.keys())
        self.supplier_combo["values"] = supplier_names
        if self.fields["supplier"].get() not in self._supplier_name_to_id and self.fields["supplier"].get() != "":
            self.fields["supplier"].set("")

    def _read_form(self) -> dict[str, str]:
        return {key: var.get().strip() for key, var in self.fields.items()}

    def add_product(self):
        data = self._read_form()
        if not validate_product_data(data):
            messagebox.showwarning("Incomplete", "Please fill required fields: name, category, unit, price, quantity.")
            return

        supplier_id = self._supplier_name_to_id.get(data.get("supplier") or "", None)
        try:
            price = float(data["price"])
            qty = int(data["quantity"])
        except ValueError:
            messagebox.showerror("Invalid input", "Price must be a number and Quantity must be an integer.")
            return

        try:
            with connect() as conn:
                conn.execute(
                    """INSERT INTO products (name, category, unit, price, quantity, expiry, supplier_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (data["name"], data["category"], data["unit"], price, qty, data.get("expiry") or None, supplier_id),
                )
                conn.commit()
            log_event("product", f"Added product: {data['name']}", self.current_user)
            self.load_products()
            self.clear_form()
            messagebox.showinfo("Success", "Product added successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_products(self):
        self.tree.delete(*self.tree.get_children())
        with connect() as conn:
            rows = conn.execute(
                """SELECT p.id, p.name, p.category, COALESCE(s.name, '') AS supplier,
                          p.unit, p.price, p.quantity, p.expiry
                   FROM products p
                   LEFT JOIN suppliers s ON s.id = p.supplier_id
                   ORDER BY p.id DESC"""
            ).fetchall()
        for row in rows:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    row["id"],
                    row["name"],
                    row["category"],
                    row["supplier"],
                    row["unit"],
                    row["price"],
                    row["quantity"],
                    row["expiry"],
                ),
            )

    def load_selected(self, _event=None):
        item = self.tree.selection()
        if not item:
            return
        data = self.tree.item(item[0])["values"]
        self.selected_id = int(data[0])
        self.fields["name"].set(str(data[1]))
        self.fields["category"].set(str(data[2]))
        self.fields["supplier"].set(str(data[3]))
        self.fields["unit"].set(str(data[4]))
        self.fields["price"].set(str(data[5]))
        self.fields["quantity"].set(str(data[6]))
        self.fields["expiry"].set("" if data[7] in (None, "None") else str(data[7]))

    def update_product(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "No product selected.")
            return

        data = self._read_form()
        if not validate_product_data(data):
            messagebox.showwarning("Incomplete", "Please fill required fields: name, category, unit, price, quantity.")
            return

        supplier_id = self._supplier_name_to_id.get(data.get("supplier") or "", None)
        try:
            price = float(data["price"])
            qty = int(data["quantity"])
        except ValueError:
            messagebox.showerror("Invalid input", "Price must be a number and Quantity must be an integer.")
            return

        try:
            with connect() as conn:
                conn.execute(
                    """UPDATE products
                       SET name=?, category=?, unit=?, price=?, quantity=?, expiry=?, supplier_id=?
                       WHERE id=?""",
                    (
                        data["name"],
                        data["category"],
                        data["unit"],
                        price,
                        qty,
                        data.get("expiry") or None,
                        supplier_id,
                        self.selected_id,
                    ),
                )
                conn.commit()
            log_event("product", f"Updated product: {data['name']} (ID {self.selected_id})", self.current_user)
            self.load_products()
            self.clear_form()
            messagebox.showinfo("Updated", "Product updated successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_product(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "No product selected.")
            return
        if not messagebox.askyesno("Delete", "Delete selected product?"):
            return
        try:
            with connect() as conn:
                row = conn.execute("SELECT name FROM products WHERE id=?", (self.selected_id,)).fetchone()
                conn.execute("DELETE FROM products WHERE id=?", (self.selected_id,))
                conn.commit()
            log_event("product", f"Deleted product: {(row['name'] if row else 'ID')} {self.selected_id}", self.current_user)
            self.load_products()
            self.clear_form()
            messagebox.showinfo("Deleted", "Product deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_form(self):
        for var in self.fields.values():
            var.set("")
        self.selected_id = None

