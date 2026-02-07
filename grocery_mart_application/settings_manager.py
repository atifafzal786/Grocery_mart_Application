from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import tkinter as tk
from ttkbootstrap import Button, Checkbutton, Combobox, Entry, Frame, Label, StringVar

from .database import DB_PATH, log_event
from .auth_service import change_password
from .utils.app_settings import get_settings, update_settings


DEFAULT_THEME_PATH = Path(__file__).resolve().parent / "styles" / "theme.json"
THEME_PATH = Path.cwd() / "styles" / "theme.json"


class SettingsManager(Frame):
    def __init__(self, master, *, style, current_user: str | None = None, on_logout=None):
        super().__init__(master, padding=10)
        self.style = style
        self.current_user = current_user
        self.on_logout = on_logout

        self._settings = get_settings()

        self.theme_var = StringVar(value=self._current_theme())
        self.accent_var = StringVar(value=str(self._settings.get("accent", "primary")))
        self.scaling_var = StringVar(value=self._scaling_label(float(self._settings.get("ui_scaling", 1.0) or 1.0)))

        self.low_stock_var = StringVar(value=str(self._settings.get("inventory_low_stock_threshold", 5)))
        self.scan_action_var = StringVar(value=str(self._settings.get("scan_default_action", "Receive (+)")))
        self.scan_qty_var = StringVar(value=str(self._settings.get("scan_default_qty", 1)))

        self.monitor_auto_var = tk.BooleanVar(value=bool(self._settings.get("monitor_auto_refresh", True)))
        interval_ms = int(self._settings.get("monitor_refresh_interval_ms", 2000) or 2000)
        self.monitor_interval_var = StringVar(value=f"{max(1, int(round(interval_ms / 1000)))}s")

        self.backup_dir_var = StringVar(value=str(self._settings.get("backup_dir", "")))

        self.pack(fill=tk.BOTH, expand=True)
        self._build_ui()

    def _current_theme(self) -> str:
        try:
            return str(self.style.theme.name)
        except Exception:
            return str(getattr(self.style, "theme", "flatly"))

    def _theme_names(self) -> list[str]:
        try:
            names = list(self.style.theme_names())
            return sorted({str(n) for n in names if n})
        except Exception:
            return ["flatly", "cosmo", "morph", "cyborg", "darkly", "superhero", "vapor"]

    def _scaling_label(self, scaling: float) -> str:
        return f"{int(round(scaling * 100))}%"

    def _parse_scaling(self) -> float | None:
        raw = str(self.scaling_var.get()).strip().replace("%", "")
        try:
            v = float(raw) / 100.0
        except Exception:
            return None
        if not (0.75 <= v <= 2.0):
            return None
        return v

    def _parse_int(self, value: str, *, min_v: int, max_v: int) -> int | None:
        try:
            v = int(str(value).strip())
        except Exception:
            return None
        if v < min_v or v > max_v:
            return None
        return v

    def _build_ui(self) -> None:
        Label(self, text="Settings", font=("Helvetica", 20, "bold")).pack(pady=(10, 2))
        Label(self, text="Customize appearance, inventory rules, and system behavior.", bootstyle="secondary").pack(
            pady=(0, 14)
        )

        grid = Frame(self)
        grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        grid.grid_columnconfigure(0, weight=1, uniform="col")
        grid.grid_columnconfigure(1, weight=1, uniform="col")

        appearance = tk.LabelFrame(grid, text="Appearance", padx=12, pady=10)
        appearance.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self._build_appearance(appearance)

        inventory = tk.LabelFrame(grid, text="Inventory", padx=12, pady=10)
        inventory.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self._build_inventory(inventory)

        security = tk.LabelFrame(grid, text="Security", padx=12, pady=10)
        security.grid(row=0, column=1, sticky="nsew", pady=(0, 10))
        self._build_security(security)

        system = tk.LabelFrame(grid, text="System", padx=12, pady=10)
        system.grid(row=1, column=1, sticky="nsew", pady=(0, 10))
        self._build_system(system)

    def _build_appearance(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(1, weight=1)

        Label(parent, text="Theme", bootstyle="secondary").grid(row=0, column=0, sticky="w", pady=4)
        theme = Combobox(parent, textvariable=self.theme_var, values=self._theme_names(), state="readonly")
        theme.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
        Button(parent, text="Apply", bootstyle="info", command=self.apply_theme).grid(
            row=0, column=2, sticky="e", padx=(10, 0), pady=4
        )

        Label(parent, text="Accent", bootstyle="secondary").grid(row=1, column=0, sticky="w", pady=4)
        accent = Combobox(
            parent,
            textvariable=self.accent_var,
            values=["primary", "secondary", "success", "info", "warning", "danger", "light", "dark"],
            state="readonly",
            width=14,
        )
        accent.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        Button(parent, text="Save", bootstyle="secondary-outline", command=self.save_preferences).grid(
            row=1, column=2, sticky="e", padx=(10, 0), pady=4
        )

        Label(parent, text="UI Scale", bootstyle="secondary").grid(row=2, column=0, sticky="w", pady=4)
        scale = Combobox(
            parent,
            textvariable=self.scaling_var,
            values=["90%", "100%", "110%", "120%", "130%"],
            state="readonly",
            width=10,
        )
        scale.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=4)
        Button(parent, text="Apply", bootstyle="secondary-outline", command=self.apply_scaling).grid(
            row=2, column=2, sticky="e", padx=(10, 0), pady=4
        )

        Button(parent, text="Reset to defaults", bootstyle="danger-outline", command=self.reset_defaults).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0)
        )

    def _build_inventory(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(1, weight=1)

        Label(parent, text="Low-stock threshold", bootstyle="secondary").grid(row=0, column=0, sticky="w", pady=4)
        Entry(parent, textvariable=self.low_stock_var, width=10).grid(
            row=0, column=1, sticky="w", padx=(10, 0), pady=4
        )
        Label(parent, text="items or less", bootstyle="secondary").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=4)

        Label(parent, text="Scan default action", bootstyle="secondary").grid(row=1, column=0, sticky="w", pady=4)
        Combobox(
            parent,
            textvariable=self.scan_action_var,
            values=["Receive (+)", "Dispatch (-)", "Set Qty"],
            state="readonly",
            width=14,
        ).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)

        Label(parent, text="Scan default qty", bootstyle="secondary").grid(row=2, column=0, sticky="w", pady=4)
        Entry(parent, textvariable=self.scan_qty_var, width=10).grid(
            row=2, column=1, sticky="w", padx=(10, 0), pady=4
        )

        Button(parent, text="Save inventory preferences", bootstyle="primary-outline", command=self.save_preferences).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0)
        )

    def _build_security(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)

        Label(parent, text="Manage your account and session.", bootstyle="secondary").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        Button(parent, text="Change Password", bootstyle="warning", command=self.change_my_password).grid(
            row=1, column=0, sticky="ew", pady=4
        )

        if self.on_logout is not None:
            Button(parent, text="Logout", bootstyle="danger-outline", command=self.on_logout).grid(
                row=2, column=0, sticky="ew", pady=4
            )

    def _build_system(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(1, weight=1)

        Label(parent, text="Monitor auto-refresh", bootstyle="secondary").grid(row=0, column=0, sticky="w", pady=4)
        Checkbutton(parent, text="Enabled", variable=self.monitor_auto_var).grid(
            row=0, column=1, sticky="w", padx=(10, 0), pady=4
        )

        Label(parent, text="Refresh interval", bootstyle="secondary").grid(row=1, column=0, sticky="w", pady=4)
        Combobox(parent, textvariable=self.monitor_interval_var, values=["1s", "2s", "5s", "10s"], state="readonly", width=6).grid(
            row=1, column=1, sticky="w", padx=(10, 0), pady=4
        )

        Label(parent, text="Backup folder", bootstyle="secondary").grid(row=2, column=0, sticky="w", pady=4)
        Entry(parent, textvariable=self.backup_dir_var).grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=4)
        Button(parent, text="Browse", bootstyle="secondary-outline", command=self.pick_backup_dir).grid(
            row=2, column=2, sticky="e", padx=(10, 0), pady=4
        )

        Button(parent, text="Backup now", bootstyle="success", command=self.backup_db).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(10, 4)
        )
        Button(parent, text="Restore from file…", bootstyle="warning-outline", command=self.restore_db).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=4
        )
        Button(parent, text="Open data folder", bootstyle="info-outline", command=self.open_data_folder).grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=4
        )

    def apply_theme(self):
        theme = self.theme_var.get()
        try:
            self.style.theme_use(theme)
        except Exception as e:
            messagebox.showerror("Theme", str(e))
            return

        THEME_PATH.parent.mkdir(parents=True, exist_ok=True)
        THEME_PATH.write_text(json.dumps({"theme": theme, "accent": self.accent_var.get()}, indent=4), encoding="utf-8")
        update_settings({"accent": self.accent_var.get()})
        log_event("settings", f"Theme changed to {theme}", self.current_user)
        messagebox.showinfo("Theme", f"Theme '{theme}' applied.")

    def change_my_password(self):
        if not self.current_user:
            messagebox.showerror("Password", "No user is signed in.")
            return
        new_pw = simpledialog.askstring("Change Password", "Enter a new password:", show="*")
        if not new_pw:
            return
        if len(new_pw) < 6:
            messagebox.showwarning("Password", "Use at least 6 characters.")
            return
        confirm = simpledialog.askstring("Change Password", "Confirm new password:", show="*")
        if new_pw != confirm:
            messagebox.showerror("Password", "Passwords do not match.")
            return
        try:
            change_password(self.current_user, new_pw)
            log_event("auth", "Password changed", self.current_user)
            messagebox.showinfo("Password", "Password updated.")
        except Exception as e:
            messagebox.showerror("Password", str(e))

    def save_preferences(self) -> None:
        threshold = self._parse_int(self.low_stock_var.get(), min_v=1, max_v=10_000)
        if threshold is None:
            messagebox.showerror("Inventory", "Low-stock threshold must be an integer between 1 and 10000.")
            return

        qty = self._parse_int(self.scan_qty_var.get(), min_v=1, max_v=1_000_000)
        if qty is None:
            messagebox.showerror("Inventory", "Scan default qty must be a positive integer.")
            return

        interval_ms = self._parse_int(self.monitor_interval_var.get().replace("s", ""), min_v=1, max_v=60)
        if interval_ms is None:
            messagebox.showerror("Monitor", "Refresh interval must be one of 1s/2s/5s/10s.")
            return

        backup_dir = str(self.backup_dir_var.get()).strip()
        if backup_dir and not Path(backup_dir).exists():
            messagebox.showerror("Backup folder", "Backup folder does not exist.")
            return

        update_settings(
            {
                "accent": self.accent_var.get(),
                "inventory_low_stock_threshold": threshold,
                "scan_default_action": self.scan_action_var.get(),
                "scan_default_qty": qty,
                "monitor_auto_refresh": bool(self.monitor_auto_var.get()),
                "monitor_refresh_interval_ms": int(interval_ms * 1000),
                "backup_dir": backup_dir,
            }
        )
        log_event("settings", "Updated preferences", self.current_user)
        messagebox.showinfo("Settings", "Preferences saved.")

    def apply_scaling(self) -> None:
        scaling = self._parse_scaling()
        if scaling is None:
            messagebox.showerror("UI Scale", "Choose a value between 75% and 200%.")
            return
        try:
            top = self.winfo_toplevel()
            top.tk.call("tk", "scaling", scaling)
        except Exception as e:
            messagebox.showerror("UI Scale", str(e))
            return
        update_settings({"ui_scaling": scaling})
        log_event("settings", f"UI scaling set to {self._scaling_label(scaling)}", self.current_user)
        messagebox.showinfo("UI Scale", f"UI scale applied: {self._scaling_label(scaling)}")

    def reset_defaults(self) -> None:
        if not messagebox.askyesno("Reset", "Reset settings to defaults?"):
            return
        update_settings(
            {
                "ui_scaling": 1.0,
                "accent": "primary",
                "inventory_low_stock_threshold": 5,
                "scan_default_action": "Receive (+)",
                "scan_default_qty": 1,
                "monitor_auto_refresh": True,
                "monitor_refresh_interval_ms": 2000,
                "backup_dir": "",
            }
        )
        self._settings = get_settings()
        self.theme_var.set(self._current_theme())
        self.accent_var.set(str(self._settings.get("accent", "primary")))
        self.scaling_var.set(self._scaling_label(float(self._settings.get("ui_scaling", 1.0) or 1.0)))
        self.low_stock_var.set(str(self._settings.get("inventory_low_stock_threshold", 5)))
        self.scan_action_var.set(str(self._settings.get("scan_default_action", "Receive (+)")))
        self.scan_qty_var.set(str(self._settings.get("scan_default_qty", 1)))
        self.monitor_auto_var.set(bool(self._settings.get("monitor_auto_refresh", True)))
        interval_ms = int(self._settings.get("monitor_refresh_interval_ms", 2000) or 2000)
        self.monitor_interval_var.set(f"{max(1, int(round(interval_ms / 1000)))}s")
        self.backup_dir_var.set(str(self._settings.get("backup_dir", "")))

        try:
            top = self.winfo_toplevel()
            top.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass

        log_event("settings", "Reset preferences to defaults", self.current_user)
        messagebox.showinfo("Reset", "Settings reset to defaults.")

    def pick_backup_dir(self) -> None:
        path = filedialog.askdirectory(title="Select backup folder")
        if not path:
            return
        self.backup_dir_var.set(path)
        self.save_preferences()

    def open_data_folder(self) -> None:
        try:
            os.startfile(str(DB_PATH.parent.resolve()))
        except Exception as e:
            messagebox.showerror("Open", str(e))

    def backup_db(self):
        try:
            backup_dir = str(self.backup_dir_var.get()).strip()
            folder = Path(backup_dir) if backup_dir else DB_PATH.parent
            folder.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = folder / f"{DB_PATH.stem}_backup_{ts}{DB_PATH.suffix}"
            shutil.copy(DB_PATH, dst)
            update_settings({"backup_dir": str(folder)})
            log_event("backup", f"Database backup created: {dst.name}", self.current_user)
            messagebox.showinfo("Backup", f"Backup created:\n{dst}")
        except Exception as e:
            messagebox.showerror("Backup", str(e))

    def restore_db(self):
        backup_dir = str(self.backup_dir_var.get()).strip()
        initial = Path(backup_dir) if backup_dir else DB_PATH.parent
        path = filedialog.askopenfilename(
            title="Select backup file",
            initialdir=str(initial),
            filetypes=[("SQLite DB", f"*{DB_PATH.suffix}"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            if not messagebox.askyesno(
                "Restore",
                "Restore database from the selected backup?\n\nThe app should be restarted after restore.",
            ):
                return
            shutil.copy(Path(path), DB_PATH)
            log_event("backup", f"Database restored from {Path(path).name}", self.current_user)
            messagebox.showinfo("Restore", "Database restored. Restart the app to apply.")
        except Exception as e:
            messagebox.showerror("Restore", str(e))
