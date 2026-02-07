from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from ttkbootstrap import Button, Frame, Label, Separator

from analytics_dashboard import AnalyticsDashboard
from extra_panel import (
    ExportDataPanel,
    InvoiceManagerPanel,
    LockSessionPanel,
    MonitorPanel,
    SearchProductPanel,
)
from home_panel import HomePanel
from inventory_manager import InventoryManager
from sales_manager import SalesManager
from settings_manager import SettingsManager
from supplier_manager import SupplierManager


APP_BG_PATH = Path(__file__).resolve().parent / "logo" / "background_image.png"


class Dashboard(Frame):
    def __init__(self, master, *, style, current_user: str, on_logout):
        super().__init__(master)
        self.master = master
        self.style = style
        self.current_user = current_user
        self.on_logout = on_logout
        self._locked = False
        self._active_panel_name: str | None = None
        self._active_panel = None
        self._shortcut_bind_ids: list[tuple[str, str]] = []

        self.configure(padding=0)

        # Background image (subtle) for a more realistic app feel.
        self._bg_canvas: tk.Canvas | None = None
        self._bg_photo = None
        self._bg_src = None
        self._bg_image_id: int | None = None
        self._bg_after_id: str | None = None
        self._bg_last_size: tuple[int, int] | None = None
        self._main_window_id: int | None = None

        self._bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._bg_canvas.pack(fill=tk.BOTH, expand=True)
        self._bg_canvas.configure(bg="#0b1b2b")
        self._bg_image_id = self._bg_canvas.create_image(0, 0, anchor="nw")

        self._main = Frame(self._bg_canvas, padding=0)
        self._main_window_id = self._bg_canvas.create_window(15, 15, anchor="nw", window=self._main)
        self._bg_canvas.bind("<Configure>", self._on_configure)

        self.sidebar = Frame(self._main, width=240, padding=12, bootstyle="light")
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14), pady=0)

        self.content_area = Frame(self._main, padding=15, bootstyle="light")
        self.content_area.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, pady=0)

        self._load_background_source()
        self._render_background()

        self._panels = {
            "Home": lambda: HomePanel(self.content_area, self.load_panel),
            "Inventory": lambda: InventoryManager(self.content_area, current_user=self.current_user),
            "Sales": lambda: SalesManager(self.content_area, current_user=self.current_user),
            "Suppliers": lambda: SupplierManager(self.content_area, current_user=self.current_user),
            "Analytics": lambda: AnalyticsDashboard(self.content_area),
            "Export": lambda: ExportDataPanel(self.content_area, current_user=self.current_user),
            "Invoices": lambda: InvoiceManagerPanel(self.content_area),
            "Search": lambda: SearchProductPanel(self.content_area),
            "Monitor": lambda: MonitorPanel(self.content_area),
            "Settings": lambda: SettingsManager(
                self.content_area, style=self.style, current_user=self.current_user, on_logout=self.on_logout
            ),
            "Lock": self._lock_session,
        }

        self.init_sidebar()
        self._bind_shortcuts()
        self.load_panel("Home")
        self.bind("<Destroy>", self._on_destroy, add=True)

    def _set_locked(self, locked: bool) -> None:
        self._locked = bool(locked)
        try:
            for name, btn in (self._sidebar_buttons or {}).items():
                if name == "Lock":
                    btn.configure(state="normal")
                    continue
                btn.configure(state="disabled" if self._locked else "normal")
            if getattr(self, "_logout_btn", None) is not None:
                self._logout_btn.configure(state="disabled" if self._locked else "normal")
        except Exception:
            pass

    def _bind_shortcuts(self) -> None:
        # Bind on the root so it works across all widgets, but unbind when Dashboard is destroyed.
        def bind(seq: str, fn) -> None:
            try:
                funcid = self.master.bind(seq, fn, add=True)
                if isinstance(funcid, str) and funcid:
                    self._shortcut_bind_ids.append((seq, funcid))
            except Exception:
                pass

        bind("<F1>", lambda e=None: self._show_shortcuts() or "break")
        bind("<F5>", lambda e=None: self._dispatch_shortcut("refresh") or "break")
        bind("<Control-f>", lambda e=None: self._dispatch_shortcut("focus_search") or "break")

        # Navigation (Ctrl + number)
        bind("<Control-Key-1>", lambda e=None: self.load_panel("Home") or "break")
        bind("<Control-Key-2>", lambda e=None: self.load_panel("Inventory") or "break")
        bind("<Control-Key-3>", lambda e=None: self.load_panel("Sales") or "break")
        bind("<Control-Key-4>", lambda e=None: self.load_panel("Suppliers") or "break")
        bind("<Control-Key-5>", lambda e=None: self.load_panel("Analytics") or "break")
        bind("<Control-Key-6>", lambda e=None: self.load_panel("Export") or "break")
        bind("<Control-Key-7>", lambda e=None: self.load_panel("Invoices") or "break")
        bind("<Control-Key-8>", lambda e=None: self.load_panel("Search") or "break")
        bind("<Control-Key-9>", lambda e=None: self.load_panel("Monitor") or "break")
        bind("<Control-Key-0>", lambda e=None: self.load_panel("Settings") or "break")

        # Session control
        bind("<Control-l>", lambda e=None: self.load_panel("Lock") or "break")
        bind("<Control-Shift-q>", lambda e=None: self._confirm_logout() or "break")
        bind("<Control-Shift-Q>", lambda e=None: self._confirm_logout() or "break")

        # Page actions (delegated to current panel if supported)
        bind("<Control-Return>", lambda e=None: self._dispatch_shortcut("primary") or "break")
        bind("<Delete>", lambda e=None: self._dispatch_shortcut("delete") or "break")
        bind("<Control-r>", lambda e=None: self._dispatch_shortcut("record") or "break")
        bind("<Control-e>", lambda e=None: self._dispatch_shortcut("export") or "break")
        bind("<Control-n>", lambda e=None: self._dispatch_shortcut("new") or "break")
        bind("<Control-p>", lambda e=None: self._dispatch_shortcut("print") or "break")

    def _dispatch_shortcut(self, action: str) -> bool:
        # While locked, only allow help and unlock screen interactions.
        if self._locked and action not in ("help",):
            return False
        panel = self._active_panel
        if panel is None:
            return False
        handler = getattr(panel, "handle_shortcut", None)
        if callable(handler):
            try:
                return bool(handler(action))
            except Exception:
                return False
        return False

    def _show_shortcuts(self) -> None:
        # Keep it simple: a help dialog with global + current page shortcuts.
        lines: list[str] = []
        lines.append("Global")
        lines.append("  F1                 Shortcut help")
        lines.append("  F5                 Refresh current page")
        lines.append("  Ctrl+1..0           Navigate (Home..Settings)")
        lines.append("  Ctrl+L             Lock session")
        lines.append("  Ctrl+Shift+Q        Logout")
        lines.append("")
        lines.append("Page (varies by screen)")
        lines.append("  Ctrl+F             Focus search / filter box")
        lines.append("  Ctrl+Enter         Primary action (Add/Apply/Record)")
        lines.append("  Delete             Delete selected item/row")
        lines.append("  Ctrl+R             Record/Run main action (if supported)")
        lines.append("  Ctrl+E             Export (if supported)")
        lines.append("  Ctrl+N             New/Clear form (if supported)")
        lines.append("  Ctrl+P             Print (if supported)")

        panel_name = self._active_panel_name or ""
        if panel_name == "Inventory":
            lines.append("")
            lines.append("Inventory")
            lines.append("  Ctrl+F             Focus search (table)")
            lines.append("  Ctrl+Enter         Apply barcode action (when Scan Mode is ON)")
            lines.append("  Delete             Delete selected product (if selected)")
            lines.append("  Ctrl+E             Export inventory")
            lines.append("  Ctrl+N             Clear form")
        elif panel_name == "Sales":
            lines.append("")
            lines.append("Sales")
            lines.append("  Ctrl+Enter         Add item to invoice")
            lines.append("  Delete             Delete selected invoice item")
            lines.append("  F5                 Refresh preview / products")
            lines.append("  Ctrl+R             Record sale")
            lines.append("  Ctrl+P             Print last invoice")
        elif panel_name == "Analytics":
            lines.append("")
            lines.append("Analytics")
            lines.append("  F5                 Refresh charts")
            lines.append("  Ctrl+E             Export report")

        try:
            messagebox.showinfo("Shortcuts", "\n".join(lines))
        except Exception:
            pass

    def _load_background_source(self) -> None:
        try:
            from PIL import Image  # type: ignore

            if APP_BG_PATH.exists():
                self._bg_src = Image.open(APP_BG_PATH).convert("RGB")
        except Exception:
            self._bg_src = None

    def _on_configure(self, _e=None) -> None:
        if self._bg_after_id is not None:
            try:
                self.after_cancel(self._bg_after_id)
            except Exception:
                pass
            self._bg_after_id = None
        self._bg_after_id = self.after(120, self._render_background)

    def _render_background(self) -> None:
        if self._bg_canvas is None:
            return

        w = max(1, int(self._bg_canvas.winfo_width()))
        h = max(1, int(self._bg_canvas.winfo_height()))
        if self._bg_last_size == (w, h):
            return
        self._bg_last_size = (w, h)

        # Keep a small margin around the app chrome so the background is visible.
        margin = 14
        if self._main_window_id is not None:
            try:
                self._bg_canvas.coords(self._main_window_id, margin, margin)
                self._bg_canvas.itemconfigure(
                    self._main_window_id, width=max(1, w - margin * 2), height=max(1, h - margin * 2)
                )
            except Exception:
                pass

        try:
            from PIL import Image, ImageEnhance, ImageFilter, ImageTk  # type: ignore

            if self._bg_src is None:
                img = Image.new("RGB", (w, h), (11, 27, 43))
            else:
                src = self._bg_src
                scale = max(w / src.width, h / src.height)
                nw, nh = int(src.width * scale), int(src.height * scale)
                img = src.resize((nw, nh), Image.Resampling.BILINEAR)
                left = (nw - w) // 2
                top = (nh - h) // 2
                img = img.crop((left, top, left + w, top + h))

                # Performance: blur at a lower resolution.
                sw, sh = max(1, w // 3), max(1, h // 3)
                small = img.resize((sw, sh), Image.Resampling.BILINEAR)
                small = small.filter(ImageFilter.GaussianBlur(radius=3))
                img = small.resize((w, h), Image.Resampling.LANCZOS)
                img = ImageEnhance.Brightness(img).enhance(0.78)
                img = ImageEnhance.Contrast(img).enhance(1.08)

            img_rgba = img.convert("RGBA")
            # Dark overlay for legibility.
            overlay = Image.new("RGBA", (w, h), (6, 20, 35, 140))
            img_rgba = Image.alpha_composite(img_rgba, overlay)

            self._bg_photo = ImageTk.PhotoImage(img_rgba)
            if self._bg_image_id is None:
                self._bg_image_id = self._bg_canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
            else:
                self._bg_canvas.itemconfigure(self._bg_image_id, image=self._bg_photo)
        except Exception:
            # Fallback: solid dark background if PIL is missing.
            try:
                self._bg_canvas.configure(bg="#0b1b2b")
            except Exception:
                pass

    def init_sidebar(self):
        Label(self.sidebar, text="Grocery Mart", font=("Helvetica", 18, "bold")).pack(pady=(10, 3))
        Label(self.sidebar, text=f"Signed in as: {self.current_user}", font=("Helvetica", 9, "italic")).pack(
            pady=(0, 12)
        )
        Separator(self.sidebar, orient="horizontal").pack(fill=tk.X, pady=(0, 12))

        self._sidebar_buttons: dict[str, Button] = {}
        buttons = [
            ("Home", "Home", "primary"),
            ("Inventory", "Inventory", "info"),
            ("Sales", "Sales", "success"),
            ("Suppliers", "Suppliers", "secondary"),
            ("Analytics", "Analytics", "warning"),
            ("Export", "Export", "secondary"),
            ("Invoices", "Invoices", "info"),
            ("Search", "Search", "dark"),
            ("Monitor", "Monitor", "primary"),
            ("Settings", "Settings", "light"),
            ("Lock", "Lock", "danger"),
        ]

        for label, panel, style in buttons:
            btn = Button(
                self.sidebar, text=label, bootstyle=f"{style}-outline", command=lambda p=panel: self.load_panel(p)
            )
            btn.pack(pady=5, fill=tk.X, padx=5)
            self._sidebar_buttons[panel] = btn

        Separator(self.sidebar, orient="horizontal").pack(fill=tk.X, pady=(18, 8))
        self._logout_btn = Button(self.sidebar, text="Logout", bootstyle="danger", command=self._confirm_logout)
        self._logout_btn.pack(fill=tk.X, padx=5)

    def _confirm_logout(self) -> None:
        if messagebox.askyesno("Logout", "Logout now?"):
            self.on_logout()

    def _lock_session(self) -> None:
        self._set_locked(True)
        for widget in self.content_area.winfo_children():
            widget.destroy()

        def _on_unlock() -> None:
            self._set_locked(False)
            self.load_panel("Home")

        self._active_panel = LockSessionPanel(self.content_area, current_user=self.current_user, on_unlock=_on_unlock)
        self._active_panel_name = "Lock"
        return self._active_panel

    def load_panel(self, name):
        if self._locked and name != "Lock":
            return
        for widget in self.content_area.winfo_children():
            widget.destroy()
        panel_factory = self._panels.get(name)
        if panel_factory:
            self._active_panel_name = name
            panel = panel_factory()
            self._active_panel = panel
        else:
            Label(self.content_area, text=f"Unknown panel: {name}").pack()
            self._active_panel_name = None
            self._active_panel = None

    def _on_destroy(self, event) -> None:
        if event.widget is not self:
            return
        for seq, funcid in list(self._shortcut_bind_ids):
            try:
                self.master.unbind(seq, funcid)
            except Exception:
                pass
        self._shortcut_bind_ids.clear()
