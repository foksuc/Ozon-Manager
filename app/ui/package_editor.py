"""Shared Streamlit component declaration for the Ozon package editor.

This module deliberately contains no page-level Streamlit rendering. Keeping
component registration here prevents page modules from importing
``streamlit_app`` merely to access the shared component, which would execute
the app module a second time and duplicate widget IDs.
"""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_EDITOR_COMPONENT = components.declare_component(
    "ozon_package_editor",
    path=str(PROJECT_ROOT / "app" / "ui" / "components" / "ozon_package_editor"),
)
