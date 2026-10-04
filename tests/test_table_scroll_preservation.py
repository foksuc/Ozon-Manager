from pathlib import Path

HTML = Path("app/ui/components/ozon_package_editor/index.html").read_text(encoding="utf-8")


def test_table_scroll_position_is_preserved_across_rerender():
    assert "scrollTop:0" in HTML
    assert "scrollLeft:0" in HTML
    assert "function rememberScroll()" in HTML
    assert "function restoreScroll()" in HTML
    assert "state.scrollTop=w.scrollTop" in HTML
    assert "state.scrollLeft=w.scrollLeft" in HTML
    assert "w.scrollTop=state.scrollTop||0" in HTML
    assert "w.scrollLeft=state.scrollLeft||0" in HTML


def test_table_scroll_listener_is_bound_after_render():
    assert "w.addEventListener('scroll'" in HTML
    assert "{passive:true}" in HTML
