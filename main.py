from __future__ import annotations

import json
import sys
from pathlib import Path


THEME_PATH = Path(__file__).resolve().parent / "styles" / "theme.json"


def _load_theme() -> str:
    try:
        data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
        return str(data.get("theme", "flatly"))
    except Exception:
        return "flatly"


def main() -> int:
    try:
        import tkinter as tk
        from ttkbootstrap import Style
    except Exception as e:
        print("Missing UI dependency. Install with: pip install -r requirements.txt", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        from database import setup_database
        from dashboard import Dashboard
        from user_auth import LoginPage
    except Exception as e:
        print("App import failed.", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        plt = None

    class GroceryInventoryApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Grocery Mart Inventory Manager")
            self.geometry("1200x700")
            self.minsize(1000, 600)

            setup_database()

            self.style = Style(_load_theme())
            try:
                from utils.app_settings import get_setting

                scaling = float(get_setting("ui_scaling", 1.0) or 1.0)
                if 0.75 <= scaling <= 2.0:
                    self.tk.call("tk", "scaling", scaling)
            except Exception:
                pass
            self._current_user = None
            self._active_frame = None

            self.show_login()
            self.protocol("WM_DELETE_WINDOW", self.safe_exit)

        def _set_root_content(self, widget: tk.Widget) -> None:
            if self._active_frame is not None:
                self._active_frame.destroy()
            self._active_frame = widget
            self._active_frame.pack(fill=tk.BOTH, expand=True)

        def show_login(self) -> None:
            def on_success(user) -> None:
                self._current_user = user
                try:
                    from database import log_event as db_log

                    db_log("auth", "Login", user.username)
                except Exception:
                    pass
                self.show_dashboard()

            login = LoginPage(self, on_login_success=on_success)
            self._set_root_content(login)

        def show_dashboard(self) -> None:
            if not self._current_user:
                self.show_login()
                return
            dashboard = Dashboard(
                self, style=self.style, current_user=self._current_user.username, on_logout=self.logout
            )
            self._set_root_content(dashboard)

        def logout(self) -> None:
            if self._current_user:
                try:
                    from database import log_event as db_log

                    db_log("auth", "Logout", self._current_user.username)
                except Exception:
                    pass
            self._current_user = None
            self.show_login()

        def safe_exit(self):
            if plt is not None:
                try:
                    plt.close("all")
                except Exception:
                    pass
            try:
                self.quit()
                self.destroy()
            except Exception:
                pass
            sys.exit(0)

    app = GroceryInventoryApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

