from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from ttkbootstrap import Button, Entry, Frame, Label, Scrollbar, StringVar, Treeview

from database import connect, log_event


class SupplierManager(Frame):
    def __init__(self, master, *, current_user: str | None = None):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.pack(fill=tk.BOTH, expand=True)

        self.selected_id: int | None = None
        self.name_var = StringVar()
        self.contact_var = StringVar()

        self.create_form()
        self.create_table()
        self.load_suppliers()

    def create_form(self):
        Label(self, text="Supplier Manager", font=("Helvetica", 20, "bold")).pack(pady=(10, 10))

        form = tk.Frame(self)
        form.pack(pady=10, padx=30, fill=tk.X)

        Label(form, text="Supplier Name").grid(row=0, column=0, sticky="w", pady=5)
        Entry(form, textvariable=self.name_var, width=45).grid(row=0, column=1, padx=10, pady=4, sticky="w")

        Label(form, text="Contact Info").grid(row=1, column=0, sticky="w", pady=5)
        Entry(form, textvariable=self.contact_var, width=45).grid(row=1, column=1, padx=10, pady=4, sticky="w")

        btns = tk.Frame(self)
        btns.pack(pady=10)
        Button(btns, text="Add", bootstyle="success", width=12, command=self.add_supplier).pack(side=tk.LEFT, padx=6)
        Button(btns, text="Update", bootstyle="warning", width=12, command=self.update_supplier).pack(
            side=tk.LEFT, padx=6
        )
        Button(btns, text="Delete", bootstyle="danger", width=12, command=self.delete_supplier).pack(side=tk.LEFT, padx=6)
        Button(btns, text="Clear", bootstyle="secondary", width=12, command=self.clear).pack(side=tk.LEFT, padx=6)

    def create_table(self):
        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = Treeview(table_frame, columns=("id", "name", "contact"), show="headings", height=12)
        for col, text, width in [
            ("id", "ID", 80),
            ("name", "Name", 220),
            ("contact", "Contact", 320),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor="center", width=width)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        scroll = Scrollbar(table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

    def load_suppliers(self):
        self.tree.delete(*self.tree.get_children())
        with connect() as conn:
            rows = conn.execute("SELECT id, name, contact FROM suppliers ORDER BY id DESC").fetchall()
        for r in rows:
            self.tree.insert("", tk.END, values=(r["id"], r["name"], r["contact"]))

    def on_select(self, _event=None):
        item = self.tree.selection()
        if not item:
            return
        data = self.tree.item(item[0])["values"]
        self.selected_id = int(data[0])
        self.name_var.set(str(data[1]))
        self.contact_var.set("" if data[2] in (None, "None") else str(data[2]))

    def add_supplier(self):
        name = self.name_var.get().strip()
        contact = self.contact_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Supplier name is required.")
            return
        try:
            with connect() as conn:
                conn.execute("INSERT INTO suppliers (name, contact) VALUES (?, ?)", (name, contact or None))
                conn.commit()
            log_event("supplier", f"Added supplier: {name}", self.current_user)
            self.load_suppliers()
            self.clear()
            messagebox.showinfo("Saved", "Supplier added.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_supplier(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "No supplier selected.")
            return
        name = self.name_var.get().strip()
        contact = self.contact_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Supplier name is required.")
            return
        try:
            with connect() as conn:
                conn.execute(
                    "UPDATE suppliers SET name=?, contact=? WHERE id=?",
                    (name, contact or None, self.selected_id),
                )
                conn.commit()
            log_event("supplier", f"Updated supplier: {name} (ID {self.selected_id})", self.current_user)
            self.load_suppliers()
            self.clear()
            messagebox.showinfo("Updated", "Supplier updated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_supplier(self):
        if not self.selected_id:
            messagebox.showwarning("Select", "No supplier selected.")
            return
        if not messagebox.askyesno("Delete", "Delete selected supplier?"):
            return
        try:
            with connect() as conn:
                row = conn.execute("SELECT name FROM suppliers WHERE id=?", (self.selected_id,)).fetchone()
                conn.execute("DELETE FROM suppliers WHERE id=?", (self.selected_id,))
                conn.commit()
            log_event(
                "supplier",
                f"Deleted supplier: {(row['name'] if row else 'ID')} {self.selected_id}",
                self.current_user,
            )
            self.load_suppliers()
            self.clear()
            messagebox.showinfo("Deleted", "Supplier deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear(self):
        self.selected_id = None
        self.name_var.set("")
        self.contact_var.set("")

