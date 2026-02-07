from __future__ import annotations


def test_load_theme_returns_string():
    from grocery_mart_application import main

    theme = main._load_theme()
    assert isinstance(theme, str)
    assert theme


def test_theme_file_exists():
    from grocery_mart_application.main import DEFAULT_THEME_PATH

    assert DEFAULT_THEME_PATH.exists()
