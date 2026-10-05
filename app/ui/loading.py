"""Shared Ozon Manager loading overlay.

The overlay is presentation-only. The global CSS is defined by the main app
shell; this helper is shared by Stocks and Promotions so both screens use the
same loading interaction without importing the Streamlit app module.
"""
from __future__ import annotations

from contextlib import contextmanager
import streamlit as st


@contextmanager
def loading_overlay(title: str, message: str = "Выполняется проверка…"):
    slot = st.empty()

    def render(current: str) -> None:
        safe_title = str(title).replace("<", "&lt;").replace(">", "&gt;")
        safe_message = str(current).replace("<", "&lt;").replace(">", "&gt;")
        slot.markdown(
            f'''<div class="oz-loading-backdrop">
                <div class="oz-loading-modal" role="status" aria-live="polite">
                    <div class="oz-loading-spinner"></div>
                    <div class="oz-loading-title">{safe_title}</div>
                    <div class="oz-loading-message">{safe_message}</div>
                </div>
            </div>''',
            unsafe_allow_html=True,
        )

    render(message)
    try:
        yield render
    finally:
        slot.empty()
