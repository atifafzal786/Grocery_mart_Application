# Contributing

Thanks for your interest in contributing!

## Development setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Install dev tools (optional but recommended):
   - `pip install -r requirements-dev.txt`
3. Run the app:
   - `python main.py`

Optional (camera barcode scanning):
- `pip install -r requirements-camera.txt`

## Code style

This repo uses:
- `ruff` for linting
- `black` for formatting
- `pytest` for tests

Run locally:
- `python -m ruff check .`
- `python -m black .`
- `python -m pytest -q`

## Pull requests

- Keep PRs focused and small when possible.
- Include screenshots/GIFs for UI changes.
- Add/update docs in `docs/` when behavior changes.
- Add tests for bug fixes when feasible.
