from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
import os
from pathlib import Path
import subprocess
import sys

# Streamlit executes this file from app/ui, so explicitly expose the project root
# for the package-style imports below (from app....).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Always prefer the application source tree over a stale/installed package named
# ``app``. This is important for local Streamlit runs after an in-place update:
# otherwise Python can import an older OzonPromotionsAdapter that lacks newer
# mutation methods (for example delete_auto_add_products).
project_root_str = str(PROJECT_ROOT)
while project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

import streamlit as st

from app.infrastructure.logging import configure_logging

app_logger = configure_logging()
app_logger.info("Ozon Manager application started")

from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
from app.config import Settings
from app.repositories.sqlite import SQLiteRepository
from app.services.rollback import SafeRollbackService
from app.services.read_cache import ReadDataCache
from app.domain.state_machine import transition
from app.domain.models import OperationStatus, Promotion
from app.services.membership import AddProductsService, AddOperationReconciliationService, RemoveProductsService, UpdateParticipantPricesService
from app.services.auto_add import AutoAddDeleteService, AutoAddRollbackService
from app.services.price_engine import (
    calculate_candidate_elastic_price, calculate_elastic_boost_price, calculate_price, elastic_discount_bounds,
    validate_global_elastic_discount,
)
from app.services.workflow import (
    CandidateService, FreshCheckService, HistoryService, MutationService, OperationFactory,
    ParticipantService, ProductNameService, PreviewService, PromotionService, PromotionValidator, SnapshotService, VerificationService,
    merge_product_catalog,
)

from app.ui.display import calculate_auto_add_discount_percent, format_candidate_rows, format_participant_rows, format_auto_add_rows, format_money, format_number
from app.ui.stocks import render_stocks_page, show_stock_confirmation_dialog

from app.ui.package_editor import PACKAGE_EDITOR_COMPONENT

st.set_page_config(page_title="Менеджер Ozon", page_icon="assets/ozon_manager.png", layout="wide")

# Presentation-only theme bridge. Streamlit owns native widget theming, while
# project-owned HTML needs concrete palette values. Do not rely on undocumented
# CSS variables here: on some Streamlit versions they are absent in the host DOM
# and fallbacks can make dark-mode text black.
try:
    ACTIVE_THEME = st.context.theme.type
except Exception:
    ACTIVE_THEME = "light"

if ACTIVE_THEME == "dark":
    THEME = {
        "bg": "#0B121A",
        "surface": "#141E29",
        "surface_alt": "#192634",
        "text": "#F3F6FA",
        "muted": "#A9B7C5",
        "subtle": "#7F91A4",
        "primary": "#276EF1",
        "primary_soft": "#153A68",
        "border": "#304152",
        "border_soft": "#263645",
        "sidebar": "#0F1822",
    }
else:
    THEME = {
        "bg": "#F8FAFD",
        "surface": "#FFFFFF",
        "surface_alt": "#F3F6F9",
        "text": "#070707",
        "muted": "#667685",
        "subtle": "#768695",
        "primary": "#005BFF",
        "primary_soft": "#E7F1FF",
        "border": "#DCE4EC",
        "border_soft": "#E9EEF3",
        "sidebar": "#FFFFFF",
    }

# Ozon Seller visual language reference:
# Onest typography, cool-gray workspace, white/dark surfaces, restrained borders,
# Ozon blue primary action and compact navigation. Presentation only.
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&display=swap');
:root {{
  --oz-bg: {THEME['bg']};
  --oz-surface: {THEME['surface']};
  --oz-surface-alt: {THEME['surface_alt']};
  --oz-text: {THEME['text']};
  --oz-muted: {THEME['muted']};
  --oz-subtle: {THEME['subtle']};
  --oz-primary: {THEME['primary']};
  --oz-primary-soft: {THEME['primary_soft']};
  --oz-border: {THEME['border']};
  --oz-border-soft: {THEME['border_soft']};
  --oz-sidebar: {THEME['sidebar']};
  --oz-radius-card: 16px;
  --oz-radius-control: 8px;
  --oz-radius-dialog: 20px;
}}
html, body, [class*="stApp"] {{ font-family:Onest,Arial,Helvetica,sans-serif; }}
[data-testid="stToolbar"] {{ visibility:hidden; height:0; }}
.block-container {{ max-width:1216px; min-width:0; padding:1.5rem 24px 3rem; }}

/* Do not repaint the native Streamlit host. Its active theme owns page
   background, Markdown, headings, captions, labels, metrics and buttons. */

/* Sidebar */
[data-testid="stSidebar"] > div:first-child {{ padding-top:1rem; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap:.35rem; }}
[data-testid="stSidebar"] button {{
  border-radius:var(--oz-radius-control) !important;
  font-weight:600 !important;
  text-align:left !important;
  min-height:40px !important;
  transition:background-color .12s ease,color .12s ease,border-color .12s ease,opacity .12s ease;
}}
[data-testid="stSidebar"] button:hover {{ opacity:1; }}
[data-testid="stSidebar"] .st-key-sidebar_stop {{
  position:sticky; bottom:0; margin-top:24px; padding-top:12px; padding-bottom:4px; z-index:4;
  background:transparent;
}}
[data-testid="stSidebar"] .st-key-sidebar_stop button {{
  border-color:rgba(241,17,126,.42) !important;
}}
[data-testid="stSidebar"] .st-key-sidebar_stop button:hover {{
  border-color:rgba(241,17,126,.72) !important;
}}
[data-testid="stSidebar"] .stCheckbox {{ padding:4px 10px; }}
[data-testid="stSidebar"] .stCheckbox label {{ font-size:13px !important; }}

/* Project-owned typography inherits Streamlit's current foreground color,
   so switching Light/Dark never depends on private CSS variable names. */
