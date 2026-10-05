from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_runs_actual_streamlit_entrypoint():
    text = (ROOT / "START_OZON_MANAGER.bat").read_text(encoding="utf-8")
    assert r'app\ui\streamlit_app.py' in text
    assert r'app\main.py' not in text


def test_windows_launcher_waits_for_streamlit_before_opening_browser():
    text = (ROOT / "START_OZON_MANAGER.bat").read_text(encoding="utf-8")
    assert "Invoke-WebRequest" in text
    assert "http://127.0.0.1:8501/" in text
    assert 'start "" "http://127.0.0.1:8501/"' in text
