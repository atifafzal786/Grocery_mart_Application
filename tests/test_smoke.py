from __future__ import annotations


def test_load_theme_returns_string():
    import main

    theme = main._load_theme()
    assert isinstance(theme, str)
    assert theme


def test_theme_file_exists():
    from pathlib import Path

    theme_path = Path(__file__).resolve().parents[1] / "styles" / "theme.json"
    assert theme_path.exists()

