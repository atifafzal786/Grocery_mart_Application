from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from threading import Event, Lock, Thread

from ttkbootstrap import Button, Combobox, Entry, Frame, Label, Scrollbar, StringVar, Treeview

from database import connect, log_event
from utils.app_settings import get_setting
from utils.helpers import validate_product_data

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


DEFAULT_LOW_STOCK_THRESHOLD = 5


class InventoryManager(Frame):
    """
    Single place to manage inventory details:
    - Add / Update / Delete products (catalog + stock)
    - Search, view, alerts, export
    """

    def __init__(self, master, *, current_user: str | None = None):
        super().__init__(master, padding=10)
        self.current_user = current_user
        self.pack(fill=tk.BOTH, expand=True)

        self.low_stock_threshold = int(get_setting("inventory_low_stock_threshold", DEFAULT_LOW_STOCK_THRESHOLD) or DEFAULT_LOW_STOCK_THRESHOLD)

        self.search_var = StringVar()
        self.search_frame: tk.Frame | None = None
        self.scan_var = StringVar()
        self.scan_action_var = StringVar(value=str(get_setting("scan_default_action", "Receive (+)") or "Receive (+)"))
        self.scan_qty_var = StringVar(value=str(get_setting("scan_default_qty", 1) or 1))
        self.scan_status_var = StringVar(value="Scan Mode: OFF")
        self.scan_mode = tk.BooleanVar(value=False)
        self._camera_stop = Event()
        self._camera_thread: Thread | None = None
        self._camera_ui_after_id: str | None = None
        self._camera_lock = Lock()
        self._latest_frame = None
        self._camera_photo = None
        self._camera_panel: tk.LabelFrame | None = None
        self._camera_image: tk.Label | None = None
        self._camera_debug_var = StringVar(value="")
        self._camera_stats: dict[str, object] = {
            "frames": 0,
            "decode_attempts": 0,
            "last_code": "",
            "decoder": "",
            "size": "",
        }
        self.fields: dict[str, StringVar] = {}
        self.selected_id: int | None = None
        self._supplier_name_to_id: dict[str, int] = {}
        self._form_visible = True
        self.form_toggle_btn: Button | None = None
        self.scan_toggle_btn: Button | None = None
        self.camera_btn: Button | None = None
        self.scan_entry: Entry | None = None
        self._search_entry: Entry | None = None
        self.table_frame: tk.Frame | None = None

        self._build_header()
        self._build_form()  # can be collapsed
        self._build_search_bar()
        self._build_table()

        self.refresh_suppliers()
        self.load_data()
        self.smart_alerts()
        self.bind("<Destroy>", self._on_destroy, add=True)

    def _build_header(self) -> None:
        Label(self, text="Inventory", font=("Helvetica", 20, "bold")).pack(pady=(5, 10))

        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.form_toggle_btn = Button(
            top_frame,
            text="Hide Form" if self._form_visible else "Show Form",
            bootstyle="secondary-outline",
            command=self.toggle_form,
        )
        self.form_toggle_btn.pack(side=tk.RIGHT, padx=(0, 8))

        Button(top_frame, text="Export", bootstyle="success-outline", command=self.export_inventory).pack(
            side=tk.RIGHT, padx=10
        )

        scan_frame = tk.Frame(self)
        scan_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.scan_toggle_btn = Button(
            scan_frame,
            text="Scan Mode: OFF",
            bootstyle="secondary-outline",
            command=self.toggle_scan_mode,
        )
        self.scan_toggle_btn.pack(side=tk.LEFT, padx=(0, 12))

        Label(scan_frame, text="Barcode:").pack(side=tk.LEFT)
        self.scan_entry = Entry(scan_frame, textvariable=self.scan_var, width=28)
        self.scan_entry.pack(side=tk.LEFT, padx=(8, 12))
        self.scan_entry.bind("<Return>", lambda _e: self.handle_barcode_scan())

        self.camera_btn = Button(
            scan_frame,
            text="Camera Scan",
            bootstyle="info-outline",
            command=self.toggle_camera_scan,
        )
        self.camera_btn.pack(side=tk.LEFT, padx=(0, 12))

        Label(scan_frame, text="Action:").pack(side=tk.LEFT)
        action = Combobox(
            scan_frame,
            textvariable=self.scan_action_var,
            values=["Receive (+)", "Dispatch (-)", "Set Qty"],
            state="readonly",
            width=14,
        )
        action.pack(side=tk.LEFT, padx=(8, 12))

        Label(scan_frame, text="Qty:").pack(side=tk.LEFT)
        qty_entry = Entry(scan_frame, textvariable=self.scan_qty_var, width=8)
        qty_entry.pack(side=tk.LEFT, padx=(8, 12))
        qty_entry.bind("<Return>", lambda _e: self.handle_barcode_scan())

        Button(scan_frame, text="Apply", bootstyle="primary-outline", command=self.handle_barcode_scan).pack(
            side=tk.LEFT
        )

        Label(scan_frame, textvariable=self.scan_status_var).pack(side=tk.RIGHT)

        self._camera_panel = tk.LabelFrame(self, text="Camera Preview", padx=10, pady=10)
        # Hidden by default; shown when camera scan starts.
        self._camera_panel.pack_forget()
        self._camera_image = tk.Label(self._camera_panel, text="Starting camera…", width=62, anchor="center")
        self._camera_image.pack(side=tk.LEFT)
        tips = tk.Frame(self._camera_panel)
        tips.pack(side=tk.LEFT, padx=14, fill=tk.BOTH, expand=True)
        Label(tips, text="Tips:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        Label(
            tips,
            text=(
                "- Hold the barcode steady for ~1s\n"
                "- Use good lighting (avoid glare)\n"
                "- If 1D barcode is slow, try moving closer/farther"
            ),
            justify="left",
        ).pack(anchor="w", pady=(2, 10))
        Label(tips, textvariable=self._camera_debug_var, justify="left", font=("Consolas", 9)).pack(
            anchor="w", pady=(0, 10)
        )
        Button(tips, text="Stop Camera", bootstyle="danger-outline", command=self.stop_camera_scan).pack(anchor="w")

    def _build_search_bar(self) -> None:
        self.search_frame = tk.LabelFrame(self, text="Search & Filter", padx=10, pady=8)
        self.search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        Label(self.search_frame, text="Search:").pack(side=tk.LEFT)
        self._search_entry = Entry(self.search_frame, textvariable=self.search_var, width=50)
        self._search_entry.pack(side=tk.LEFT, padx=(8, 10))
        self._search_entry.bind("<KeyRelease>", lambda _e: self.load_data())

        Button(
            self.search_frame,
            text="Clear",
            bootstyle="secondary-outline",
            command=lambda: (self.search_var.set(""), self.load_data()),
        ).pack(side=tk.LEFT)

    def handle_shortcut(self, action: str) -> bool:
        action = (action or "").strip().lower()
        try:
            if action in ("focus_search", "search"):
                if self._search_entry is not None:
                    self._search_entry.focus_set()
                    return True
                return False

            if action in ("refresh",):
                self.load_data()
                return True

            if action in ("primary",):
                # If scan mode is ON, Ctrl+Enter applies the scan action; otherwise no-op.
                if bool(self.scan_mode.get()):
                    self.handle_barcode_scan()
                    return True
                return False

            if action in ("export",):
                self.export_inventory()
                return True

            if action in ("new",):
                self.clear_form()
                return True

            if action in ("delete",):
                if self.selected_id is not None:
                    self.delete_product()
                    return True
                return False
        except Exception:
            return False
        return False

    def _build_form(self) -> None:
        self.form_frame = tk.Frame(self, relief=tk.GROOVE, borderwidth=1)
        self.form_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        header = tk.Frame(self.form_frame)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        Label(header, text="Add / Update Item", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)

        btns = tk.Frame(header)
        btns.pack(side=tk.LEFT, padx=(14, 0))
        Button(btns, text="Add", bootstyle="success", width=10, command=self.add_product).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        Button(btns, text="Update", bootstyle="warning", width=10, command=self.update_product).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        Button(btns, text="Delete", bootstyle="danger", width=10, command=self.delete_product).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        Button(btns, text="Clear", bootstyle="secondary", width=10, command=self.clear_form).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        Button(btns, text="Refresh Suppliers", bootstyle="info-outline", command=self.refresh_suppliers).pack(
            side=tk.LEFT
        )

        content = tk.Frame(self.form_frame)
        content.pack(fill=tk.X, padx=10, pady=10)

        col1 = tk.Frame(content)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        col2 = tk.Frame(content)
        col2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        for col in (col1, col2):
            col.grid_columnconfigure(1, weight=1)

        labels = [
            "Product Name",
            "Barcode",
            "Category",
            "Supplier",
            "Unit",
            "Price",
            "GST %",
            "Tax %",
            "Quantity",
            "Expiry (YYYY-MM-DD)",
        ]
        keys = ["name", "barcode", "category", "supplier", "unit", "price", "gst_percent", "tax_percent", "quantity", "expiry"]
        categories = ["Pulses", "Grains", "Snacks", "Drinks", "Toiletries", "Stationery", "Other"]

        for i, (label_text, key) in enumerate(zip(labels, keys)):
            target = col1 if i < 4 else col2
            row = i if i < 4 else i - 4
            Label(target, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            var = StringVar()
            if key == "category":
                widget = Combobox(target, textvariable=var, values=categories, state="readonly")
            elif key == "supplier":
                widget = Combobox(target, textvariable=var, values=[], state="readonly")
                self.supplier_combo = widget
            else:
                widget = Entry(target, textvariable=var)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.fields[key] = var

        self.fields["barcode"].set("")
        self.fields["gst_percent"].set("0")
        self.fields["tax_percent"].set("0")

    def toggle_scan_mode(self) -> None:
        enabled = not bool(self.scan_mode.get())
        self.scan_mode.set(enabled)
        if self.scan_toggle_btn is not None:
            try:
                self.scan_toggle_btn.config(
                    text="Scan Mode: ON" if enabled else "Scan Mode: OFF",
                    bootstyle="success-outline" if enabled else "secondary-outline",
                )
            except Exception:
                pass
        if not enabled:
            self.stop_camera_scan()
        self.scan_status_var.set("Ready to scan..." if enabled else "Scan Mode: OFF")
        if enabled and self.scan_entry is not None:
            try:
                self.scan_entry.focus_set()
                self.scan_entry.selection_range(0, tk.END)
            except Exception:
                pass

    def toggle_camera_scan(self) -> None:
        if self._camera_thread is not None and self._camera_thread.is_alive():
            self.stop_camera_scan()
            return
        self.start_camera_scan()

    def start_camera_scan(self) -> None:
        if self._camera_thread is not None and self._camera_thread.is_alive():
            return

        if not bool(self.scan_mode.get()):
            self.scan_mode.set(True)
            if self.scan_toggle_btn is not None:
                try:
                    self.scan_toggle_btn.config(text="Scan Mode: ON", bootstyle="success-outline")
                except Exception:
                    pass

        try:
            import cv2  # type: ignore
        except Exception as e:
            messagebox.showerror(
                "Camera Scan",
                "Camera scanning requires OpenCV.\n\n"
                "Install: pip install opencv-contrib-python\n\n"
                f"Error: {e}",
            )
            return

        decode = None
        decoder_name = "opencv"
        try:
            from pyzbar.pyzbar import ZBarSymbol, decode as _decode  # type: ignore

            # Limit symbologies for stability/perf. This also avoids rare decoder assertions
            # from unrelated formats (e.g. PDF417) on noisy frames.
            allowed = [
                ZBarSymbol.EAN13,
                ZBarSymbol.EAN8,
                ZBarSymbol.UPCA,
                ZBarSymbol.UPCE,
                ZBarSymbol.CODE128,
                ZBarSymbol.CODE39,
                ZBarSymbol.CODE93,
                ZBarSymbol.I25,
                ZBarSymbol.QRCODE,
            ]

            def decode(img):  # type: ignore[no-redef]
                return _decode(img, symbols=allowed)

            decoder_name = "pyzbar+opencv"
        except Exception:
            decode = None
            decoder_name = "opencv"

        self.scan_status_var.set("Camera scanning...")
        with self._camera_lock:
            self._camera_stats = {
                "frames": 0,
                "decode_attempts": 0,
                "last_code": "",
                "decoder": decoder_name,
                "size": "",
            }
        self._camera_stop.clear()
        if self.camera_btn is not None:
            try:
                self.camera_btn.config(text="Stop Camera", bootstyle="danger-outline")
            except Exception:
                pass

        if self._camera_panel is not None:
            try:
                self._camera_panel.pack(fill=tk.X, padx=10, pady=(0, 10))
            except Exception:
                pass

        self._camera_thread = Thread(target=self._camera_capture_loop, args=(cv2, decode), daemon=True)
        self._camera_thread.start()
        self._schedule_camera_ui_update(cv2)

    def stop_camera_scan(self) -> None:
        self._camera_stop.set()
        if self.camera_btn is not None:
            try:
                self.camera_btn.config(text="Camera Scan", bootstyle="info-outline")
            except Exception:
                pass
        if self._camera_ui_after_id is not None:
            try:
                self.after_cancel(self._camera_ui_after_id)
            except Exception:
                pass
            self._camera_ui_after_id = None
        if self._camera_panel is not None:
            try:
                self._camera_panel.pack_forget()
            except Exception:
                pass
        with self._camera_lock:
            self._latest_frame = None
        self._camera_photo = None
        if bool(self.scan_mode.get()):
            self.scan_status_var.set("Ready to scan...")

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.stop_camera_scan()

    def _schedule_camera_ui_update(self, cv2) -> None:  # type: ignore[no-untyped-def]
        if self._camera_ui_after_id is not None:
            try:
                self.after_cancel(self._camera_ui_after_id)
            except Exception:
                pass
            self._camera_ui_after_id = None

        def tick() -> None:
            if self._camera_stop.is_set():
                self._camera_ui_after_id = None
                return
            self._update_camera_preview(cv2)
            self._camera_ui_after_id = self.after(66, tick)  # ~15 FPS (lighter on CPU)

        self._camera_ui_after_id = self.after(0, tick)

    def _update_camera_preview(self, cv2) -> None:  # type: ignore[no-untyped-def]
        if self._camera_image is None:
            return
        with self._camera_lock:
            frame = self._latest_frame
            stats = dict(self._camera_stats)
        if frame is None:
            self._camera_debug_var.set(
                f"Decoder: {stats.get('decoder','')}\nStatus: waiting for camera frame…"
            )
            return
        try:
            from PIL import Image, ImageTk  # type: ignore

            # Downscale using OpenCV first (faster than PIL on large frames).
            h, w = frame.shape[:2]
            target_w, target_h = 520, 320
            scale = min(target_w / max(w, 1), target_h / max(h, 1))
            if scale < 1.0:
                frame_small = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                frame_small = frame

            rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._camera_photo = ImageTk.PhotoImage(img)
            self._camera_image.configure(image=self._camera_photo)
            self._camera_debug_var.set(
                f"Decoder: {stats.get('decoder','')}\n"
                f"Frame: {stats.get('size','')}\n"
                f"Seen: {stats.get('frames',0)}  Attempts: {stats.get('decode_attempts',0)}\n"
                f"Last: {stats.get('last_code','') or '-'}"
            )
        except Exception:
            return

    def _camera_capture_loop(self, cv2, decode) -> None:  # type: ignore[no-untyped-def]
        cap = None
        try:
            cap = cv2.VideoCapture(0)
            if not cap or not cap.isOpened():
                self.after(0, lambda: messagebox.showerror("Camera Scan", "Could not open the camera."))
                self.after(0, lambda: self.scan_status_var.set("Camera unavailable."))
                return

            # Request a higher resolution if supported (helps 1D barcodes).
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            except Exception:
                pass

            def opencv_detect(frame) -> list[str]:
                # OpenCV contrib exposes barcode APIs inconsistently across builds; try a few.
                candidates = []
                try:
                    if hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
                        det = cv2.barcode.BarcodeDetector()
                        ok, decoded_info, _decoded_type, _points = det.detectAndDecode(frame)
                        if ok and decoded_info:
                            candidates.extend([s for s in decoded_info if s])
                except Exception:
                    pass
                try:
                    if hasattr(cv2, "barcode_BarcodeDetector"):
                        det = cv2.barcode_BarcodeDetector()
                        ok, decoded_info, _decoded_type, _points = det.detectAndDecode(frame)
                        if ok and decoded_info:
                            candidates.extend([s for s in decoded_info if s])
                except Exception:
                    pass
                return [c.strip() for c in candidates if c and str(c).strip()]

            def pyzbar_detect(frame) -> list[str]:
                if decode is None:
                    return []
                try:
                    codes = decode(frame) or []
                except Exception:
                    codes = []
                out = []
                for c in codes:
                    try:
                        out.append(c.data.decode("utf-8").strip())
                    except Exception:
                        continue
                return [s for s in out if s]

            frame_idx = 0
            while not self._camera_stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue

                h, w = frame.shape[:2]
                with self._camera_lock:
                    self._latest_frame = frame
                    self._camera_stats["frames"] = int(self._camera_stats.get("frames", 0) or 0) + 1
                    if not self._camera_stats.get("size"):
                        self._camera_stats["size"] = f"{w}x{h}"

                frame_idx += 1
                # Decode every other frame to keep UI responsive.
                if frame_idx % 2 == 0:
                    data = ""
                    with self._camera_lock:
                        self._camera_stats["decode_attempts"] = int(self._camera_stats.get("decode_attempts", 0) or 0) + 1

                    # Center ROI (helps reduce noise and speeds decode).
                    try:
                        x0 = int(w * 0.1)
                        y0 = int(h * 0.2)
                        x1 = int(w * 0.9)
                        y1 = int(h * 0.8)
                        roi = frame[y0:y1, x0:x1]
                    except Exception:
                        roi = frame

                    # Preprocess (helps 1D barcodes with low contrast).
                    try:
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        gray = cv2.GaussianBlur(gray, (3, 3), 0)
                        gray = cv2.equalizeHist(gray)
                        _t, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    except Exception:
                        gray = roi
                        bw = roi

                    # Prefer OpenCV's detector if present; otherwise fall back to pyzbar.
                    found = opencv_detect(roi)
                    if not found:
                        found = opencv_detect(gray)
                    if not found:
                        found = pyzbar_detect(bw)
                    if not found:
                        found = pyzbar_detect(gray)

                    if found:
                        data = found[0].strip()

                    if data:
                        self._camera_stop.set()
                        with self._camera_lock:
                            self._camera_stats["last_code"] = data

                        def on_scan() -> None:
                            self.scan_var.set(data)
                            self.handle_barcode_scan()

                        self.after(0, on_scan)
                        break
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            self.after(0, self.stop_camera_scan)

    def _parse_scan_qty(self) -> int | None:
        try:
            qty = int(str(self.scan_qty_var.get()).strip())
        except Exception:
            return None
        return qty if qty > 0 else None

    def _barcode_owner_id(self, barcode: str) -> int | None:
        with connect() as conn:
            row = conn.execute("SELECT id FROM products WHERE barcode = ?", (barcode,)).fetchone()
        return int(row["id"]) if row else None

    def _validate_barcode_unique(self, barcode: str, *, exclude_id: int | None = None) -> bool:
        barcode = barcode.strip()
        if not barcode:
            return True
        owner_id = self._barcode_owner_id(barcode)
        if owner_id is None:
            return True
        if exclude_id is not None and owner_id == exclude_id:
            return True
        messagebox.showerror("Barcode", "This barcode is already assigned to another product.")
        return False

    def _select_tree_row(self, product_id: int) -> None:
        try:
            for item in self.tree.get_children():
                values = self.tree.item(item).get("values") or []
                if values and int(values[0]) == int(product_id):
                    self.tree.selection_set(item)
                    self.tree.focus(item)
                    self.tree.see(item)
                    return
        except Exception:
            return

    def handle_barcode_scan(self) -> None:
        if not bool(self.scan_mode.get()):
            self.scan_status_var.set("Scan Mode: OFF")
            return

        barcode = str(self.scan_var.get()).strip()
        if not barcode:
            return

        qty = self._parse_scan_qty()
        if qty is None:
            messagebox.showerror("Scan Qty", "Qty must be a positive integer.")
            return

        action = str(self.scan_action_var.get()).strip()

        with connect() as conn:
            row = conn.execute(
                "SELECT id, name, quantity FROM products WHERE barcode = ?",
                (barcode,),
            ).fetchone()

        if not row:
            if self.selected_id and messagebox.askyesno(
                "Unknown Barcode",
                "Barcode not found. Assign this barcode to the currently selected product?",
            ):
                if not self._validate_barcode_unique(barcode):
                    return
                try:
                    with connect() as conn:
                        conn.execute("UPDATE products SET barcode = ? WHERE id = ?", (barcode, self.selected_id))
                        conn.commit()
                    log_event("product", f"Assigned barcode {barcode} to product ID {self.selected_id}", self.current_user)
                    self.load_data()
                    self._select_tree_row(self.selected_id)
                    self.scan_status_var.set("Barcode assigned.")
                except Exception as e:
                    messagebox.showerror("Barcode", str(e))
            else:
                messagebox.showwarning(
                    "Unknown Barcode",
                    "Barcode not found. Select a product and scan again to assign, or add a new product first.",
                )
            self.scan_var.set("")
            if self.scan_entry is not None:
                try:
                    self.scan_entry.focus_set()
                except Exception:
                    pass
            return

        product_id = int(row["id"])
        name = str(row["name"])
        current_qty = int(row["quantity"])

        if action == "Set Qty":
            new_qty = qty
        elif action == "Dispatch (-)":
            new_qty = current_qty - qty
        else:
            new_qty = current_qty + qty

        if new_qty < 0:
            messagebox.showerror("Stock", f"Cannot dispatch {qty}. Current stock for {name} is {current_qty}.")
            return

        try:
            with connect() as conn:
                conn.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, product_id))
                conn.commit()
            log_event("product", f"Barcode {barcode}: {action} {qty} on {name} (qty {current_qty} -> {new_qty})", self.current_user)
            self.load_data()
            self._select_tree_row(product_id)
            self.scan_status_var.set(f"{name}: {current_qty} → {new_qty}")
        except Exception as e:
            messagebox.showerror("Update failed", str(e))
        finally:
            self.scan_var.set("")
            if self.scan_entry is not None:
                try:
                    self.scan_entry.focus_set()
                except Exception:
                    pass

    def toggle_form(self) -> None:
        self._form_visible = not self._form_visible
        if self._form_visible:
            # Keep the form positioned above search + table when re-packing.
            before = self.search_frame or self.table_frame
            if before is not None:
                self.form_frame.pack(before=before, fill=tk.X, padx=10, pady=(0, 10))
            else:
                self.form_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        else:
            self.form_frame.pack_forget()

        if self.form_toggle_btn is not None:
            try:
                self.form_toggle_btn.config(text="Hide Form" if self._form_visible else "Show Form")
            except Exception:
                pass

    def _build_table(self) -> None:
        self.table_frame = tk.Frame(self)
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = Treeview(
            self.table_frame,
            columns=("id", "name", "category", "supplier", "unit", "price", "gst", "tax", "quantity", "expiry"),
            show="headings",
            height=15,
        )

        headers = {
            "id": "ID",
            "name": "Product Name",
            "category": "Category",
            "supplier": "Supplier",
            "unit": "Unit",
            "price": "Price",
            "gst": "GST %",
            "tax": "Tax %",
            "quantity": "Quantity",
            "expiry": "Expiry Date",
        }

        for col, text in headers.items():
            self.tree.heading(col, text=text)
            width = 120
            anchor = "center"
            if col == "name":
                width = 220
                anchor = "w"
            elif col in ("gst", "tax"):
                width = 80
            elif col == "price":
                width = 110
            elif col == "expiry":
                width = 130
            self.tree.column(col, anchor=anchor, width=width)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        scroll = Scrollbar(self.table_frame, command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.tag_configure("lowstock", background="#fff3cd")  # Light yellow
        self.tree.tag_configure("expiring", background="#f8d7da")  # Light red

    def refresh_suppliers(self) -> None:
        with connect() as conn:
            rows = conn.execute("SELECT id, name FROM suppliers ORDER BY name ASC").fetchall()
        self._supplier_name_to_id = {r["name"]: int(r["id"]) for r in rows}
        names = [""] + list(self._supplier_name_to_id.keys())
        self.supplier_combo["values"] = names
        if self.fields["supplier"].get() not in self._supplier_name_to_id and self.fields["supplier"].get() != "":
            self.fields["supplier"].set("")

    def _read_form(self) -> dict[str, str]:
        return {k: v.get().strip() for k, v in self.fields.items()}

    def load_data(self):
        keyword = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        with connect() as conn:
            rows = conn.execute(
                """SELECT p.id, p.name, p.category, COALESCE(s.name, '') AS supplier,
                          p.unit, p.price, p.gst_percent, p.tax_percent, p.quantity, p.expiry
                   FROM products p
                   LEFT JOIN suppliers s ON s.id = p.supplier_id
                   ORDER BY p.id DESC"""
            ).fetchall()

        for row in rows:
            if keyword:
                if keyword not in row["name"].lower() and keyword not in row["category"].lower():
                    continue

            tags: tuple[str, ...] = ()
            expiry = row["expiry"]
            if expiry:
                try:
                    exp_date = datetime.strptime(str(expiry), "%Y-%m-%d")
                    if (exp_date - datetime.now()).days <= 7:
                        tags = ("expiring",)
                except Exception:
                    pass
            if int(row["quantity"]) <= self.low_stock_threshold:
                tags = ("lowstock",)

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
                    row["gst_percent"],
                    row["tax_percent"],
                    row["quantity"],
                    row["expiry"],
                ),
                tags=tags,
            )

    def load_selected(self, _event=None) -> None:
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
        self.fields["gst_percent"].set(str(data[6] if data[6] not in (None, "None", "") else "0"))
        self.fields["tax_percent"].set(str(data[7] if data[7] not in (None, "None", "") else "0"))
        self.fields["quantity"].set(str(data[8]))
        self.fields["expiry"].set("" if data[9] in (None, "None") else str(data[9]))
        try:
            with connect() as conn:
                row = conn.execute("SELECT barcode FROM products WHERE id = ?", (self.selected_id,)).fetchone()
            self.fields["barcode"].set("" if not row or not row["barcode"] else str(row["barcode"]))
        except Exception:
            self.fields["barcode"].set("")

    def add_product(self) -> None:
        data = self._read_form()
        if not validate_product_data(data):
            messagebox.showwarning("Incomplete", "Required: name, category, unit, price, quantity.")
            return

        if not self._validate_barcode_unique(data.get("barcode", "")):
            return

        supplier_id = self._supplier_name_to_id.get(data.get("supplier") or "", None)
        try:
            price = float(data["price"])
            qty = int(data["quantity"])
            gst_percent = float(data.get("gst_percent") or 0)
            tax_percent = float(data.get("tax_percent") or 0)
        except ValueError:
            messagebox.showerror(
                "Invalid input",
                "Price must be a number, Quantity must be an integer, and GST/Tax must be numbers.",
            )
            return
        if not (0 <= gst_percent <= 100) or not (0 <= tax_percent <= 100):
            messagebox.showerror("Invalid tax", "GST% and Tax% must be between 0 and 100.")
            return

        try:
            with connect() as conn:
                conn.execute(
                    """INSERT INTO products (name, barcode, category, unit, price, gst_percent, tax_percent, quantity, expiry, supplier_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["name"],
                        data.get("barcode") or None,
                        data["category"],
                        data["unit"],
                        price,
                        gst_percent,
                        tax_percent,
                        qty,
                        data.get("expiry") or None,
                        supplier_id,
                    ),
                )
                conn.commit()
            log_event("product", f"Added product: {data['name']}", self.current_user)
            self.load_data()
            self.clear_form()
            messagebox.showinfo("Saved", "Product added.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_product(self) -> None:
        if not self.selected_id:
            messagebox.showwarning("Select", "No product selected.")
            return

        data = self._read_form()
        if not validate_product_data(data):
            messagebox.showwarning("Incomplete", "Required: name, category, unit, price, quantity.")
            return

        if not self._validate_barcode_unique(data.get("barcode", ""), exclude_id=self.selected_id):
            return

        supplier_id = self._supplier_name_to_id.get(data.get("supplier") or "", None)
        try:
            price = float(data["price"])
            qty = int(data["quantity"])
            gst_percent = float(data.get("gst_percent") or 0)
            tax_percent = float(data.get("tax_percent") or 0)
        except ValueError:
            messagebox.showerror(
                "Invalid input",
                "Price must be a number, Quantity must be an integer, and GST/Tax must be numbers.",
            )
            return
        if not (0 <= gst_percent <= 100) or not (0 <= tax_percent <= 100):
            messagebox.showerror("Invalid tax", "GST% and Tax% must be between 0 and 100.")
            return

        try:
            with connect() as conn:
                conn.execute(
                    """UPDATE products
                       SET name=?, barcode=?, category=?, unit=?, price=?, gst_percent=?, tax_percent=?, quantity=?, expiry=?, supplier_id=?
                       WHERE id=?""",
                    (
                        data["name"],
                        data.get("barcode") or None,
                        data["category"],
                        data["unit"],
                        price,
                        gst_percent,
                        tax_percent,
                        qty,
                        data.get("expiry") or None,
                        supplier_id,
                        self.selected_id,
                    ),
                )
                conn.commit()
            log_event("product", f"Updated product: {data['name']} (ID {self.selected_id})", self.current_user)
            self.load_data()
            self.clear_form()
            messagebox.showinfo("Updated", "Product updated.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_product(self) -> None:
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
            log_event(
                "product",
                f"Deleted product: {(row['name'] if row else 'ID')} {self.selected_id}",
                self.current_user,
            )
            self.load_data()
            self.clear_form()
            messagebox.showinfo("Deleted", "Product deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_form(self) -> None:
        for var in self.fields.values():
            var.set("")
        self.selected_id = None

    def export_inventory(self):
        if pd is None:
            messagebox.showerror("Export", "Missing dependency: pandas. Install with `pip install -r requirements.txt`.")
            return

        with connect() as conn:
            rows = conn.execute(
                """SELECT p.id, p.name, p.barcode, p.category, COALESCE(s.name, '') AS supplier,
                          p.unit, p.price, p.gst_percent, p.tax_percent, p.quantity, p.expiry
                   FROM products p
                   LEFT JOIN suppliers s ON s.id = p.supplier_id
                   ORDER BY p.id DESC"""
            ).fetchall()

        if not rows:
            messagebox.showwarning("No Data", "No inventory records to export.")
            return

        df = pd.DataFrame([dict(r) for r in rows])
        out = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            filetypes=[("Excel Workbook", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not out:
            return
        try:
            if out.lower().endswith(".csv"):
                df.to_csv(out, index=False)
            else:
                df.to_excel(out, index=False)
            log_event("export", f"Inventory exported to {out}", self.current_user)
            messagebox.showinfo("Exported", f"Saved: {out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def smart_alerts(self):
        with connect() as conn:
            rows = conn.execute("SELECT name, quantity, expiry FROM products").fetchall()

        low = []
        expiring = []
        for r in rows:
            if int(r["quantity"]) <= self.low_stock_threshold:
                low.append(r["name"])
            expiry = r["expiry"]
            if not expiry:
                continue
            try:
                exp = datetime.strptime(str(expiry), "%Y-%m-%d")
                if (exp - datetime.now()).days <= 7:
                    expiring.append(r["name"])
            except Exception:
                continue

        if low or expiring:
            msg = []
            if low:
                msg.append("Low stock: " + ", ".join(low[:15]) + (" ..." if len(low) > 15 else ""))
            if expiring:
                msg.append("Expiring soon: " + ", ".join(expiring[:15]) + (" ..." if len(expiring) > 15 else ""))
            messagebox.showwarning("Smart Alerts", "\n".join(msg))
