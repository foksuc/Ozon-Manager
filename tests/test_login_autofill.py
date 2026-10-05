from pathlib import Path


def test_client_id_is_visible_username_autofill_field():
    source = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"
    text = source.read_text(encoding="utf-8")
    assert '"Идентификатор клиента"' in text
    assert 'type="default"' in text
    assert 'autocomplete="username"' in text
    assert 'key="account_dialog_client_id"' in text
    assert 'Client ID", value=os.getenv("OZON_CLIENT_ID", ""), type="password"' not in text


def test_api_key_remains_password_current_password_autofill():
    source = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"
    text = source.read_text(encoding="utf-8")
    assert '"Ключ API"' in text
    assert 'type="password"' in text
    assert 'autocomplete="current-password"' in text
    assert 'key="account_dialog_api_key"' in text


def test_account_dialog_is_dispatched_before_sidebar_on_first_session():
    source = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"
    text = source.read_text(encoding="utf-8")
    startup = text.index('if st.session_state.get("startup_account_dialog_pending")')
    sidebar = text.index('with st.sidebar:')
    assert startup < sidebar
    assert '_render_account_dialog()' in text[startup:sidebar]
    assert 'st.session_state.startup_account_dialog_pending = False' in text[startup:sidebar]
    assert 'st.stop()' in text[startup:sidebar]