.oz-brand {{ display:flex; align-items:center; gap:10px; padding:8px 10px 18px; font-size:21px; font-weight:700; letter-spacing:-.02em; color:inherit; }}
.oz-brand-mark {{ width:30px; height:30px; border-radius:9px; background:var(--oz-primary); display:grid; place-items:center; color:#fff; font-weight:700; font-size:15px; }}
.oz-page-title {{ font-size:30px; line-height:1.15; font-weight:700; letter-spacing:-.025em; margin:0 0 5px; color:inherit; }}
.oz-page-subtitle {{ color:inherit; opacity:.72; font-size:14px; margin:0 0 22px; }}

[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:var(--oz-radius-card) !important; }}
[role="dialog"] {{ border-radius:var(--oz-radius-dialog) !important; }}
.stButton > button {{ border-radius:var(--oz-radius-control); min-height:40px; font-family:inherit; font-weight:600; }}
.st-key-candidates_hub_button button,
.st-key-participants_hub_button button,
.st-key-auto_add_hub_button button {{ min-height:54px !important; justify-content:center !important; text-align:center !important; }}
.st-key-candidates_hub_button button p,
.st-key-participants_hub_button button p,
.st-key-auto_add_hub_button button p {{ width:100%; text-align:center !important; margin:0 !important; }}
[data-testid="stMetric"] {{ border-radius:var(--oz-radius-card); padding:14px 16px; }}
.stAlert {{ border-radius:10px; }}
[data-testid="stExpander"] {{ border-radius:10px !important; }}

/* Keep inputs/selects native; only normalize radius. */
[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] > div {{ border-radius:var(--oz-radius-control) !important; }}

/* Project-owned loading overlay. */
.oz-loading-backdrop {{ position:fixed; inset:0; z-index:999999; background:rgba(3,8,13,.62); backdrop-filter:blur(2px); display:flex; align-items:center; justify-content:center; pointer-events:all; }}
.oz-loading-modal {{ width:min(520px, calc(100vw - 40px)); padding:28px 30px; border-radius:var(--oz-radius-card); background:var(--oz-surface); color:var(--oz-text); border:1px solid var(--oz-border); box-shadow:0 24px 70px rgba(0,0,0,.42); text-align:center; }}
.oz-loading-spinner {{ width:38px; height:38px; margin:0 auto 16px; border:4px solid var(--oz-border); border-top-color:var(--oz-primary); border-radius:50%; animation:ozspin .8s linear infinite; }}
.oz-loading-title {{ font-size:18px; font-weight:700; color:var(--oz-text); margin-bottom:7px; }}
.oz-loading-message {{ color:var(--oz-muted); font-size:13px; line-height:1.5; }}
@keyframes ozspin {{ to {{ transform:rotate(360deg); }} }}
</style>
""", unsafe_allow_html=True)

st.title("Менеджер Ozon")

settings = Settings()
READ_CACHE_TTL_SECONDS = 60.0
FIXED_ACTION_ID = "1977747"
FIXED_ACTION_TITLE = "Эластичный бустинг. Без ограничения срока действия"

from app.ui.loading import loading_overlay

def _loading_overlay(title: str, message: str = "Выполняется проверка…"):
    """Backward-compatible alias for the shared loading overlay."""
    return loading_overlay(title, message)

if "ui_page" not in st.session_state:
    st.session_state.ui_page = "actions"

if "read_cache" not in st.session_state:
    st.session_state.read_cache = ReadDataCache()
read_cache: ReadDataCache = st.session_state.read_cache

# Credentials stay in Streamlit session state only. They are never written to the
# project database, operation history, logs, or other persistent project data.
if "ozon_client_id" not in st.session_state:
    st.session_state.ozon_client_id = os.getenv("OZON_CLIENT_ID", "")
if "ozon_api_key" not in st.session_state:
    st.session_state.ozon_api_key = os.getenv("OZON_API_KEY", "")

# Dialog widgets intentionally use separate keys from the canonical credential state.
# Streamlit forbids assigning to st.session_state.<widget_key> after that widget
# has been instantiated. Keeping dialog input keys separate lets the Save/Test
# actions safely copy values into the canonical session-state credentials.
if "account_dialog_client_id" not in st.session_state:
    st.session_state.account_dialog_client_id = st.session_state.get("ozon_client_id", "")
if "account_dialog_api_key" not in st.session_state:
    st.session_state.account_dialog_api_key = st.session_state.get("ozon_api_key", "")

# Show the Account dialog once automatically when a new Streamlit session starts.
# After the first render it is not reopened on ordinary reruns.
if "startup_account_dialog_pending" not in st.session_state:
    st.session_state.startup_account_dialog_pending = True


@st.dialog("Аккаунт")
def _render_account_dialog():
    st.caption("Данные аккаунта хранятся только в текущей сессии приложения.")
    dialog_client_id = st.text_input(
        "Идентификатор клиента",
        type="default",
        autocomplete="username",
        key="account_dialog_client_id",
    )
    dialog_api_key = st.text_input(
        "Ключ API",
        type="password",
        autocomplete="current-password",
        key="account_dialog_api_key",
    )
    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("Сохранить", type="primary", use_container_width=True):
            st.session_state.ozon_client_id = dialog_client_id.strip()
            st.session_state.ozon_api_key = dialog_api_key
            st.success("Данные аккаунта сохранены в текущей сессии.")
            st.rerun()
    with col_test:
        if st.button("Проверить подключение к Ozon", use_container_width=True):
            if not dialog_client_id.strip() or not dialog_api_key:
                st.error("Введите идентификатор клиента и ключ API.")
            else:
                try:
                    with _loading_overlay("Проверка подключения", "Проверяем идентификатор клиента, ключ API и доступ к Ozon…"):
                        test_adapter = OzonPromotionsAdapter(
                            OzonCredentials(dialog_client_id.strip(), dialog_api_key),
                            settings.ozon_base_url,
                            settings.ozon_timeout,
                        )
                        test_adapter.list_participants(FIXED_ACTION_ID)
                    st.session_state.ozon_client_id = dialog_client_id.strip()
                    st.session_state.ozon_api_key = dialog_api_key
                    st.success("Подключение к Ozon подтверждено.")
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    category = getattr(exc, "category", "Неизвестно")
                    if status is not None:
                        st.error(f"Не удалось подключиться к Ozon: HTTP {status}; категория={category}")
                    else:
                        st.error(f"Не удалось подключиться к Ozon: категория={category}; {type(exc).__name__}")

# Startup Account gate: open the credentials dialog before rendering the rest
# of the application when this is a new session without configured credentials.
# The flag is consumed before opening the dialog so Streamlit cannot schedule it
# repeatedly on ordinary reruns.
if st.session_state.get("startup_account_dialog_pending") and not (
    st.session_state.get("ozon_client_id", "").strip()
    and st.session_state.get("ozon_api_key", "")
):
    st.session_state.startup_account_dialog_pending = False
    _render_account_dialog()
    st.stop()

def _stop_ozon_manager() -> None:
    """Invoke the existing Windows STOP_OZON_MANAGER launcher without changing app logic."""
    stop_script = PROJECT_ROOT / "STOP_OZON_MANAGER.bat"
    if os.name != "nt" or not stop_script.exists():
        st.error("Выключение доступно через STOP_OZON_MANAGER.bat в Windows.")
        return
    subprocess.Popen(["cmd.exe", "/c", str(stop_script)], cwd=str(PROJECT_ROOT))


with st.sidebar:
    st.markdown('<div class="oz-brand"><span class="oz-brand-mark">O</span><span>Менеджер Ozon</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:var(--oz-border);margin:0 10px 10px"></div>', unsafe_allow_html=True)
    if st.button("👤 Аккаунт", use_container_width=True):
        _render_account_dialog()
    if st.button("🔄 Обновить данные", use_container_width=True):
        read_cache.clear()
        st.session_state.pop("auto_add_hidden_ids", None)
        st.session_state.pop("auto_add_source_key", None)
        st.session_state.pop("auto_add_rows_by_source", None)
        st.session_state.pop("auto_add_selected_action_id", None)
        st.session_state.pop("auto_add_selected_date", None)
        st.session_state.pop("selected_auto_add_ids", None)
        st.session_state.pop("stocks_rows", None)
        st.session_state.pop("stocks_plan", None)
        st.session_state.pop("stocks_edit_buffer", None)
        st.rerun()
    if st.button("🎯 Акции", use_container_width=True):
        st.session_state.ui_page = "actions"
        st.rerun()
    if st.button("📦 Остатки", use_container_width=True):
        st.session_state.ui_page = "stocks"
        st.rerun()
    if st.button("📜 История", use_container_width=True):
        st.session_state.ui_page = "history"
        st.rerun()
    with st.container(key="sidebar_stop"):
        if st.button("Выключить", use_container_width=True, key="sidebar_stop_manager"):
            _stop_ozon_manager()

client_id = st.session_state.get("ozon_client_id", "").strip()
api_key = st.session_state.get("ozon_api_key", "")

if not client_id or not api_key:
    # Локальная история не требует API-ключей.
    # Разделы, которым нужен Ozon API, остаются защищены до подключения аккаунта.
    adapter = None
else:
    credentials = OzonCredentials(client_id, api_key)
    adapter = OzonPromotionsAdapter(
        credentials,
        settings.ozon_base_url,
        settings.ozon_timeout,
    )


repo = SQLiteRepository(settings.database_path)
promotion_service = PromotionService(adapter)
participant_service = ParticipantService(adapter)
candidate_service = CandidateService(adapter)
product_name_service = ProductNameService(adapter)
preview_service = PreviewService()
fresh_service = FreshCheckService()
snapshot_service = SnapshotService(repo)
mutation_service = MutationService(adapter, repo, batch_size=settings.batch_size)
verification_service = VerificationService(adapter, repo)
history_service = HistoryService(repo)
rollback_service = SafeRollbackService(repo, participant_service, preview_service, fresh_service, snapshot_service, mutation_service, verification_service, promotion_service)

def _interactive_readonly_table(rows: list[dict], *, component_key: str, height: int = 520):
    """Render a read-only interactive table. Defined before History because
    Streamlit executes this module top-to-bottom on each rerun."""
    if not rows:
        return
    return PACKAGE_EDITOR_COMPONENT(
        rows=rows,
        selectable=False,
        selected_ids=[],
        mode="readonly",
        height=height,
        key=component_key,
        default=None,
    )


def _request_dialog(dialog_name: str):
    """Schedule exactly one dialog for the next Streamlit script run.

    This helper is defined before any page renderer can execute so that
    Streamlit's top-to-bottom module execution cannot hit a NameError when
    the History page requests the Auto-Add rollback dialog.
    """
    st.session_state["_pending_dialog"] = dialog_name


STATUS_LABELS = {
    "SUCCESS": "Успешно",
    "PARTIAL": "Частично",
    "FAILED": "Ошибка",
    "UNKNOWN_RESULT": "Результат неизвестен",
    "RUNNING": "Выполняется",
    "CONFIRMED": "Подтверждено",
    "SNAPSHOTTED": "Снимок создан",
    "VERIFICATION_FAILED": "Проверка не пройдена",
    "PENDING": "Ожидает",
}

def _status_ru(value) -> str:
    raw = str(value or "").upper()
    return STATUS_LABELS.get(raw, raw or "Неизвестно")

@st.dialog("История — Остатки", width="large")
def _show_stock_history_dialog():
    history = repo.list_stock_operations(limit=100)
    st.caption("Полная история операций с остатками, снимками состояния и результатами изменений.")
    if not history:
        st.info("Операций с остатками пока нет.")
        return
    history_rows = [{
        "Идентификатор операции": str(r["operation_id"]), "Время": r["created_at"],
        "Тип": _operation_type_ru(r["operation_type"]), "Статус": _status_ru(r["status"]),
        "Товар–склад": r["product_count"], "Успешно": r["success_count"],
        "Ошибки": r["failed_count"], "Снимок": r["snapshot_id"] or "—",
    } for r in history]
    _interactive_readonly_table(history_rows, component_key="history_stock_operations_table", height=420)
    selected_operation = st.selectbox("Детали операции", [str(r["operation_id"]) for r in history], key="history_stock_operation")
    selected = next((dict(r) for r in history if str(r["operation_id"]) == selected_operation), None)
    if selected:
        st.caption(f"Статус: {_status_ru(selected.get('status'))} · Снимок: {selected.get('snapshot_id') or '—'}")
        details = [dict(r) for r in repo.list_stock_operation_items(selected_operation)]
        if details:
            _interactive_readonly_table([{
                "Идентификатор товара": r["product_id"], "SKU": r["sku"] or "Неизвестно",
                "Склад": r["warehouse_name"] or r["warehouse_id"],
                "Было доступно": r["old_free_stock"], "Запрошено": r["requested_free_stock"],
                "Фактически": r["actual_free_stock"] if r["actual_free_stock"] is not None else "Неизвестно",
                "Статус": _status_ru(r["status"]), "Ошибка": r["error"] or "—",
            } for r in details], component_key="history_stock_operation_details", height=360)
        # Rollback is available only from a successfully completed operation.
        # Snapshot rows/failed/partial/unknown operations remain visible for audit,
        # but they are never presented as rollback sources.
        rollback_candidates = [
            dict(r) for r in history
            if r["status"] == "SUCCESS" and r["snapshot_id"]
        ]
        if rollback_candidates:
            rollback_options = {
                f"{r['operation_id']} — {r['created_at']} — снимок={r['snapshot_id']}": r
                for r in rollback_candidates
            }
            st.subheader("Откат")
            rollback_label = st.selectbox(
                "Успешная операция для отката",
                list(rollback_options),
                key="history_stock_rollback_operation",
            )
            if st.button(
                "Подготовить откат",
                type="secondary",
                use_container_width=True,
                key="history_stock_rollback",
            ):
                try:
                    from app.services.stocks import StockService
                    source = rollback_options[rollback_label]
                    with _loading_overlay(
                        "Подготовка отката",
                        "Читаем снимок, проверяем актуальность данных и создаём новый снимок…",
                    ):
                        rollback_plan = StockService(adapter, repo).prepare_rollback(str(source["snapshot_id"]))
                    st.session_state.stocks_plan = rollback_plan
                    st.session_state.stocks_plan_kind = "ROLLBACK"
                    st.session_state.history_modal = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Откат заблокирован: {type(exc).__name__}: {exc}")
        else:
            st.info("Откат доступен только для успешно завершённых операций с существующим снимком.")
        if selected.get("status") == "UNKNOWN_RESULT":
            st.warning("Результат этой операции неизвестен. Повторная отправка изменения запрещена.")


OPERATION_TYPE_LABELS = {
    "ADD_PRODUCTS": "Добавление товаров",
    "UPDATE_PRICE": "Обновление цены",
    "DELETE_PRODUCTS": "Удаление товаров из акции",
    "AUTO_ADD_DELETE": "Удаление из автодобавления",
    "ROLLBACK": "Откат",
}

def _operation_type_ru(value) -> str:
    raw = str(value or "")
    return OPERATION_TYPE_LABELS.get(raw, raw or "Неизвестно")

@st.dialog("История — Акции", width="large")
def _show_promotion_history_dialog():
    rows = repo.list_operations(limit=100)
    st.caption("Полная история операций с акциями, сверок, снимков состояния и откатов.")
    history_rows = [{
        "Идентификатор операции": str(r["operation_id"]),
        "Время": r["created_at"],
        "Тип": _operation_type_ru(r["operation_type"]),
        "Товаров": r["product_count"],
        "Успешно": r["success_count"],
        "Ошибок": r["failed_count"],
        "Статус": _status_ru(r["status"]),
        "Снимок": r["snapshot_id"] or "—",
    } for r in rows]
    _interactive_readonly_table(history_rows, component_key="history_promotion_operations_table", height=420)
    if not rows:
        st.info("Операций с акциями пока нет.")
        return
    unknown_options = {f"{r['operation_id']} — {_status_ru(r['status'])} — {_operation_type_ru(r['operation_type'])}": r for r in rows if r["operation_type"] == "ADD_PRODUCTS" and r["status"] == "VERIFICATION_FAILED"}
    if unknown_options:
        st.subheader("Сверка результата добавления")
        reconcile_label = st.selectbox("Операция для сверки", list(unknown_options), key="history_add_reconcile_operation")
        if adapter is None:
            st.info("Для сверки подключите Ozon API в боковой панели.")
        elif st.button("Проверить результат повторно", key="history_add_reconcile_button"):
            try:
                with _loading_overlay("Сверка результата", "Повторно проверяем фактическое состояние Ozon без повторного изменения…"):
                    message = AddOperationReconciliationService(adapter, repo).reconcile(unknown_options[reconcile_label]["operation_id"])
                read_cache.clear(); st.success(message); st.rerun()
            except Exception as exc:
                st.error(f"Сверка не выполнена: {exc}")
    auto_add_rollback_options = {f"{r['operation_id']} — {_status_ru(r['status'])} — снимок={r['snapshot_id']}": r for r in rows if r["operation_type"] == "AUTO_ADD_DELETE" and r["status"] == "SUCCESS" and r["snapshot_id"]}
    if auto_add_rollback_options:
        st.subheader("Откат автодобавления")
        aa_label = st.selectbox("Снимок автодобавления", list(auto_add_rollback_options), key="history_auto_add_rollback_snapshot_select")
        if st.button("Подготовить откат автодобавления", key="history_prepare_auto_add_rollback"):
            st.session_state.auto_add_rollback_snapshot_id = auto_add_rollback_options[aa_label]["snapshot_id"]
            st.session_state.history_modal = None
            _request_dialog("auto_add_rollback")
            st.rerun()
    rollback_options = {f"{r['operation_id']} — {_status_ru(r['status'])} — снимок={r['snapshot_id'] or 'нет'}": r for r in rows if r["snapshot_id"] and r["operation_type"] != "AUTO_ADD_DELETE"}
    if rollback_options:
        st.subheader("Безопасный откат")
        rb_label = st.selectbox("Снимок", list(rollback_options), key="history_promotion_rollback_snapshot")
        if adapter is None:
            st.info("Для отката подключите Ozon API в боковой панели.")
        elif st.button("Подготовить откат", key="history_promotion_prepare_rollback"):
            try:
                with _loading_overlay("Подготовка отката", "Выполняем предпросмотр и проверку актуальности перед откатом…"):
                    rb = rollback_service.prepare(rollback_options[rb_label]["snapshot_id"], "streamlit-session")
                st.session_state.rollback_operation = rb
                st.success("Предпросмотр, проверка актуальности и снимок для отката готовы. Требуется подтверждение.")
            except Exception as exc:
                st.error(str(exc))
        rb = st.session_state.get("rollback_operation")
        if rb:
            source_rows = {str(r["product_id"]): r for r in repo.get_snapshot(rb.source_snapshot_id)} if rb.source_snapshot_id else {}
            _interactive_readonly_table([{
                "Идентификатор товара": i.product_id,
                "Текущая цена": str(i.old_action_price),
                "Цена из снимка": str(i.requested_action_price),
                "Изменение": str(i.requested_action_price - i.old_action_price),
                "Текущий бустинг": str(i.old_current_boost) if i.old_current_boost is not None else "Неизвестно",
                "Бустинг из снимка": str(source_rows[i.product_id]["current_boost"]) if source_rows.get(i.product_id) and source_rows[i.product_id]["current_boost"] is not None else "Неизвестно",
                "Участие": source_rows[i.product_id]["membership"] if source_rows.get(i.product_id) else "Неизвестно",
                "Предупреждение": i.warning or "—",
            } for i in rb.items], component_key="history_promotion_rollback_preview")
            rb_confirm = st.checkbox("Я подтверждаю откат", key="history_promotion_rollback_confirm")
            if st.button("Подтвердить откат", disabled=not rb_confirm, key="history_promotion_rollback_execute"):
                try:
                    with _loading_overlay("Откат", "Создаём снимок, выполняем изменение и проверяем результат…"):
                        if rb.operation_type in {"ROLLBACK_ADD_REMOVE", "ROLLBACK_REMOVE_ADD"}:
                            # Membership rollback is the inverse operation, not an
                            # action_price=0 update.  The dedicated services repeat
                            # their own mandatory Fresh Check + snapshot immediately
                            # before the real mutation.
                            rollback_service.execute_membership_inverse(rb)
                        else:
                            mutation_service.confirm(rb, "streamlit-session"); mutation_service.execute(rb); verification_service.verify(rb); history_service.persist(rb)
                    st.success(f"Результат отката: {_status_ru(rb.status.value)}")
                    st.session_state.rollback_operation = None
                    read_cache.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Откат требует сверки: {exc}")


def _render_history():
    st.title("История")
    st.caption("Единый центр истории операций. Выберите раздел для просмотра всех данных.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Остатки", type="primary", use_container_width=True, key="history_open_stocks"):
            st.session_state.history_modal = "stocks"
            st.rerun()
    with c2:
        if st.button("Акции", use_container_width=True, key="history_open_promotions"):
            st.session_state.history_modal = "promotions"
            st.rerun()


@st.dialog("Откат автодобавления Ozon", width="large")
def show_auto_add_rollback_dialog():
    snapshot_id = st.session_state.get("auto_add_rollback_snapshot_id")
    if not snapshot_id:
        st.info("Снимок для отката не выбран.")
        return
    source_rows = repo.get_snapshot(snapshot_id)
    if not source_rows:
        st.error("Снимок не найден.")
        return
    st.warning(f"Откат восстановит {len(source_rows)} товаров в автодобавлении из снимка `{snapshot_id}`.")
    preview = [{
        "Идентификатор товара": str(row["product_id"]),
        "Дата автодобавления": str(row["auto_add_date"] or "Неизвестно"),
        "Цена автодобавления до удаления": str(row["action_price"]),
        "Текущее состояние": "отсутствует — будет восстановлено",
    } for row in source_rows]
    _interactive_readonly_table(preview, component_key="auto_add_rollback_preview_table", height=520)
    st.caption("Подготовка выполняет проверку актуальности без изменения данных. Непосредственно перед изменением выполняется повторная проверка и создаётся отдельный снимок исходного состояния.")
    confirm = st.checkbox("Я подтверждаю восстановление этих товаров в автодобавлении Ozon")
    if st.button("Восстановить в автодобавление Ozon", disabled=not confirm, type="primary", use_container_width=True):
        try:
            with _loading_overlay("Откат автодобавления", "Проверяем актуальность, создаём снимок, восстанавливаем данные и проверяем результат…"):
                service = AutoAddRollbackService(adapter, repo)
                operation = service.prepare(snapshot_id, "streamlit-session")
                operation, result = service.execute(operation, "streamlit-session")
            read_cache.clear()
            st.session_state.pop("auto_add_rollback_snapshot_id", None)
            if operation.status.value == "SUCCESS":
                st.success(f"Откат подтверждён: {len(result.active_product_ids)} товаров восстановлено.")
            elif operation.status.value == "PARTIAL":
                st.warning(f"Откат подтверждён частично: {operation.error_summary}")
            else:
                st.error(f"Откат требует сверки: {operation.error_summary or operation.status.value}")
            st.rerun()
        except Exception as exc:
            st.error(f"Откат заблокирован или не подтверждён: {exc}")



if st.session_state.ui_page == "history":
    _render_history()
    # Streamlit permits only one @st.dialog per script run. Consume a pending
    # dialog first; a requested Auto-Add rollback therefore suppresses the
    # underlying History modal for this run.
    pending_dialog = st.session_state.pop("_pending_dialog", None)
    if pending_dialog == "auto_add_rollback":
        show_auto_add_rollback_dialog()
    elif st.session_state.get("stocks_plan"):
        show_stock_confirmation_dialog(adapter, repo)
    elif st.session_state.get("history_modal") == "stocks":
        _show_stock_history_dialog()
    elif st.session_state.get("history_modal") == "promotions":
        _show_promotion_history_dialog()
    st.stop()

if st.session_state.ui_page == "stocks":
    render_stocks_page(adapter, repo, read_cache)
    st.stop()

# Candidates/Participants remain fixed to the single audited Elastic Boosting
# action.  The full /v1/actions response is still preserved because the
# Auto-Add hub below intentionally discovers every promotion that exposes
# Ozon-provided auto_add_dates.
if adapter is None:
    st.warning("Для раздела «Акции» подключите идентификатор клиента и ключ API в разделе «Аккаунт».")
    st.stop()

try:
    with _loading_overlay("Загрузка данных Ozon", "Получаем список акций и проверяем доступ к выбранной акции…"):
        promotions = adapter.list_promotions()
except Exception as exc:
    st.error(f"Не удалось получить данные акции из Ozon: {type(exc).__name__}: {exc}")
    st.stop()

promotion = next((p for p in promotions if str(p.action_id) == FIXED_ACTION_ID), None)
if promotion is None:
    st.error(f"Ozon не вернул аудированную акцию {FIXED_ACTION_ID} в /v1/actions.")
    st.stop()

# Preserve the API-provided metadata. Do not synthesize or hard-code
# auto_add_dates: absence in the actual /v1/actions response remains UNKNOWN.
PromotionValidator.ensure_elastic_promotion(promotion)


if not read_cache.has_action_data(promotion.action_id, READ_CACHE_TTL_SECONDS):
    try:
        with _loading_overlay("Загрузка товаров", "Получаем участников и кандидатов из Ozon…"):
            participants = participant_service.load(promotion.action_id)
            candidate_rows = candidate_service.load(promotion.action_id)
    except Exception as exc:
        st.error(f"Не удалось загрузить участников: {exc}")
        st.stop()

    read_cache.mark_action(promotion.action_id, participants, candidate_rows)
else:
    participants = read_cache.participants or []
    candidate_rows = read_cache.candidate_rows or []

# Auto-Add is deliberately decoupled from the single audited Elastic Boosting
# action used by Candidates/Participants. Ozon /v1/actions exposes
# ``auto_add_dates`` per promotion, and the existing Auto-Add adapter/service
# accepts action_id + the exact Ozon-provided date. The UI therefore discovers
# every promotion with Auto-Add metadata and reuses the same read/delete
# workflow without changing the mutation implementation.
def _promotion_auto_add_dates(item: Promotion) -> list[str]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    values = metadata.get("auto_add_dates")
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


auto_add_promotions: list[tuple[Promotion, list[str]]] = []
for _promotion_item in promotions:
    _dates = _promotion_auto_add_dates(_promotion_item)
    if _dates:
        auto_add_promotions.append((_promotion_item, _dates))
auto_add_promotions.sort(key=lambda pair: ((pair[0].title or "").casefold(), str(pair[0].action_id)))


def _auto_add_ui_cache_key(action_id: str, auto_add_date: str) -> str:
    return f"{str(action_id)}::{str(auto_add_date)}"


def _load_auto_add_rows_for(action_id: str, auto_add_date: str) -> list[dict]:
    cache = dict(st.session_state.get("auto_add_rows_by_source", {}))
    cache_key = _auto_add_ui_cache_key(action_id, auto_add_date)
    if cache_key not in cache:
        with _loading_overlay("Загрузка автодобавления", "Получаем актуальное состояние автодобавления выбранной акции из Ozon…"):
            cache[cache_key] = adapter.list_auto_add_products(
                str(action_id),
                auto_add_date=str(auto_add_date),
                limit=100,
            )
        st.session_state.auto_add_rows_by_source = cache
    return [dict(row) for row in cache.get(cache_key, [])]


def _invalidate_auto_add_ui_cache(action_id: str, auto_add_date: str) -> None:
    cache = dict(st.session_state.get("auto_add_rows_by_source", {}))
    cache.pop(_auto_add_ui_cache_key(action_id, auto_add_date), None)
    st.session_state.auto_add_rows_by_source = cache


if not participants:
    st.warning("В выбранной акции сейчас 0 участников. Операции с участниками недоступны.")


# Resolve only Product IDs that are not already known in this Streamlit session.
product_ids = {
    str(row.get("id", row.get("product_id", "")))
    for row in candidate_rows
    if row.get("id", row.get("product_id")) not in (None, "")
}
product_ids.update(str(product.product_id) for product in participants)
missing_card_ids = sorted(product_ids - set(read_cache.skus) - read_cache.sku_misses)
if missing_card_ids:
    try:
        with _loading_overlay("Загрузка карточек", f"Получаем SKU и названия для {len(missing_card_ids)} товаров…"):
            resolved_cards = adapter.resolve_product_cards(missing_card_ids)
        for pid, card in resolved_cards.items():
            if card.get("name"):
                read_cache.names[pid] = str(card["name"])
            if card.get("sku"):
                read_cache.skus[pid] = str(card["sku"])
        read_cache.name_misses.update(set(missing_card_ids) - set(read_cache.names))
        read_cache.sku_misses.update(set(missing_card_ids) - set(read_cache.skus))
    except Exception as exc:
        # Keep the existing name lookup as a compatibility fallback. SKU is
        # intentionally marked UNKNOWN if the card lookup cannot be completed.
        try:
            with _loading_overlay("Резервная загрузка названий", "Получаем названия товаров через резервный Ozon API метод…"):
                resolved = adapter.resolve_product_names(missing_card_ids)
                read_cache.names.update(resolved)
        except Exception:
            pass
        read_cache.name_misses.update(set(missing_card_ids) - set(read_cache.names))
        read_cache.sku_misses.update(set(missing_card_ids) - set(read_cache.skus))
        st.warning(f"Не удалось получить SKU/названия новых товаров через OzonAPI: {type(exc).__name__}.")

enriched_candidates = []
for row in candidate_rows:
    copy = dict(row)
    pid = str(copy.get("id", copy.get("product_id", "")))
    if not copy.get("name"):
        copy["name"] = read_cache.names.get(pid)
    enriched_candidates.append(copy)
candidate_rows = enriched_candidates
participants = [
    replace(product, name=read_cache.names.get(str(product.product_id), product.name))
    for product in participants
]

resolved_names = {pid: read_cache.names[pid] for pid in product_ids if pid in read_cache.names}
resolved_skus = {pid: read_cache.skus[pid] for pid in product_ids if pid in read_cache.skus}
current_time = __import__("datetime").datetime.now().strftime("%H:%M")
st.caption(
    f"Данные API: сохранены в текущей сессии · обновлено: {current_time}. "
    "Для принудительного обновления используйте «🔄 Обновить данные»."
)
if len(resolved_names) < len(product_ids):
    st.warning(f"Для {len(product_ids) - len(resolved_names)} товаров Ozon не вернул название. В таблице будет «Неизвестно».")
if len(resolved_skus) < len(product_ids):
    st.warning(f"Для {len(product_ids) - len(resolved_skus)} товаров Ozon не вернул SKU. В таблице будет «Неизвестно».")

candidate_by_id = {}
for row in candidate_rows:
    pid = str(row.get("id", row.get("product_id", "")))
    if pid:
        candidate_by_id[pid] = row
participant_by_id = {str(p.product_id): p for p in participants}


def _money_decimal(row: dict, key: str) -> Decimal | None:
    raw = row.get(key)
    try:
        value = Decimal(str(raw.get("amount") if isinstance(raw, dict) else raw))
        return value if value > 0 else None
    except Exception:
        return None


def _candidate_price(row: dict) -> Decimal:
    value = _money_decimal(row, "price")
    if value is None:
        raise ValueError(f"Идентификатор товара {row.get('id', row.get('product_id'))}: отсутствует положительная Цена для расчёта")
    return value


def _candidate_max_action_price(row: dict) -> Decimal | None:
    return _money_decimal(row, "max_action_price")


def _participant_price(product) -> Decimal:
    if product.price is None:
        raise ValueError(f"Идентификатор товара {product.product_id}: отсутствует Цена для расчёта")
    return Decimal(str(product.price))


def _candidate_minimum_discount(row: dict) -> Decimal:
    """Return the minimum Ozon-derived Elastic discount used by ADD preview.

    This is presentation-side selection only.  It reuses the same price
    thresholds as the existing ADD price planner and does not mutate Ozon.
    """
    minimum, _maximum = elastic_discount_bounds(
        _candidate_price(row),
        _money_decimal(row, "price_min_elastic"),
        _money_decimal(row, "price_max_elastic"),
    )
    return minimum


def _participant_discount_percent(product) -> Decimal | None:
    """Return the participant's current action discount for UI filtering."""
    try:
        price = Decimal(str(product.price))
        action_price = Decimal(str(product.action_price))
        if price <= 0 or action_price < 0:
            return None
        return (price - action_price) / price * Decimal("100")
    except Exception:
        return None


def _display_whole_price(value) -> str:
    """Display a calculated action price as whole RUB in UI tables."""
    try:
        return str(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return str(value)


def _display_id_for_product(product_id: str) -> str:
    """Show Ozon SKU in the table where the user needs a card-search identifier."""
    return read_cache.skus.get(str(product_id), "Неизвестно")


def _table_rows_with_selection(rows: list[dict], state_key: str, *, value_columns: list[str], display_id_to_product_id: dict[str, str] | None = None) -> list[dict]:
    """Return the complete table with a dedicated selection checkbox column.

    Deliberately no pagination: the table dialog is the user's complete view of
    the API result. This is important for actions such as selecting any of the
    892+ candidates rather than silently limiting the working set to page 1.
    """
    selected = set(st.session_state.get(state_key, []))
    result = []
    for row in rows:
        display_id = str(row.get("SKU", row.get("Идентификатор товара", "")))
        internal_id = display_id_to_product_id.get(display_id, display_id) if display_id_to_product_id else display_id
        item = {"Выбрать": internal_id in selected}
        item.update(row)
        result.append(item)
    return result


def _selected_from_table(edited_rows: list[dict], state_key: str, display_id_to_product_id: dict[str, str] | None = None) -> list[str]:
    selected = set()
    for row in edited_rows:
        if row.get("Выбрать"):
            display_id = str(row.get("SKU", row.get("Идентификатор товара", ""))).strip()
            pid = display_id_to_product_id.get(display_id, display_id) if display_id_to_product_id else display_id
            if pid:
                selected.add(pid)
    st.session_state[state_key] = sorted(selected)
    return sorted(selected)


def _product_table_component(rows: list[dict], *, component_key: str, selected_ids: list[str] | None = None, selectable: bool = True, height: int = 520, mode: str = "selection", allow_remove: bool = False):
    return PACKAGE_EDITOR_COMPONENT(rows=rows, selectable=selectable, selected_ids=[str(x) for x in (selected_ids or [])], mode=mode, allow_remove=allow_remove, height=height, key=component_key, default=None)


def _candidate_editor() -> list[str]:
    rows = format_candidate_rows(candidate_rows, sku_map=read_cache.skus)
    # Product ID is the authoritative row identity.  Never reconstruct it
    # from the displayed SKU: SKUs are presentation data and can be missing,
    # duplicated, or stale in the local cache.
    for display_row, source_row in zip(rows, candidate_rows):
        pid = source_row.get("id", source_row.get("product_id"))
        display_row["__id"] = str(pid) if pid not in (None, "") else ""
    if not rows:
        st.info("Нет товаров.")
        return []
    result = _product_table_component(rows, component_key=f"candidate_selection_editor_{st.session_state.get('candidate_table_version', 0)}", selected_ids=st.session_state.get("selected_candidate_ids", []), selectable=True)
    if isinstance(result, dict) and result.get("action") == "selection":
        selected = [str(x) for x in result.get("selected_ids", [])]
        st.session_state.selected_candidate_ids = selected
        return selected
    return [str(x) for x in st.session_state.get("selected_candidate_ids", [])]


def _participant_editor() -> list[str]:
    rows = format_participant_rows(participants, sku_map=read_cache.skus)
    for row, product in zip(rows, participants):
        row["__id"] = str(product.product_id)
    if not rows:
        st.info("Нет товаров.")
        return []
    result = _product_table_component(rows, component_key=f"participant_selection_editor_{st.session_state.get('participant_table_version', 0)}", selected_ids=st.session_state.get("selected_participant_ids", []), selectable=True)
    if isinstance(result, dict) and result.get("action") == "selection":
        selected = [str(x) for x in result.get("selected_ids", [])]
        st.session_state.selected_participant_ids = selected
        return selected
    return [str(x) for x in st.session_state.get("selected_participant_ids", [])]



def _auto_add_editor(rows_source: list[dict], *, source_key: str) -> list[str]:
    rows = format_auto_add_rows(rows_source)
    for row, source in zip(rows, rows_source):
        row["__id"] = str(source.get("product_id", ""))
    if not rows:
        st.info("Нет товаров автодобавления.")
        return []
    result = _product_table_component(
        rows,
        component_key=(
            f"auto_add_selection_editor_{source_key}_"
            f"{st.session_state.get('auto_add_table_version', 0)}"
        ),
        selected_ids=st.session_state.get("selected_auto_add_ids", []),
        selectable=True,
        mode="readonly",
    )
    if isinstance(result, dict) and result.get("action") == "selection":
        selected = [str(x) for x in result.get("selected_ids", [])]
        st.session_state.selected_auto_add_ids = selected
        return selected
    return [str(x) for x in st.session_state.get("selected_auto_add_ids", [])]


@st.dialog("Автодобавление Ozon", width="large")
def show_auto_add_dialog():
    selected_action_id = str(st.session_state.get("auto_add_selected_action_id", "") or "")
    selected_entry = next(
        ((item, dates) for item, dates in auto_add_promotions if str(item.action_id) == selected_action_id),
        None,
    )

    # Hub view: every action for which Ozon actually returned auto_add_dates.
    # Action buttons are intentionally laid out in two columns. No product
    # count is shown here, so opening the hub does not fan out read requests
    # across every promotion.
    if selected_entry is None:
        st.caption(
            "Все акции, для которых Ozon вернул даты автодобавления. "
            "Выберите акцию — товары будут загружены только для неё."
        )
        if not auto_add_promotions:
            st.info("Ozon не вернул акции с доступным автодобавлением.")
            return

        hub_columns = st.columns(2)
        for index, (item, dates) in enumerate(auto_add_promotions):
            with hub_columns[index % 2]:
                with st.container(border=True):
                    action_title = item.title.strip() if item.title else f"Акция {item.action_id}"
                    if st.button(
                        action_title,
                        key=f"auto_add_open_action_{item.action_id}",
                        use_container_width=True,
                    ):
                        st.session_state.auto_add_selected_action_id = str(item.action_id)
                        st.session_state.auto_add_selected_date = str(dates[0])
                        st.session_state.selected_auto_add_ids = []
                        st.session_state.auto_add_table_version = st.session_state.get("auto_add_table_version", 0) + 1
                        _request_dialog("auto_add_hub")
                        st.rerun()
                    st.caption(
                        f"ID акции: {item.action_id} · "
                        f"дат автодобавления: {len(dates)}"
                    )
        return

    selected_promotion, available_dates = selected_entry

    nav_col, title_col = st.columns([0.24, 0.76], vertical_alignment="center")
    with nav_col:
        if st.button("← Все акции", key="auto_add_back_to_hub", use_container_width=True):
            st.session_state.pop("auto_add_selected_action_id", None)
            st.session_state.pop("auto_add_selected_date", None)
            st.session_state.selected_auto_add_ids = []
            _request_dialog("auto_add_hub")
            st.rerun()
    with title_col:
        action_heading = selected_promotion.title or f"Акция {selected_promotion.action_id}"
        st.markdown(f"**{action_heading}**")
        st.caption(f"ID акции: {selected_promotion.action_id}")

    preferred_date = str(st.session_state.get("auto_add_selected_date", "") or "")
    if preferred_date not in available_dates:
        preferred_date = str(available_dates[0])
    if len(available_dates) > 1:
        selected_date = st.selectbox(
            "Дата автодобавления Ozon",
            available_dates,
            index=available_dates.index(preferred_date),
            key=f"auto_add_date_selector_{selected_promotion.action_id}",
        )
    else:
        selected_date = preferred_date
        st.caption(f"Дата автодобавления Ozon: {selected_date}")

    previous_source_key = str(st.session_state.get("auto_add_source_key", "") or "")
    source_key = _auto_add_ui_cache_key(selected_promotion.action_id, selected_date)
    if previous_source_key != source_key:
        st.session_state.auto_add_source_key = source_key
        st.session_state.auto_add_selected_date = selected_date
        st.session_state.selected_auto_add_ids = []
        st.session_state.auto_add_table_version = st.session_state.get("auto_add_table_version", 0) + 1

    try:
        auto_add_rows = _load_auto_add_rows_for(selected_promotion.action_id, selected_date)
    except Exception as exc:
        st.error(f"Не удалось загрузить автодобавление Ozon: {type(exc).__name__}: {exc}")
        return

    last_result = st.session_state.pop("auto_add_last_result", None)
    if last_result:
        st.success(str(last_result))

    st.caption(f"Товаров в автодобавлении: {len(auto_add_rows)}")

    with st.container(border=True):
        control_col, button_col = st.columns([1, 1.35], vertical_alignment="bottom")
        with control_col:
            discount_threshold_text = st.text_input(
                "Удалить из автодобавления товары со скидкой больше, %",
                value="5.00",
                key=f"auto_add_discount_threshold_{selected_promotion.action_id}_{selected_date}",
                autocomplete="off",
            )
        with button_col:
            if st.button(
                "Подготовить удаление товаров со скидкой выше N%",
                disabled=not auto_add_rows,
                use_container_width=True,
                key=f"auto_add_prepare_delete_{selected_promotion.action_id}_{selected_date}",
            ):
                try:
                    threshold = Decimal(str(discount_threshold_text).strip().replace(",", "."))
                except Exception:
                    st.error("Введите корректное числовое значение скидки.")
                    st.stop()
                if not threshold.is_finite():
                    st.error("Введите конечное числовое значение скидки.")
                    st.stop()

                to_delete = []
                for source in auto_add_rows:
                    discount = calculate_auto_add_discount_percent(source)
                    if discount is not None and discount > threshold:
                        to_delete.append(source)
                if not to_delete:
                    st.info("Товаров со скидкой выше указанного порога нет.")
                else:
                    st.session_state.auto_add_delete_plan = {
                        "action_id": str(selected_promotion.action_id),
                        "action_title": selected_promotion.title or f"Акция {selected_promotion.action_id}",
                        "auto_add_date": str(selected_date),
                        "threshold": str(threshold),
                        "rows": {str(r.get("product_id")): dict(r) for r in to_delete},
                    }
                    _request_dialog("auto_add_delete")
                    st.rerun()
        st.caption(
            "Кнопка только готовит пакет удаления. Перед mutation выполняются "
            "предпросмотр, Fresh Check, снимок состояния и отдельное подтверждение."
        )

    selected = _auto_add_editor(auto_add_rows, source_key=source_key.replace(":", "_"))
    st.caption(f"Выбрано: {len(selected)}")
    st.info(
        "Функциональность таблицы и безопасный workflow удаления совпадают с "
        "ранее реализованным автодобавлением; меняется только выбранная акция."
    )


candidate_dialog_help = [
    ("SKU", "SKU Ozon — идентификатор, который можно использовать для поиска карточки товара на Ozon."),
    ("Название", "Название товара."),
    ("Цена", "Текущая цена товара. Именно от этой цены рассчитывается Elastic Boosting."),
    ("Минимальная цена бустинга", "Минимальная скидка, рассчитанная от текущей Цены до Ozon минимальная цена бустинга; справа показывается целевая цена. Для ADD это нижняя граница допустимой скидки."),
    ("Максимальная цена бустинга", "Максимальная скидка, рассчитанная от текущей Цены до Ozon максимальная цена бустинга; справа показывается целевая цена. Для ADD это верхняя граница допустимой скидки."),
    ("Ограничение для акций", "Значение max_action_price, возвращённое Ozon. Показывается информативно и не используется как нижний порог расчёта."),
    ("Ошибка ограничения цены акции", "Флаг предупреждения/ошибки max action price, возвращённый Ozon."),
    ("Предупреждение по цене акции", "Значение предупреждения max action price, возвращённое Ozon."),
]

participant_dialog_help = [
    ("SKU", "SKU Ozon — идентификатор, который можно использовать для поиска карточки товара на Ozon."),
    ("Название", "Название товара."),
    ("Цена", "Цена товара до применения скидки акции."),
    ("Минимальная цена бустинга", "Значение минимальная цена бустинга, фактически возвращённое Ozon. Используется для информирования и проверку актуальности, но не превращается в самодельное правило блокировки."),
    ("Максимальная цена бустинга", "Значение максимальная цена бустинга, фактически возвращённое Ozon."),
    ("Ограничение для акции", "Значение max_action_price, возвращённое Ozon."),
    ("Скидка", "Итоговая скидка: разница между Ценой и текущей ценой внутри акции, в процентах."),
]


@st.dialog("Удаление из автодобавления Ozon", width="large")
def show_auto_add_delete_dialog():
    plan = st.session_state.get("auto_add_delete_plan")
    if not plan:
        st.info("План удаления отсутствует.")
        return
    rows = plan["rows"]
    threshold = Decimal(str(plan["threshold"]))
    st.warning(
        f"Будет удалено из автодобавления Ozon: {len(rows)} товаров. "
        f"Акция: {plan.get('action_title') or plan['action_id']} · "
        f"порог: скидка > {threshold}% · дата: {plan['auto_add_date']}"
    )
    preview = []
    for row in rows.values():
        preview.append({
            "Идентификатор товара": str(row.get("product_id", "")),
            "SKU": str(row.get("sku", "")),
            "Название": row.get("name") or "Неизвестно",
            "Цена": str(row.get("price", "")),
            "Цена автодобавления": str(row.get("action_price_to_auto_add", "")),
            "Скидка": format_auto_add_rows([row])[0].get("Скидка", "Неизвестно"),
        })
    _interactive_readonly_table(preview, component_key="auto_add_delete_preview_table", height=520)
    st.caption("Непосредственно перед изменением проверка актуальности сравнит текущие данные Ozon с предпросмотром. Если цена или цена автодобавления изменились, удаление будет заблокировано.")
    confirm = st.checkbox("Я подтверждаю удаление этих товаров из автодобавления Ozon")
    if st.button("Удалить из автодобавления Ozon", disabled=not confirm, type="primary", use_container_width=True):
        try:
            with _loading_overlay("Удаление из автодобавления", "Проверяем актуальные данные, создаём снимок и выполняем изменение…"):
                service = AutoAddDeleteService(adapter, repo)
                operation = service.build_operation(
                    plan["action_id"],
                    plan["auto_add_date"],
                    list(rows.values()),
                    threshold,
                    "streamlit-session",
                )
                operation, result = service.execute(
                    operation,
                    plan["auto_add_date"],
                    rows,
                    "streamlit-session",
                )
            read_cache.clear()
            _invalidate_auto_add_ui_cache(plan["action_id"], plan["auto_add_date"])
            st.session_state.auto_add_selected_action_id = str(plan["action_id"])
            st.session_state.auto_add_selected_date = str(plan["auto_add_date"])
            st.session_state.selected_auto_add_ids = []
            st.session_state.auto_add_last_result = (
                f"Изменение автодобавления завершено: {len(result.deactivated_product_ids)} "
                f"подтверждено Ozon; статус операции: {operation.status.value}."
            )
            st.session_state.pop("auto_add_delete_plan", None)
            _request_dialog("auto_add_hub")
            st.rerun()
        except Exception as exc:
            st.error(f"Удаление из автодобавления заблокировано или не подтверждено: {exc}")


@st.dialog("Кандидаты", width="large")
def show_candidates_dialog():
    st.caption(f"Всего кандидатов: {len(candidate_rows)}")
    bulk_threshold = st.number_input(
        "Добавить все товары с минимальной скидкой меньше, %",
        value=5.0, step=0.01,
        key="candidate_bulk_discount_threshold",
        help="Сравнивается минимальная скидка Elastic Boosting, рассчитанная из текущей цены и price_min_elastic. Само добавление проходит обычный безопасный workflow.",
    )
    if st.button(f"Добавить все товары со скидкой меньше {bulk_threshold:g}%", use_container_width=True, key="candidate_bulk_add_below_threshold"):
        threshold = Decimal(str(bulk_threshold))
        bulk_ids: list[str] = []
        skipped = 0
        for row in candidate_rows:
            pid = str(row.get("id", row.get("product_id", "")))
            if not pid:
                continue
            try:
                if _candidate_minimum_discount(row) < threshold:
                    bulk_ids.append(pid)
            except Exception:
                skipped += 1
        if bulk_ids:
            st.session_state.selected_candidate_ids = sorted(set(bulk_ids))
            st.session_state.add_selected_ids = sorted(set(bulk_ids))
            _request_dialog("add_price")
            st.rerun()
        else:
            suffix = f" Не удалось рассчитать скидку для {skipped} товаров." if skipped else ""
            st.info(f"Кандидатов с минимальной скидкой меньше {threshold}% нет.{suffix}")
    st.caption("Массовая кнопка только формирует пакет. Preview, проверка цен, Fresh Check, Snapshot и подтверждение остаются в существующем процессе добавления.")

    selected = _candidate_editor()
    if st.button("Добавить товары", disabled=not selected, type="primary", use_container_width=True):
        st.session_state.add_selected_ids = selected
        _request_dialog("add_price")
        st.rerun()


@st.dialog("Участники", width="large")
def show_participants_dialog():
    st.caption(f"Всего участников: {len(participants)}")
    bulk_threshold = st.number_input(
        "Удалить все товары со скидкой больше, %",
        value=5.0, step=0.01,
        key="participant_bulk_discount_threshold",
        help="Сравнивается текущая скидка участника: разница между базовой ценой и текущей ценой участия, в процентах. Удаление выполняется только через существующий диалог подтверждения.",
    )
    if st.button(f"Удалить все товары со скидкой больше {bulk_threshold:g}%", use_container_width=True, key="participant_bulk_remove_above_threshold"):
        threshold = Decimal(str(bulk_threshold))
        bulk_ids = []
        for product in participants:
            discount = _participant_discount_percent(product)
            if discount is not None and discount > threshold:
                bulk_ids.append(str(product.product_id))
        if bulk_ids:
            st.session_state.selected_participant_ids = sorted(set(bulk_ids))
            st.session_state.delete_selected_ids = sorted(set(bulk_ids))
            _request_dialog("delete")
            st.rerun()
        else:
            st.info(f"Участников со скидкой больше {threshold}% нет.")
    st.caption("Массовая кнопка только формирует список удаления. Перед mutation остаются текущие Preview/проверки/подтверждение существующего RemoveProductsService.")

    selected = _participant_editor()
    update_col, remove_col = st.columns(2)
    with update_col:
        if st.button("Обновить цену", disabled=not selected, type="primary", use_container_width=True):
            st.session_state.update_selected_ids = selected
            st.session_state.update_price_plan = {}
            st.session_state.update_price_plan_sequence = st.session_state.get("update_price_plan_sequence", 0)
            st.session_state.update_price_package_editor_version = st.session_state.get("update_price_package_editor_version", 0) + 1
            _request_dialog("update_price")
            st.rerun()
    with remove_col:
        if st.button("Удалить из акции", disabled=not selected, use_container_width=True):
            st.session_state.delete_selected_ids = selected
            _request_dialog("delete")
            st.rerun()


col_candidates, col_participants, col_auto_add = st.columns(3)
with col_candidates:
    if st.button(
        f"Кандидаты — {len(candidate_rows)}",
        key="candidates_hub_button",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.selected_candidate_ids = []
        st.session_state.candidate_table_version = st.session_state.get("candidate_table_version", 0) + 1
        show_candidates_dialog()
with col_participants:
    if st.button(
        f"Участники — {len(participants)}",
        key="participants_hub_button",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.selected_participant_ids = []
        st.session_state.participant_table_version = st.session_state.get("participant_table_version", 0) + 1
        show_participants_dialog()
with col_auto_add:
    if st.button(
        "Автодобавление Ozon",
        key="auto_add_hub_button",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.pop("auto_add_selected_action_id", None)
        st.session_state.pop("auto_add_selected_date", None)
        st.session_state.selected_auto_add_ids = []
        st.session_state.auto_add_table_version = st.session_state.get("auto_add_table_version", 0) + 1
        _request_dialog("auto_add_hub")
        st.rerun()


def _money_decimal(row: dict, key: str) -> Decimal | None:
    raw = row.get(key)
    try:
        value = Decimal(str(raw.get("amount") if isinstance(raw, dict) else raw))
        return value if value > 0 else None
    except Exception:
        return None


def _candidate_price(row: dict) -> Decimal:
    value = _money_decimal(row, "price")
    if value is None:
        raise ValueError(f"Идентификатор товара {row.get('id', row.get('product_id'))}: отсутствует положительная Цена для расчёта")
    return value


def _candidate_max_action_price(row: dict) -> Decimal | None:
    return _money_decimal(row, "max_action_price")


def _participant_price(product) -> Decimal:
    if product.price is None:
        raise ValueError(f"Идентификатор товара {product.product_id}: отсутствует Цена для расчёта")
    return Decimal(str(product.price))


def _candidate_elastic_bounds(row: dict) -> tuple[Decimal, Decimal]:
    return elastic_discount_bounds(
        _candidate_price(row),
        _money_decimal(row, "price_min_elastic"),
        _money_decimal(row, "price_max_elastic"),
    )


def _elastic_threshold_display(percent: Decimal, price: Decimal) -> str:
    return f"{percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}% → {format_money(price)} ₽"


def _price_plan_dialog(selected_ids: list[str], *, mode: str):
    """Edit one accumulated price package.

    ADD uses Ozon's per-product Elastic Boosting price interval.  Each new
    candidate starts at its own minimum required discount; inline edits are
    accepted only inside that candidate's calculated interval.
    UPDATE uses the same per-product Ozon Elastic Boosting price thresholds
    as ADD. There is no hard-coded 1%–18% business rule.
    """
    is_add = mode == "add"
    plan_key = "add_price_plan" if is_add else "update_price_plan"
    if not is_add:
        st.subheader("Обновление цены участников")

    existing = dict(st.session_state.get(plan_key, {}))
    existing_ids = [str(pid) for pid in existing.get("selected_ids", [])]
    new_ids = [str(pid) for pid in selected_ids if str(pid) not in existing_ids]
    working_ids = existing_ids + new_ids

    st.caption(f"В пакете товаров: {len(working_ids)}")
    st.caption("Для каждого товара скидку можно изменить прямо в таблице двойным нажатием ЛКМ.")

    default_boost = Decimal("0")
    if is_add:
        st.info("Для каждого нового товара начальная скидка рассчитывается автоматически: минимальный процент, необходимый для попадания в минимальная цена бустинга.")
    else:
        st.info("Для каждого участника диапазон скидки рассчитывается индивидуально по актуальным минимальная цена бустинга / максимальная цена бустинга, полученным от Ozon.")

    if not working_ids:
        st.info("Пакет пуст. Выберите товары в таблице кандидатов и добавьте их в пакет.")
        return

    discounts = {str(k): str(v) for k, v in existing.get("discounts", {}).items()}
    source_rows = []
    errors = []
    for pid in working_ids:
        if is_add:
            row = candidate_by_id.get(pid)
            if not row:
                continue
            base = _candidate_price(row)
            action_limit = _candidate_max_action_price(row)
            row_error = False
            try:
                min_discount, max_discount = _candidate_elastic_bounds(row)
            except Exception as exc:
                min_discount = max_discount = Decimal("0")
                errors.append(f"{pid}: {exc}")
                row_error = True
            if pid in new_ids and not row_error:
                discounts[pid] = str(min_discount)
            source_rows.append((
                pid, row.get("name") or "Неизвестно", base, action_limit,
                _money_decimal(row, "price_min_elastic"), _money_decimal(row, "price_max_elastic"),
                min_discount, max_discount,
            ))
        else:
            product = participant_by_id.get(pid)
            if product is None:
                errors.append(f"{pid}: товар отсутствует в текущем списке участников; требуется обновить данные")
                continue
            base = _participant_price(product)
            action_limit = product.max_action_price
            try:
                min_discount, max_discount = elastic_discount_bounds(
                    base, product.price_min_elastic, product.price_max_elastic
                )
            except Exception as exc:
                min_discount = max_discount = Decimal("0")
                errors.append(f"{pid}: {exc}")
            if pid in new_ids and product.price_min_elastic is not None and product.price_max_elastic is not None:
                discounts[pid] = str(min_discount)
            source_rows.append((
                pid, product.name or "Неизвестно", base, action_limit,
                product.price_min_elastic, product.price_max_elastic, min_discount, max_discount,
            ))

    if not is_add:
        st.markdown("#### Единый процент для всех выбранных товаров")
        st.caption("Заданный процент проверяется отдельно для каждого товара по его актуальному диапазону Ozon. Если хотя бы один товар не проходит проверку, изменения не применяются ни к одному товару.")
        value_col, apply_col = st.columns([1.6, 0.8])
        with value_col:
            # Streamlit number_input требует, чтобы value/session_state, min_value и step
            # имели совместимый числовой тип. Значение в session_state могло остаться
            # строкой после предыдущего сохранения плана, поэтому нормализуем его до float
            # именно для UI-виджета. В бизнес-логику значение снова преобразуется в Decimal
            # через Decimal(str(...)), чтобы не терять детерминированность расчётов.
            raw_global_value = st.session_state.get("update_global_discount_value", 0.0)
            try:
                global_value = float(Decimal(str(raw_global_value)))
            except (ValueError, TypeError, ArithmeticError):
                global_value = 0.0
            st.session_state["update_global_discount_value"] = global_value
            manual_value = st.number_input(
                "Процент", step=0.01, format="%.2f",
                key="update_global_discount_value",
                help="Введите один процент, который будет применён ко всем выбранным товарам. Для каждого товара отдельно проверяется его актуальный минимум и максимум.",
            )
        with apply_col:
            st.markdown("<div style='height:29px'></div>", unsafe_allow_html=True)
            apply_global = st.button("Применить ко всем", type="primary", use_container_width=True, key="update_apply_global_discount")
        if apply_global:
            target = Decimal(str(manual_value))
            validation_rows = [
                {
                    "product_id": pid, "name": name, "base_price": base,
                    "price_min_elastic": min_price, "price_max_elastic": max_price,
                    "min_discount": min_disc, "max_discount": max_disc,
                }
                for pid, name, base, _limit, min_price, max_price, min_disc, max_disc in source_rows
            ]
            errors_global, prices_global = validate_global_elastic_discount(validation_rows, target)
            if errors_global:
                st.error("Единый процент не применён. Проверка товаров:\n" + "\n".join(f"• {item}" for item in errors_global))
            else:
                next_package = dict(existing)
                next_package["selected_ids"] = [str(x[0]) for x in source_rows]
                next_package["discounts"] = {str(x[0]): str(target) for x in source_rows}
                next_package["prices"] = prices_global
                next_package["operation"] = "−N%"
                next_package["value"] = str(target)
                next_package["id"] = existing.get("id", 1)
                st.session_state[plan_key] = next_package
                st.session_state["update_price_package_editor_version"] = st.session_state.get("update_price_package_editor_version", 0) + 1
                st.session_state["_pending_dialog"] = "update_price"
                st.rerun()

    calculated = {}
    for pid, _name, base, _action_limit, price_min_elastic, price_max_elastic, min_discount, max_discount in source_rows:
        try:
            discount = Decimal(str(discounts.get(pid, default_boost)))
            if is_add:
                calculated[pid] = calculate_candidate_elastic_price(
                    base, discount, price_min_elastic, price_max_elastic, "Без округления"
                )
            else:
                calculated[pid] = calculate_candidate_elastic_price(
                    base, discount, price_min_elastic, price_max_elastic, "Без округления"
                )
        except Exception as exc:
            errors.append(f"{pid}: {exc}")

    for error in errors:
        st.error(error)

    editor_rows = []
    for pid, name, base, action_limit, price_min_elastic, price_max_elastic, min_discount, max_discount in source_rows:
        if is_add:
            min_label = _elastic_threshold_display(min_discount, price_min_elastic) if price_min_elastic is not None else "—"
            max_label = _elastic_threshold_display(max_discount, price_max_elastic) if price_max_elastic is not None else "—"
        else:
            min_label = _elastic_threshold_display(min_discount, price_min_elastic) if price_min_elastic is not None else "—"
            max_label = _elastic_threshold_display(max_discount, price_max_elastic) if price_max_elastic is not None else "—"
        editor_rows.append({
            "__id": pid,
            "SKU": _display_id_for_product(pid),
            "Название": name,
            "Цена": str(base),
            "Минимальная цена бустинга": min_label,
            "Максимальная цена бустинга": max_label,
            "Ограничение для акции": str(action_limit) if action_limit is not None else "—",
            "Скидка": float(Decimal(str(discounts.get(pid, default_boost)))),
            "Новая цена": _display_whole_price(calculated.get(pid, "")),
            "__min_discount": str(min_discount),
            "__max_discount": str(max_discount),
            "__base_price": str(base),
            "__min_price": str(price_min_elastic) if price_min_elastic is not None else "",
            "__max_price": str(price_max_elastic) if price_max_elastic is not None else "",
        })

    component_result = _product_table_component(
        editor_rows,
        component_key=f"{mode}_price_editor_{st.session_state.get(mode + '_package_editor_version', 0)}",
        selectable=False,
        height=520,
        mode="package",
        allow_remove=is_add,
    )
    if isinstance(component_result, dict):
        action = component_result.get("action")
        pid = str(component_result.get("product_id", ""))
        valid_ids = {str(x[0]) for x in source_rows}
        if action == "discount" and pid in valid_ids:
            try:
                discount = Decimal(str(component_result.get("discount")))
                source = next(x for x in source_rows if str(x[0]) == pid)
                if is_add:
                    base, min_price, max_price = source[2], source[4], source[5]
                    min_discount, max_discount = source[6], source[7]
                    if discount < min_discount or discount > max_discount:
                        raise ValueError(
                            f"Допустимо для этого товара: {min_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%–"
                            f"{max_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
                        )
                    new_price = calculate_candidate_elastic_price(base, discount, min_price, max_price)
                else:
                    min_discount, max_discount = source[6], source[7]
                    if discount < min_discount or discount > max_discount:
                        raise ValueError(
                            f"Допустимо для этого товара: {min_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%–"
                            f"{max_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
                        )
                    new_price = calculate_candidate_elastic_price(
                        source[2], discount, source[4], source[5]
                    )
                next_package = dict(existing) if is_add else {
                    "id": 1,
                    "selected_ids": [str(x[0]) for x in source_rows],
                    "discounts": dict(discounts),
                    "prices": dict(calculated),
                    "operation": "−N%", "value": None,
                }
                next_discounts = dict(discounts)
                next_discounts[pid] = str(discount)
                next_prices = dict(calculated)
                next_prices[pid] = new_price
                next_package["selected_ids"] = [str(x[0]) for x in source_rows]
                next_package["discounts"] = next_discounts
                next_package["prices"] = next_prices
                next_package["operation"] = "−N%"
                next_package["value"] = None
                next_package["id"] = existing.get("id", 1)
                st.session_state[plan_key] = next_package
                st.session_state[f"{mode}_package_editor_version"] = st.session_state.get(f"{mode}_package_editor_version", 0) + 1
                if not is_add:
                    st.session_state["_pending_dialog"] = "update_price"
                st.rerun()
            except (TypeError, ValueError) as exc:
                st.error(f"Изменение скидки заблокировано: {exc}")
        elif action == "remove" and is_add and pid in valid_ids:
            remaining = [str(x[0]) for x in source_rows if str(x[0]) != pid]
            next_package = dict(existing)
            next_package["selected_ids"] = remaining
            next_package["discounts"] = {k: v for k, v in discounts.items() if k in remaining}
            next_package["prices"] = {p: calculate_candidate_elastic_price(_candidate_price(candidate_by_id[p]), Decimal(str(next_package["discounts"].get(p, 0))), _money_decimal(candidate_by_id[p], "price_min_elastic"), _money_decimal(candidate_by_id[p], "price_max_elastic")) for p in remaining}
            st.session_state[plan_key] = next_package if remaining else {}
            st.session_state[f"{mode}_package_editor_version"] = st.session_state.get(f"{mode}_package_editor_version", 0) + 1
            st.rerun()

    if is_add:
        candidate_package = dict(existing)
        candidate_package["selected_ids"] = [pid for pid, *_rest in source_rows]
        candidate_package["discounts"] = discounts
        candidate_package["prices"] = calculated
        candidate_package["operation"] = "−N%"
        candidate_package["value"] = None
        candidate_package["id"] = existing.get("id", 1)
        if not new_ids:
            st.session_state[plan_key] = candidate_package

        action_col, clear_col = st.columns(2)
        with action_col:
            if new_ids and st.button("Добавить выбранные в пакет", type="primary", use_container_width=True, disabled=bool(errors)):
                st.session_state[plan_key] = candidate_package
                st.session_state.add_selected_ids = []
                st.session_state.add_package_editor_version = st.session_state.get("add_package_editor_version", 0) + 1
                st.rerun()
        with clear_col:
            if st.button("Очистить", use_container_width=True):
                st.session_state[plan_key] = {}
                st.session_state.add_selected_ids = []
                st.session_state.add_package_confirm_version = st.session_state.get("add_package_confirm_version", 0) + 1
                st.session_state.add_package_editor_version = st.session_state.get("add_package_editor_version", 0) + 1
                st.rerun()
    else:
        if st.button("Подтвердить цены", type="primary", disabled=bool(errors), use_container_width=True):
            next_plan = {
                "id": st.session_state.get("update_price_plan_sequence", 0) + 1,
                "selected_ids": [pid for pid, *_rest in source_rows],
                "prices": calculated,
                "discounts": discounts,
                "operation": "−N%",
                "value": None,
            }
            st.session_state["update_price_plan_sequence"] = next_plan["id"]
            pending = list(st.session_state.get("update_price_plans", []))
            pending.append(next_plan)
            st.session_state["update_price_plans"] = pending
            st.session_state["update_price_plan"] = {}
            st.session_state["update_selected_ids"] = []
            st.rerun()


@st.dialog("Добавление товаров", width="large")
def show_add_price_dialog():
    _price_plan_dialog(st.session_state.get("add_selected_ids", []), mode="add")


@st.dialog("Обновление цены", width="large")
def show_update_price_dialog():
    _price_plan_dialog(st.session_state.get("update_selected_ids", []), mode="update")


@st.dialog("Удаление товаров из акции")
def show_delete_dialog():
    selected_ids = st.session_state.get("delete_selected_ids", [])
    st.warning(f"Будет удалено из акции: {len(selected_ids)} товаров.")
    _interactive_readonly_table(
        [{"SKU": _display_id_for_product(pid), "Название": participant_by_id.get(pid).name if participant_by_id.get(pid) else "Неизвестно"} for pid in selected_ids],
        component_key="delete_confirmation_table", height=520)
    confirm = st.checkbox("Я подтверждаю удаление выбранных товаров")
    if st.button("Удалить", disabled=not confirm, type="primary", use_container_width=True):
        try:
            with _loading_overlay("Удаление товаров", "Проверяем актуальность, создаём снимок, выполняем изменение и проверяем результат…"):
                result = RemoveProductsService(adapter, repo).execute(
                    promotion.action_id, selected_ids, "streamlit-session", confirmed=True
                )
            st.session_state.selected_participant_ids = []
            read_cache.clear()
            st.success(f"Удаление завершено: {len(result)} товаров.")
            st.rerun()
        except Exception as exc:
            st.error(f"Удаление заблокировано: {exc}")


# One-shot dialog dispatch. Account is a startup dialog, but it must never
# compete with another pending dialog. We only auto-open it when the session
# has no credentials yet; after Save/Test it will not reopen on normal reruns.
pending_dialog = st.session_state.pop("_pending_dialog", None)
if pending_dialog is None and st.session_state.get("startup_account_dialog_pending"):
    st.session_state.startup_account_dialog_pending = False
    if not (st.session_state.get("ozon_client_id") and st.session_state.get("ozon_api_key")):
        pending_dialog = "account"

if pending_dialog == "account":
    _render_account_dialog()
elif pending_dialog == "add_price":
    show_add_price_dialog()
elif pending_dialog == "update_price":
    show_update_price_dialog()
elif pending_dialog == "delete":
    show_delete_dialog()
elif pending_dialog == "auto_add_hub":
    show_auto_add_dialog()
elif pending_dialog == "auto_add_delete":
    show_auto_add_delete_dialog()


def _render_operation_confirmation(state_key: str, *, title: str):
    result_state = st.session_state.get(state_key)
    if not result_state:
        return
    st.markdown(f"## {title}")
    status = result_state.get("status", "UNKNOWN_RESULT")
    operation_id = result_state.get("operation_id", "Неизвестно")
    if status == "SUCCESS":
        st.success("Операция завершена и результат подтверждён повторным чтением из Ozon.")
    elif status == "PARTIAL":
        st.warning("Операция завершена частично. Результат по каждому товару показан ниже.")
    else:
        st.error("Операция завершена с ошибкой или требует проверки.")
    st.markdown(f"**Операция:** `{operation_id}` · **Статус:** `{_status_ru(status)}`")
    message = result_state.get("message")
    if message:
        st.write(message)
    item_rows = result_state.get("items", [])
    if item_rows:
        _interactive_readonly_table(
            item_rows,
            component_key=f"confirmed_operation_{operation_id}",
            height=520,
        )
    if st.button("Закрыть результат", key=f"close_{state_key}", use_container_width=True):
        st.session_state.pop(state_key, None)
        st.rerun()


def _render_pending_price_operations(plan_key: str, selected_key: str, *, mode: str):
    plans = list(st.session_state.get(plan_key, []))
    if not plans:
        return

    for plan in plans:
        plan_id = plan["id"]
        prices = plan["prices"]
        selected_ids = plan["selected_ids"]
        title = "Проверка и отправка: добавление товаров" if mode == "add" else "Проверка и отправка: обновление цены"
        st.subheader(f"{title} · пакет #{plan_id}")
        st.caption(f"Скидка: {plan['value']}% · товаров: {len(selected_ids)}")
        if mode == "add":
            rows = []
            for pid in selected_ids:
                row = candidate_by_id.get(pid, {})
                rows.append({
                    "SKU": _display_id_for_product(pid),
                    "Название": row.get("name") or "Неизвестно",
                    "Цена": format_money(row.get("price")),
                    "Минимальная цена бустинга": format_money(row.get("price_min_elastic")),
                    "Максимальная цена бустинга": format_money(row.get("price_max_elastic")),
                    "Новая цена": _display_whole_price(prices[pid]),
                })
        else:
            rows = []
            for pid in selected_ids:
                product = participant_by_id.get(pid)
                rows.append({
                    "SKU": _display_id_for_product(pid),
                    "Название": product.name if product else "Неизвестно",
                    "Цена": format_money(product.price if product else None),
                    "Минимальная цена бустинга": format_money(product.price_min_elastic if product else None),
                    "Максимальная цена бустинга": format_money(product.price_max_elastic if product else None),
                    "Старая цена акции": format_money(product.action_price if product else None),
                    "Скидка": (
                        f"{format_number(Decimal(str(plan.get('discounts', {}).get(pid, 0))))}%"
                        if plan.get("discounts", {}).get(pid) is not None else "—"
                    ),
                    "Новая цена": _display_whole_price(prices[pid]),
                })
        _interactive_readonly_table(rows, component_key=f"pending_{mode}_preview_table", height=520)
        confirm_key = f"{plan_key}_{plan_id}_confirm"
        send_key = f"{plan_key}_{plan_id}_send"
        confirm = st.checkbox("Я проверил товары и цены и подтверждаю отправку", key=confirm_key)
        if st.button("Отправить изменения", disabled=not confirm, type="primary", key=send_key):
            try:
                with _loading_overlay(
                    "Обновление цены" if mode == "update" else "Добавление товаров",
                    "Проверяем актуальные данные и выполняем проверку актуальности…",
                ) as loading:
                    if mode == "add":
                        loading("Создаём снимок перед изменением…")
                        result = AddProductsService(adapter, repo).execute(
                            promotion.action_id, selected_ids, prices, candidate_by_id, "streamlit-session", confirmed=True
                        )
                    else:
                        loading("Создаём снимок перед изменением…")
                        result = UpdateParticipantPricesService(adapter, repo).execute(
                            promotion.action_id, selected_ids, prices, participant_by_id, "streamlit-session", confirmed=True
                        )
                    loading("Проверяем результат изменения повторным чтением из Ozon…")
                    latest = repo.list_operations(limit=1)
                    op_row = latest[0] if latest else None

                item_rows = []
                if op_row:
                    for item in repo.list_operation_items(op_row["operation_id"]):
                        item_rows.append({
                            "SKU": item["product_id"],
                            "Старая цена": item["old_action_price"],
                            "Новая цена": _display_whole_price(item["requested_action_price"]),
                            "Фактическая цена": _display_whole_price(item["actual_action_price"]) if item["actual_action_price"] is not None else "Неизвестно",
                            "Статус": _status_ru(item["status"]),
                            "Причина Ozon": item["error"] or "—",
                            "Предупреждение": item["warning"] or "—",
                        })
                result_state = {
                    "status": op_row["status"] if op_row else "Неизвестно",
                    "operation_id": op_row["operation_id"] if op_row else "Неизвестно",
                    "message": result,
                    "items": item_rows,
                }
                state_key = "last_add_operation_result" if mode == "add" else "last_update_operation_result"
                st.session_state[state_key] = result_state
                remaining = [p for p in st.session_state.get(plan_key, []) if p["id"] != plan_id]
                st.session_state[plan_key] = remaining
                read_cache.clear()
                st.rerun()
            except Exception as exc:
                latest = repo.list_operations(limit=1)
                op_row = latest[0] if latest else None
                item_rows = []
                if op_row and op_row["operation_type"] in {"ADD_PRODUCTS", "UPDATE_PRICE"}:
                    item_rows = [{
                        "SKU": item["product_id"],
                        "Старая цена": item["old_action_price"],
                        "Новая цена": _display_whole_price(item["requested_action_price"]),
                        "Фактическая цена": _display_whole_price(item["actual_action_price"]) if item["actual_action_price"] is not None else "Неизвестно",
                        "Статус": _status_ru(item["status"]),
                        "Причина Ozon": item["error"] or item["warning"] or "—",
                    } for item in repo.list_operation_items(op_row["operation_id"])]
                state_key = "last_add_operation_result" if mode == "add" else "last_update_operation_result"
                st.session_state[state_key] = {
                    "status": op_row["status"] if op_row else "FAILED",
                    "operation_id": op_row["operation_id"] if op_row else "Неизвестно",
                    "message": f"Изменения заблокированы/не завершены: {exc}",
                    "items": item_rows,
                }
                st.session_state[plan_key] = [p for p in st.session_state.get(plan_key, []) if p["id"] != plan_id]
                st.rerun()


def _render_add_package():
    """Render one accumulated ADD package.

    The package editor is a local static Streamlit component.  It keeps the
    SKU delete control inside the SKU cell and reveals it only on hover.
    There is no CDN/frontend build dependency.
    """
    package = st.session_state.get("add_price_plan", {})
    selected_ids = [str(pid) for pid in package.get("selected_ids", [])]
    if not selected_ids:
        return

    prices = {str(k): v for k, v in package.get("prices", {}).items()}
    discounts = {str(k): str(v) for k, v in package.get("discounts", {}).items()}

    # A package may survive a Streamlit rerun after the source candidate list
    # has been refreshed.  Fail closed instead of passing an empty row into
    # _candidate_price() and crashing the whole page.
    valid_package_ids = [pid for pid in selected_ids if pid in candidate_by_id]
    stale_package_ids = [pid for pid in selected_ids if pid not in candidate_by_id]
    if stale_package_ids:
        st.warning(
            "Из пакета удалены устаревшие товары, которых нет в текущем списке кандидатов: "
            + ", ".join(stale_package_ids)
        )
        selected_ids = valid_package_ids
        if selected_ids:
            st.session_state["add_price_plan"] = {
                **package,
                "selected_ids": selected_ids,
                "prices": {k: v for k, v in prices.items() if k in selected_ids},
                "discounts": {k: v for k, v in discounts.items() if k in selected_ids},
            }
            package = st.session_state["add_price_plan"]
            prices = {str(k): v for k, v in package.get("prices", {}).items()}
            discounts = {str(k): str(v) for k, v in package.get("discounts", {}).items()}
        else:
            st.session_state["add_price_plan"] = {}
            return

    st.subheader("Проверка и отправка: добавление товаров · пакет")
    st.caption(f"Товаров в одном пакете: {len(selected_ids)}")

    editor_rows = []
    for pid in selected_ids:
        row = candidate_by_id.get(pid, {})
        try:
            min_discount, max_discount = _candidate_elastic_bounds(row)
            min_label = _elastic_threshold_display(min_discount, _money_decimal(row, "price_min_elastic"))
            max_label = _elastic_threshold_display(max_discount, _money_decimal(row, "price_max_elastic"))
        except Exception:
            min_discount, max_discount = Decimal("0"), Decimal("0")
            min_label = format_money(row.get("price_min_elastic"))
            max_label = format_money(row.get("price_max_elastic"))
        editor_rows.append({
            "product_id": pid,
            "sku": _display_id_for_product(pid),
            "name": row.get("name") or "Неизвестно",
            "price": format_money(row.get("price")),
            "минимальная цена бустинга": min_label,
            "максимальная цена бустинга": max_label,
            "discount": float(discounts.get(pid, min_discount)),
            "new_price": str(prices.get(pid, "")),
            "__min_discount": str(min_discount),
            "__max_discount": str(max_discount),
            "__base_price": str(_candidate_price(row)),
            "__min_price": str(_money_decimal(row, "price_min_elastic") or ""),
            "__max_price": str(_money_decimal(row, "price_max_elastic") or ""),
        })

    component_result = PACKAGE_EDITOR_COMPONENT(
        rows=editor_rows,
        selectable=False,
        selected_ids=[],
        mode="package",
        allow_remove=True,
        key=f"add_package_editor_{st.session_state.get('add_package_editor_version', 0)}",
        height=520,
        default=None,
    )

    if isinstance(component_result, dict):
        action = component_result.get("action")
        pid = str(component_result.get("product_id", ""))
        current_ids = [str(value) for value in package.get("selected_ids", [])]
        if pid in current_ids and action == "remove":
            remaining = [value for value in current_ids if value != pid]
            next_package = dict(package)
            next_package["selected_ids"] = remaining
            next_package["prices"] = {k: v for k, v in prices.items() if k in remaining}
            next_package["discounts"] = {k: v for k, v in discounts.items() if k in remaining}
            st.session_state["add_price_plan"] = next_package if remaining else {}
            st.session_state["add_package_confirm_version"] = st.session_state.get("add_package_confirm_version", 0) + 1
            st.session_state["add_package_editor_version"] = st.session_state.get("add_package_editor_version", 0) + 1
            st.rerun()
        elif pid in current_ids and action == "discount":
            try:
                discount = Decimal(str(component_result.get("discount")))
                source = candidate_by_id.get(pid)
                if source:
                    min_discount, max_discount = _candidate_elastic_bounds(source)
                    next_price = calculate_candidate_elastic_price(
                        _candidate_price(source), discount,
                        _money_decimal(source, "price_min_elastic"), _money_decimal(source, "price_max_elastic"),
                    )
                    next_prices = dict(prices)
                    next_prices[pid] = next_price
                    next_discounts = dict(discounts)
                    next_discounts[pid] = str(discount)
                    next_package = dict(package)
                    next_package["discounts"] = next_discounts
                    next_package["prices"] = next_prices
                    st.session_state["add_price_plan"] = next_package
                    st.session_state["add_package_confirm_version"] = st.session_state.get("add_package_confirm_version", 0) + 1
                    st.session_state["add_package_editor_version"] = st.session_state.get("add_package_editor_version", 0) + 1
                    st.rerun()
            except (TypeError, ValueError) as exc:
                st.error(f"Изменение скидки заблокировано: {exc}")

    st.caption("Двойной клик ЛКМ по «Скидка» — ручное редактирование. Наведите курсор на SKU — справа появится кнопка удаления.")
    confirm_key = f"add_package_confirm_{st.session_state.get('add_package_confirm_version', 0)}"
    confirm = st.checkbox("Я проверил товары и цены и подтверждаю отправку", key=confirm_key)
    send_col, clear_col = st.columns(2)
    with send_col:
        if st.button("Отправить изменения", disabled=not confirm, type="primary", key="add_package_send"):
            try:
                current_package = st.session_state.get("add_price_plan", {})
                current_ids = [str(pid) for pid in current_package.get("selected_ids", [])]
                current_discounts = {str(k): str(v) for k, v in current_package.get("discounts", {}).items()}
                recalculated = {}
                with _loading_overlay("Добавление товаров в Ozon", "1/4 · Проверяем актуальные данные…") as loading:
                    for pid in current_ids:
                        source = candidate_by_id.get(pid, {})
                        recalculated[pid] = calculate_candidate_elastic_price(
                            _candidate_price(source), Decimal(str(current_discounts.get(pid, 0))),
                            _money_decimal(source, "price_min_elastic"), _money_decimal(source, "price_max_elastic"),
                        )
                    loading("2/4 · Создаём снимок и выполняем проверку актуальности…")
                    result = AddProductsService(adapter, repo).execute(
                        promotion.action_id, current_ids, recalculated, candidate_by_id, "streamlit-session", confirmed=True
                    )
                    loading("3/4 · Изменение завершено. Проверяем фактическое состояние Ozon…")
                    latest = repo.list_operations(limit=1)
                    op_row = latest[0] if latest else None
                    loading("4/4 · Формируем подтверждение операции…")

                item_rows = []
                if op_row:
                    item_rows = [{
                        "SKU": item["product_id"],
                        "Старая цена": item["old_action_price"],
                        "Новая цена": _display_whole_price(item["requested_action_price"]),
                        "Фактическая цена": _display_whole_price(item["actual_action_price"]) if item["actual_action_price"] is not None else "Неизвестно",
                        "Статус": _status_ru(item["status"]),
                        "Причина Ozon": item["error"] or "—",
                        "Предупреждение": item["warning"] or "—",
                    } for item in repo.list_operation_items(op_row["operation_id"])]
                st.session_state["last_add_operation_result"] = {
                    "status": op_row["status"] if op_row else "Неизвестно",
                    "operation_id": op_row["operation_id"] if op_row else "Неизвестно",
                    "message": result,
                    "items": item_rows,
                }
                st.session_state["add_price_plan"] = {}
                st.session_state["add_selected_ids"] = []
                st.session_state["add_package_confirm_version"] = st.session_state.get("add_package_confirm_version", 0) + 1
                st.session_state["add_package_editor_version"] = st.session_state.get("add_package_editor_version", 0) + 1
                read_cache.clear()
                st.rerun()
            except Exception as exc:
                latest = repo.list_operations(limit=1)
                op_row = latest[0] if latest and latest[0]["operation_type"] == "ADD_PRODUCTS" else None
                item_rows = []
                if op_row:
                    item_rows = [{
                        "SKU": item["product_id"],
                        "Старая цена": item["old_action_price"],
                        "Новая цена": _display_whole_price(item["requested_action_price"]),
                        "Фактическая цена": _display_whole_price(item["actual_action_price"]) if item["actual_action_price"] is not None else "Неизвестно",
                        "Статус": _status_ru(item["status"]),
                        "Причина / состояние": item["error"] or item["warning"] or "—",
                    } for item in repo.list_operation_items(op_row["operation_id"])]
                st.session_state["last_add_operation_result"] = {
                    "status": op_row["status"] if op_row else "FAILED",
                    "operation_id": op_row["operation_id"] if op_row else "Неизвестно",
                    "message": f"Изменения заблокированы/не завершены: {exc}",
                    "items": item_rows,
                }
                st.session_state["add_price_plan"] = {}
                read_cache.clear()
                st.rerun()
    with clear_col:
        if st.button("Очистить", key="add_package_clear", use_container_width=True):
            st.session_state["add_price_plan"] = {}
            st.session_state["add_selected_ids"] = []
            st.session_state["add_package_confirm_version"] = st.session_state.get("add_package_confirm_version", 0) + 1
            st.session_state["add_package_editor_version"] = st.session_state.get("add_package_editor_version", 0) + 1
            st.rerun()


_render_operation_confirmation("last_add_operation_result", title="Подтверждение операции: добавление товаров")
_render_operation_confirmation("last_update_operation_result", title="Подтверждение операции: обновление цены")
_render_add_package()
_render_pending_price_operations("update_price_plans", "update_selected_ids", mode="update")

