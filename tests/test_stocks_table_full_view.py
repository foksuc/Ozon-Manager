from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCKS = ROOT / "app" / "ui" / "stocks.py"


def test_stocks_table_has_no_rows_per_page_or_page_number_pagination():
    source = STOCKS.read_text(encoding="utf-8")
    assert '"Строк на странице"' not in source
    assert '"Страница"' not in source
    assert "stocks_page_size" not in source
    assert "stocks_page_number" not in source
    assert "page_count" not in source
    assert "start = (int(page) - 1)" not in source


def test_stocks_passes_all_filtered_rows_to_shared_scrollable_table():
    source = STOCKS.read_text(encoding="utf-8")
    assert "display_rows = _normalize_rows(filtered, read_cache.names)" in source
    assert "height=520" in source
    assert 'key="stocks_table_component"' in source
