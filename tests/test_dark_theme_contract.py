from pathlib import Path
import tomllib

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / ".streamlit" / "config.toml"
UI = ROOT / "app" / "ui" / "streamlit_app.py"
COMP = ROOT / "app" / "ui" / "components" / "ozon_package_editor" / "index.html"
REQ = ROOT / "requirements.txt"


def test_dual_streamlit_theme_has_readable_explicit_dark_palette():
    data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    dark = data["theme"]["dark"]
    light = data["theme"]["light"]
    assert dark["primaryColor"].upper() == "#276EF1"
    assert dark["backgroundColor"].upper() == "#0B121A"
    assert dark["secondaryBackgroundColor"].upper() == "#141E29"
    assert dark["textColor"].upper() == "#F3F6FA"
    assert dark["borderColor"].upper() == "#304152"
    assert dark["dataframeHeaderBackgroundColor"].upper() == "#192634"
    assert light["backgroundColor"].upper() == "#F8FAFD"
    assert data["theme"]["dark"]["backgroundColor"] != data["theme"]["dark"]["secondaryBackgroundColor"]


def test_host_theme_bridge_uses_runtime_theme_and_no_black_fallback():
    source = UI.read_text(encoding="utf-8")
    assert "ACTIVE_THEME = st.context.theme.type" in source
    assert '"text": "#F3F6FA"' in source
    assert '"muted": "#A9B7C5"' in source
    assert ".stApp { color:var(--oz-text); }" not in source
    assert "--oz-text: var(--st-text-color" not in source
    assert '[data-baseweb="input"] > div,\n[data-baseweb="select"] > div' in source


def test_native_host_text_and_buttons_are_left_to_streamlit_theme():
    source = UI.read_text(encoding="utf-8")
    assert "Do not repaint the native Streamlit host" in source
    assert '[data-testid="stMarkdownContainer"]' not in source
    assert '[data-testid="stCaptionContainer"]' not in source
    assert '.stButton > button:not([kind="primary"])' not in source
    assert '.stButton > button:disabled' not in source
    assert '.oz-brand {' in source and 'color:inherit;' in source
    assert '.oz-page-title {' in source and 'color:inherit;' in source
    assert 'background:transparent;' in source  # no light strip behind the shutdown button


def test_custom_table_has_full_dark_surface_palette_and_no_transparent_body():
    html = COMP.read_text(encoding="utf-8")
    assert "r.setProperty('--oz-page',t.backgroundColor||'#0B121A')" in html
    assert "r.setProperty('--oz-surface',t.secondaryBackgroundColor||'#141E29')" in html
    assert "r.setProperty('--oz-header','#192634')" in html
    assert "r.setProperty('--oz-muted','#A9B7C5')" in html
    assert "r.setProperty('--oz-selected','#153A68')" in html
    assert "background:transparent;overflow:hidden" not in html
    assert "document.body.style.visibility='visible'" in html
    assert "accent-color:var(--oz-focus)" in html


def test_streamlit_version_supports_dual_light_dark_theme_configuration():
    req = REQ.read_text(encoding="utf-8")
    assert "streamlit>=1.51,<2" in req
