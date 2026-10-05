from pathlib import Path
UI=Path(__file__).parents[1]/"app"/"ui"/"streamlit_app.py"
COMP=Path(__file__).parents[1]/"app"/"ui"/"components"/"ozon_package_editor"/"index.html"

def test_interactive_component_is_used_for_product_and_readonly_tables():
    s=UI.read_text(encoding="utf-8"); assert "def _product_table_component" in s; assert "def _interactive_readonly_table" in s; assert "selectable=True" in s

def test_sort_and_context_filter():
    s=COMP.read_text(encoding="utf-8"); assert "contextmenu" in s; assert "state.filters" in s; assert "state.sortIndex" in s; assert "localeCompare" in s

def test_shift_range_selection():
    s=COMP.read_text(encoding="utf-8"); assert "e.shiftKey" in s; assert "selected_ids" in s; assert "function toggle" in s

def test_hundredths_discount():
    s=COMP.read_text(encoding="utf-8"); assert "i.step='0.01'" in s; assert "toFixed(2)" in s

def test_legacy_text_removed():
    s=UI.read_text(encoding="utf-8"); assert "Что означает каждый столбец" not in s; assert "Закрыть таблицу: × вверху окна или Esc" not in s; assert "Elastic Boosting рассчитывается от «Цены»" not in s


def test_history_table_helper_is_defined_before_history_renderer():
    s = UI.read_text(encoding='utf-8')
    assert s.index('def _interactive_readonly_table') < s.index('def _render_history')


def test_header_sort_filter_and_shift_range_contract():
    s=COMP.read_text(encoding="utf-8")
    assert 'th[data-index]' in s
    assert "th.addEventListener('click'" in s
    assert "th.addEventListener('contextmenu'" in s
    assert "toggle(tr.dataset.id,e.shiftKey)" in s
    assert "e.preventDefault();e.stopPropagation();toggle(tr.dataset.id,e.shiftKey)" in s
    assert 'Shift+ЛКМ / Shift+ПКМ — диапазон' in s
    assert 'class="select-col select-all"' in s
    assert 'function rangeSelectTo(id)' in s
    assert "tr.addEventListener('contextmenu'" in s



def test_selection_message_is_emitted_before_rerender_and_sorted():
    s=COMP.read_text(encoding="utf-8")
    assert "function emitSelection(sel)" in s
    assert "emitSelection(sel);render();" in s
    assert "selected_ids:Array.from(sel).map(String).sort" in s
