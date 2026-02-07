from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from ttkbootstrap import Button, Entry, Frame, Label, StringVar

from .auth_service import AuthUser, verify_credentials


LOGO_PATH = Path(__file__).resolve().parent / "logo" / "login_page_logo.png"
APP_BG_PATH = Path(__file__).resolve().parent / "logo" / "background_image.png"
LOGIN_BG_PATH = Path(__file__).resolve().parent / "Gemini_Generated_Image_m87t1hm87t1hm87t.png"


class LoginPage(Frame):
    def __init__(self, master, on_login_success):
        # Keep padding on the card, not the page, so the background can fill the window.
        super().__init__(master, padding=0)
        self.master = master
        self.on_login_success = on_login_success
        self.username = StringVar(value="admin")
        self.password = StringVar(value="")
        self._error_label: Label | None = None
        self._return_binding = None
        self._bg_canvas: tk.Canvas | None = None
        self._bg_photo = None
        self._logo_photo = None
        self._bg_after_id: str | None = None
        self._bg_src = None
        self._bg_image_id: int | None = None
        self._bg_last_size: tuple[int, int] | None = None
        self._bg_overlay_cache: dict[tuple[int, int], object] = {}
        self.build_ui()

    def build_ui(self) -> None:
        for child in list(self.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        # Background canvas (image + dark overlay)
        self._bg_last_size = None
        self._bg_overlay_cache.clear()
        self._bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._bg_canvas.configure(bg="#061423")
        # Use `place` to guarantee true edge-to-edge background (avoids any pack/padding quirks).
        self._bg_canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._bg_image_id = self._bg_canvas.create_image(0, 0, anchor="nw")

        # Center login card
        # Slight padding wrapper to mimic a "glass" card with border.
        card_border = tk.Frame(self._bg_canvas, bg="#1f2f41", bd=0, highlightthickness=0)
        card_border.place(relx=0.5, rely=0.5, anchor="center")
        card = tk.Frame(card_border, bg="#0b1b2b", bd=0, highlightthickness=0)
        card.pack(padx=2, pady=2)

        # Card content
        pad = tk.Frame(card, bg="#0b1b2b")
        pad.pack(padx=42, pady=32)

        self._load_logo()
        if self._logo_photo is not None:
            tk.Label(pad, image=self._logo_photo, bg="#0b1b2b").pack(pady=(0, 8))

        tk.Label(pad, text="GROCERY MART", font=("Helvetica", 16, "bold"), fg="#eaf2ff", bg="#0b1b2b").pack()
        tk.Label(pad, text="WELCOME BACK", font=("Helvetica", 22, "bold"), fg="#ffffff", bg="#0b1b2b").pack(
            pady=(12, 2)
        )
        tk.Label(pad, text="Login to continue", font=("Helvetica", 10), fg="#9bb0c8", bg="#0b1b2b").pack(
            pady=(0, 18)
        )

        self._error_label = Label(pad, text="", bootstyle="danger")
        self._error_label.pack(fill=tk.X, pady=(0, 10))
        self._error_label.pack_forget()

        fields = tk.Frame(pad, bg="#0b1b2b")
        fields.pack(fill=tk.X)

        def pill(parent: tk.Misc) -> tk.Frame:
            f = tk.Frame(parent, bg="#ffffff", highlightthickness=0, bd=0)
            return f

        user_pill = pill(fields)
        user_pill.pack(fill=tk.X, pady=(0, 12))
        user_entry = Entry(user_pill, textvariable=self.username, width=34)
        user_entry.pack(fill=tk.X, ipady=6, padx=12, pady=6)

        pw_pill = pill(fields)
        pw_pill.pack(fill=tk.X, pady=(0, 14))
        pw_row = tk.Frame(pw_pill, bg="#ffffff")
        pw_row.pack(fill=tk.X, padx=12, pady=6)
        pw_row.grid_columnconfigure(0, weight=1)

        show_pw = tk.BooleanVar(value=False)
        pass_entry = Entry(pw_row, show="*", textvariable=self.password)
        pass_entry.grid(row=0, column=0, sticky="ew", ipady=6)

        def toggle_pw() -> None:
            show_pw.set(not bool(show_pw.get()))
            try:
                pass_entry.configure(show="" if show_pw.get() else "*")
            except Exception:
                pass
            try:
                show_btn.configure(text="Hide" if show_pw.get() else "Show")
            except Exception:
                pass

        show_btn = Button(pw_row, text="Show", bootstyle="secondary-outline", width=7, command=toggle_pw)
        show_btn.grid(row=0, column=1, padx=(10, 0))

        actions = tk.Frame(pad, bg="#0b1b2b")
        actions.pack(fill=tk.X, pady=(0, 4))
        remember = tk.BooleanVar(value=True)
        tk.Checkbutton(
            actions,
            text="Remember me",
            variable=remember,
            bg="#0b1b2b",
            fg="#cfe0ff",
            activebackground="#0b1b2b",
            activeforeground="#cfe0ff",
            selectcolor="#0b1b2b",
            bd=0,
            highlightthickness=0,
        ).pack(side=tk.LEFT)

        def forgot() -> None:
            messagebox.showinfo("Forgot Password", "Ask an admin to reset your password from the Users database.")

        Button(actions, text="Forgot password?", bootstyle="link", command=forgot).pack(side=tk.RIGHT)

        btn = Button(pad, text="LOGIN", bootstyle="primary", command=self.check_login)
        btn.pack(fill=tk.X, ipady=6, pady=(10, 10))

        tk.Label(
            pad,
            text="Tip: Default login is admin / admin",
            font=("Helvetica", 9),
            fg="#9bb0c8",
            bg="#0b1b2b",
        ).pack()

        user_entry.focus_set()

        # Background rendering
        self._load_background_source()
        self._bg_canvas.bind("<Configure>", self._on_bg_configure)
        self._render_background()

        def on_return(_e=None) -> None:
            self.check_login()

        try:
            self._return_binding = self.master.bind("<Return>", on_return)
            self.bind("<Destroy>", lambda _e: self._unbind_return(), add=True)
        except Exception:
            pass

    def _load_logo(self) -> None:
        try:
            from PIL import Image, ImageTk  # type: ignore

            if LOGO_PATH.exists():
                img = Image.open(LOGO_PATH).convert("RGBA")
                # Scale up a bit for a more "app-like" header logo.
                # Keep aspect ratio to avoid distortion if the asset changes.
                max_dim = 84
                w, h = img.size
                if w > 0 and h > 0:
                    scale = max_dim / max(w, h)
                    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
        except Exception:
            self._logo_photo = None

    def _load_background_source(self) -> None:
        try:
            from PIL import Image  # type: ignore

            if APP_BG_PATH.exists():
                self._bg_src = Image.open(APP_BG_PATH).convert("RGB")
            elif LOGIN_BG_PATH.exists():
                self._bg_src = Image.open(LOGIN_BG_PATH).convert("RGB")
        except Exception:
            self._bg_src = None

    def _on_bg_configure(self, _e=None) -> None:
        if self._bg_after_id is not None:
            try:
                self.after_cancel(self._bg_after_id)
            except Exception:
                pass
            self._bg_after_id = None
        self._bg_after_id = self.after(110, self._render_background)

    def _get_bg_overlay(self, size: tuple[int, int]):
        cached = self._bg_overlay_cache.get(size)
        if cached is not None:
            return cached

        try:
            from PIL import Image  # type: ignore

            w, h = size
            # Base dark overlay + subtle vertical gradient to mimic a modern "hero" login.
            base = Image.new("RGBA", (w, h), (6, 20, 35, 165))
            mask = Image.new("L", (1, h))
            for y in range(h):
                # Slightly darker towards the bottom.
                mask.putpixel((0, y), int(55 * (y / max(1, h - 1))))
            mask = mask.resize((w, h))
            grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            grad.putalpha(mask)
            overlay = Image.alpha_composite(base, grad)
        except Exception:
            overlay = None

        self._bg_overlay_cache[size] = overlay
        # Keep cache small (login page only needs the last few sizes).
        if len(self._bg_overlay_cache) > 6:
            try:
                self._bg_overlay_cache.pop(next(iter(self._bg_overlay_cache)))
            except Exception:
                pass
        return overlay

    def _render_background(self) -> None:
        if self._bg_canvas is None:
            return
        w = max(1, int(self._bg_canvas.winfo_width()))
        h = max(1, int(self._bg_canvas.winfo_height()))

        if self._bg_last_size == (w, h):
            return
        self._bg_last_size = (w, h)

        try:
            from PIL import Image, ImageEnhance, ImageFilter, ImageTk  # type: ignore

            if self._bg_src is None:
                img = Image.new("RGB", (w, h), (6, 20, 35))
            else:
                # cover-fit
                src = self._bg_src
                scale = max(w / src.width, h / src.height)
                nw, nh = int(src.width * scale), int(src.height * scale)
                # Bilinear is noticeably faster and good enough for a blurred background.
                img = src.resize((nw, nh), Image.Resampling.BILINEAR)
                left = (nw - w) // 2
                top = (nh - h) // 2
                img = img.crop((left, top, left + w, top + h))

                # Speed: blur on a smaller image, then scale back up.
                sw, sh = max(1, w // 3), max(1, h // 3)
                small = img.resize((sw, sh), Image.Resampling.BILINEAR)
                small = small.filter(ImageFilter.GaussianBlur(radius=4))
                img = small.resize((w, h), Image.Resampling.LANCZOS)
                img = ImageEnhance.Brightness(img).enhance(0.72)
                img = ImageEnhance.Contrast(img).enhance(1.05)

            img_rgba = img.convert("RGBA")
            overlay = self._get_bg_overlay((w, h))
            if overlay is not None:
                img_rgba = Image.alpha_composite(img_rgba, overlay)

            self._bg_photo = ImageTk.PhotoImage(img_rgba)
            if self._bg_image_id is None:
                self._bg_image_id = self._bg_canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
            else:
                self._bg_canvas.itemconfigure(self._bg_image_id, image=self._bg_photo)
        except Exception:
            # Fallback to solid color if PIL is missing
            self._bg_canvas.configure(bg="#061423")

    def _unbind_return(self) -> None:
        try:
            self.master.unbind("<Return>", self._return_binding)
        except Exception:
            pass
        self._return_binding = None

    def _set_error(self, msg: str) -> None:
        if self._error_label is None:
            return
        try:
            self._error_label.configure(text=msg)
            # label is packed in the new layout
            self._error_label.pack(fill=tk.X, pady=(0, 10))
        except Exception:
            pass

    def check_login(self):
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self._set_error("Enter username and password.")
            return

        user: AuthUser | None = verify_credentials(username, password)
        if not user:
            self._set_error("Invalid credentials.")
            return

        if username == "admin" and password == "admin":
            messagebox.showwarning(
                "Default password",
                "You are using the default admin password.\n\nGo to Settings -> Change Password.",
            )
        self.on_login_success(user)
