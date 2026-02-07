"""
Compatibility entrypoint.

Use `python main.py` as the primary entrypoint. This file remains as a thin wrapper for older references.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Ensure the project directory is importable even when launched from a different CWD.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
