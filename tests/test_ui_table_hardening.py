from pathlib import Path

ROOT = Path(__file__).parents[1]
UI = ROOT / "app" / "ui" / "streamlit_app.py"
COMP = ROOT / "app" / "ui" / "components" / "ozon_package_editor" / "index.html"


def test_filter_enter_uses_explicit_apply_path():
    s = COMP.read_text(encoding="utf-8")
    assert "function applyFilter()" in s
    assert "if(e.key==='Enter'){e.preventDefault();e.stopPropagation();applyFilter();return;}" in s
    assert "document.getElementById('filter-apply').click()" not in s


def test_selection_uses_local_optimistic_state_and_change_event():
    s = COMP.read_text(encoding="utf-8")
    assert "selectedIds:new Set()" in s
    assert "state.selectedIds=sel;state.pendingSelection=true;rememberScroll();emitSelection(sel);render();" in s
    assert "addEventListener('click'" in s
    assert "e.preventDefault();e.stopPropagation();toggle(tr.dataset.id,e.shiftKey)" in s


def test_add_dialog_keeps_only_top_discount_hint():
    s = UI.read_text(encoding="utf-8")
    assert s.count("Для каждого товара скидку можно изменить прямо в таблице двойным нажатием ЛКМ.") == 1


def test_new_price_is_displayed_as_whole_rubles():
    s = UI.read_text(encoding="utf-8")
    assert "def _display_whole_price" in s
    assert '"Новая цена": _display_whole_price(' in s
    assert "ROUND_HALF_UP" in s


def test_tables_use_content_width_layout():
    s = COMP.read_text(encoding="utf-8")
    assert "width:max-content" in s
    assert "table-layout:auto" in s


def test_table_component_does_not_use_viewport_max_height():
    from pathlib import Path
    html = Path("app/ui/components/ozon_package_editor/index.html").read_text(encoding="utf-8")
    assert "max-height:calc(100vh - 180px)" not in html
    assert "max-height:calc(100vh - 180px)" not in html
    assert "max-height:none" in html


def test_table_component_has_min_height_for_small_tables():
    from pathlib import Path
    html = Path("app/ui/components/ozon_package_editor/index.html").read_text(encoding="utf-8")
    assert "min-height:110px" in html
    assert "overflow:auto" in html


def test_selection_is_limited_to_first_column_and_cells_remain_copyable():
    s = COMP.read_text(encoding="utf-8")
    assert "tbody td{user-select:text;-webkit-user-select:text;cursor:text}" in s
    assert "let selectCell=tr.querySelector('.select-col')" in s
    assert "tr.addEventListener('click',e=>" not in s
    assert "selectCell.addEventListener('click'" in s

