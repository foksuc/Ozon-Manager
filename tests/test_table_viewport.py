from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "app" / "ui" / "components" / "ozon_package_editor" / "index.html"
STREAMLIT_APP = ROOT / "app" / "ui" / "streamlit_app.py"


def test_shared_table_uses_both_axis_scroll_and_fixed_frame_height():
    html = COMPONENT.read_text(encoding="utf-8")
    assert ".table-wrap" in html
    assert "overflow:auto" in html
    assert "height:calc(var(--oz-frame-height,520px) - 48px)" in html
    assert "send(HEIGHT,{height:frameHeight()})" in html
    assert "Math.max(110,Math.min(1400" not in html


def test_operational_table_defaults_are_compact_enough_for_actions():
    app = STREAMLIT_APP.read_text(encoding="utf-8")
    assert 'height: int = 520' in app
    assert 'height=520,\n        mode="package"' in app
    assert 'key=f"add_package_editor_{st.session_state.get(\'add_package_editor_version\', 0)}",\n        height=520,' in app
