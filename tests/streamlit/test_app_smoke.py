"""Streamlit AppTest smoke checks.

These tests verify application-level startup and the high-level UI contract without
requiring a real browser. Browser E2E is intentionally not part of this project.
"""

import os
from pathlib import Path

import pytest

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # pragma: no cover - environment-dependent optional dependency
    AppTest = None

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app" / "ui" / "streamlit_app.py"


@pytest.mark.streamlit
@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed in the test environment")
def test_streamlit_app_boots_without_mock_mode():
    os.environ.pop("OZON_MOCK_MODE", None)
    at = AppTest.from_file(str(APP), default_timeout=15)
    at.run(timeout=15)

    assert any("Менеджер Ozon" in title.value for title in at.title)
    assert any("Акции" in button.label for button in at.button)
    assert not any("Mock mode" in checkbox.label for checkbox in at.checkbox)
