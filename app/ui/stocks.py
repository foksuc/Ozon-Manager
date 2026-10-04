from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from app.services.stocks import StockChange, StockService
from app.ui.loading import loading_overlay
from app.ui.package_editor import PACKAGE_EDITOR_COMPONENT


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_stock(value: Any) -> str:
    return f"{_safe_int(value):,}".replace(",", " ")


def _normalize_rows(rows: list[dict[str, Any]], names: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = dict(row)
        pid = str(item.get("product_id", ""))
        item["Название"] = names.get(pid, item.get("name") or "Неизвестно")
        item["SKU"] = str(item.get("sku") or "Неизвестно")
        item["Идентификатор предложения"] = str(item.get("offer_id") or "Неизвестно")
        item["Идентификатор товара"] = pid
        item["Склад"] = item.get("warehouse_name") or str(item.get("warehouse_id"))
        item["Остаток"] = _format_stock(item.get("present"))
        item["Резерв"] = _format_stock(item.get("reserved"))
        item["Доступно"] = _format_stock(item.get("free_stock"))
        item["Новое наличие"] = _safe_int(item.get("new_free_stock", item.get("free_stock")))
        item["Статус"] = "Изменён" if _safe_int(item["Новое наличие"]) != _safe_int(item.get("free_stock")) else "Без изменений"
        result.append(item)
    return result


def _changes_from_rows(rows: list[dict[str, Any]]) -> list[StockChange]:
    changes: list[StockChange] = []
    for row in rows:
        old = _safe_int(row.get("free_stock"))
        new = _safe_int(row.get("new_free_stock", old))
        if new == old:
            continue
        changes.append(StockChange(
            product_id=str(row["product_id"]),
            sku=row.get("sku"),
            offer_id=row.get("offer_id"),
            warehouse_id=int(row["warehouse_id"]),
            warehouse_name=row.get("warehouse_name"),
            old_present=_safe_int(row.get("present")),
            old_reserved=_safe_int(row.get("reserved")),
            old_free_stock=old,
            requested_free_stock=new,
            updated_at=row.get("updated_at"),
        ))
    return changes



def _stock_preview_rows(changes: list[StockChange], names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    names = names or {}
    return [{
        "Название": names.get(str(c.product_id), "Неизвестно"),
        "SKU": c.sku or "Неизвестно",
        "Идентификатор товара": c.product_id,
        "Склад": c.warehouse_name or str(c.warehouse_id),
        "Было доступно": c.old_free_stock,
        "Новое доступно": c.requested_free_stock,
        "Изменение": c.requested_free_stock - c.old_free_stock,
    } for c in changes]

def _apply_search_filters(rows: list[dict[str, Any]], query: str, warehouse: str, availability: str) -> list[dict[str, Any]]:
    q = query.strip().casefold()
    result = []
    for row in rows:
        haystack = " ".join([
            str(row.get("product_id", "")), str(row.get("sku", "")),
            str(row.get("offer_id", "")), str(row.get("Название", "")),
        ]).casefold()
        if q and q not in haystack:
            continue
        if warehouse != "Все склады" and str(row.get("Склад")) != warehouse:
            continue
        free = _safe_int(row.get("free_stock"))
        reserved = _safe_int(row.get("reserved"))
        if availability == "Нет в наличии" and free != 0:
            continue
        if availability == "Есть в наличии" and free <= 0:
            continue
        if availability == "Есть резерв" and reserved <= 0:
            continue
        result.append(row)
    return result


@st.dialog("Подтверждение изменения остатков", width="large")
def _show_stock_confirmation_dialog(adapter, repository, plan, plan_kind="UPDATE") -> None:
    changes = list(plan.get("changes", []))
    if plan_kind == "ROLLBACK":
        st.warning("Это откат. Целевые значения взяты из исходного снимка; перед отправкой будет выполнена проверка актуальности.")
    else:
        st.markdown("**Проверьте Предпросмотр перед отправкой изменения в Ozon.**")
    st.caption(
        f"Товар–склад: {len(changes)} · Ozon API получает свободный остаток без резерва. "
        "Непосредственно перед изменение сервис повторит проверку актуальности."
    )
    PACKAGE_EDITOR_COMPONENT(
        rows=_stock_preview_rows(changes, getattr(st.session_state.get("read_cache"), "names", {})), selectable=False, selected_ids=[], mode="readonly",
        height=min(430, max(220, 70 + len(changes) * 38)), key="stocks_confirmation_table",
        default=None,
    )
    st.divider()
    total_delta = sum(c.requested_free_stock - c.old_free_stock for c in changes)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Товаров", len(changes))
    with m2:
        st.metric("Было доступно", _format_stock(sum(c.old_free_stock for c in changes)))
    with m3:
        st.metric("Изменение", f"{total_delta:+,}".replace(",", " "))
    cancel_col, confirm_col = st.columns([1, 1])
    with cancel_col:
        if st.button("Отмена", use_container_width=True, key="stocks_confirmation_cancel"):
            st.session_state.pop("stocks_plan", None)
            st.session_state.pop("stocks_plan_kind", None)
            st.rerun()
    with confirm_col:
        if st.button("Подтвердить и отправить в Ozon", type="primary", use_container_width=True, key="stocks_confirmation_execute"):
            try:
                service = StockService(adapter, repository)
                with loading_overlay("Изменение остатков", "проверка актуальности → снимок → изменение → контроль результата…"):
                    result = service.execute(plan, confirmed=True)
                    refreshed_rows = adapter.list_stocks_by_warehouse()
                st.session_state["stocks_rows"] = refreshed_rows
                st.session_state["stocks_last_updated"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                st.session_state["stocks_edit_buffer"] = {}
                st.session_state["stocks_selected_ids"] = []
                st.session_state.pop("stocks_plan", None)
                st.session_state.pop("stocks_plan_kind", None)
                st.session_state["stocks_last_mutation_result"] = {
                    "status": result["status"], "operation_id": result.get("operation_id"),
                    "success_count": result.get("success_count", 0), "failed_count": result.get("failed_count", 0),
                }
                st.rerun()
            except Exception as exc:
                operation_id = plan.get("operation_id") if isinstance(plan, dict) else None
                st.session_state["stocks_plan"] = plan
                category = getattr(exc, "category", "")
                is_unknown = category == "UNKNOWN_RESULT" or "результат изменение неизвестен" in str(exc).casefold()
                st.session_state["stocks_last_mutation_result"] = {
                    "status": "UNKNOWN_RESULT" if is_unknown else "ERROR",
                    "operation_id": operation_id, "message": f"{type(exc).__name__}: {exc}",
                }
                if is_unknown:
                    st.warning(f"Результат изменения неизвестен: {type(exc).__name__}: {exc}. Повторная отправка запрещена.")
                else:
                    st.error(f"Изменение не выполнено: {type(exc).__name__}: {exc}")


def show_stock_confirmation_dialog(adapter, repository) -> None:
    plan = st.session_state.get("stocks_plan")
    if plan:
        _show_stock_confirmation_dialog(
            adapter, repository, plan, st.session_state.get("stocks_plan_kind", "UPDATE")
        )


def render_stocks_page(adapter, repository, read_cache) -> None:
    st.markdown('<div class="oz-page-title">Остатки</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="oz-page-subtitle">Управление свободным остатком товаров FBS и rFBS через Ozon Seller API. Акционные данные в этот раздел не входят.</div>',
        unsafe_allow_html=True,
    )

    if adapter is None:
        st.warning("Для раздела «Остатки» подключите идентификатор клиента и ключ API в разделе «Аккаунт».")
        return

    refresh_col, last_col = st.columns([1, 2])
    with refresh_col:
        refresh = st.button("Обновить остатки", type="primary", use_container_width=True, key="stocks_refresh")
    if refresh or "stocks_rows" not in st.session_state:
        try:
            with loading_overlay("Загрузка остатков", "Получаем актуальные остатки из Ozon…"):
                raw_rows = adapter.list_stocks_by_warehouse()
                product_ids = sorted({str(r.get("product_id")) for r in raw_rows if r.get("product_id") not in (None, "")})
                missing = [pid for pid in product_ids if pid not in read_cache.names]
                if missing:
                    cards = adapter.resolve_product_cards(missing)
                    for pid, card in cards.items():
                        if card.get("name"):
                            read_cache.names[pid] = str(card["name"])
                        if card.get("sku"):
                            read_cache.skus[pid] = str(card["sku"])
                for row in raw_rows:
                    pid = str(row.get("product_id", ""))
                    if not row.get("sku") and pid in read_cache.skus:
                        row["sku"] = read_cache.skus[pid]
                    if not row.get("name") and pid in read_cache.names:
                        row["name"] = read_cache.names[pid]
            st.session_state.stocks_rows = raw_rows
            st.session_state.stocks_last_updated = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            st.session_state.stocks_edit_buffer = {}
            st.session_state.pop("stocks_plan", None)
        except Exception as exc:
            category = getattr(exc, "category", "Неизвестно")
            status = getattr(exc, "status_code", None)
            if status == 401 or status == 403:
                st.error("Ozon отклонил доступ. Проверьте идентификатор клиента и ключ API.")
            elif status == 429 or category == "RATE_LIMIT":
                st.error("Ozon временно ограничил частоту запросов. Повторите обновление позже.")
            else:
                st.error(f"Не удалось загрузить остатки из Ozon: {type(exc).__name__}: {exc}")
            return

    rows = [dict(r) for r in st.session_state.get("stocks_rows", [])]
    edit_buffer = st.session_state.setdefault("stocks_edit_buffer", {})
    for row in rows:
        key = str(row["row_key"])
        if key in edit_buffer:
            row["new_free_stock"] = edit_buffer[key]
        else:
            row["new_free_stock"] = _safe_int(row.get("free_stock"))

    with last_col:
        updated = st.session_state.get("stocks_last_updated")
        st.caption(f"Последнее обновление: {updated or '—'} · строк: {len(rows)}")

    search_col, warehouse_col, availability_col = st.columns([2, 1, 1])
    with search_col:
        query = st.text_input("Поиск", placeholder="Название, SKU, идентификатор предложения или идентификатор товара", key="stocks_search")
    warehouses = sorted({str(r.get("warehouse_name") or r.get("warehouse_id")) for r in rows})
    with warehouse_col:
        warehouse = st.selectbox("Склад", ["Все склады"] + warehouses, key="stocks_warehouse_filter")
    with availability_col:
        availability = st.selectbox("Наличие", ["Все", "Есть в наличии", "Нет в наличии", "Есть резерв"], key="stocks_availability_filter")

    filtered = _apply_search_filters(rows, query, warehouse, availability)
    total_filtered = len(filtered)
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Остаток", _format_stock(sum(_safe_int(r.get("present")) for r in filtered)))
    with metric_cols[1]:
        st.metric("Резерв", _format_stock(sum(_safe_int(r.get("reserved")) for r in filtered)))
    with metric_cols[2]:
        st.metric("Доступно", _format_stock(sum(_safe_int(r.get("free_stock")) for r in filtered)))
    # Stocks is a full operational table, like Candidates: pass every
    # filtered row to the shared table component and let the table viewport
    # provide vertical/horizontal scrolling. There is intentionally no
    # "rows per page" selector or page-number pagination.
    display_rows = _normalize_rows(filtered, read_cache.names)
    table_rows = []
    for row in display_rows:
        table_rows.append({
            "Название": row["Название"],
            "SKU": row["SKU"],
            "Идентификатор предложения": row["Идентификатор предложения"],
            "Идентификатор товара": row["Идентификатор товара"],
            "Склад": row["Склад"],
            "Остаток": row["Остаток"],
            "Резерв": row["Резерв"],
            "Доступно": row["Доступно"],
            "Новое наличие": row["Новое наличие"],
            "Статус": row["Статус"],
            "__id": row["row_key"],
        })

    from app.ui.package_editor import PACKAGE_EDITOR_COMPONENT
    event = PACKAGE_EDITOR_COMPONENT(
        rows=table_rows,
        selectable=True,
        selected_ids=st.session_state.get("stocks_selected_ids", []),
        mode="stocks",
        height=520,
        key="stocks_table_component",
        default=None,
    )
    if isinstance(event, dict):
        action = event.get("action")
        if action == "selection":
            st.session_state.stocks_selected_ids = [str(x) for x in event.get("selected_ids", [])]
        elif action == "stock":
            row_key = str(event.get("row_key", ""))
            value = _safe_int(event.get("stock"), -1)
            if row_key and value >= 0:
                edit_buffer[row_key] = value
                st.session_state.stocks_edit_buffer = edit_buffer
                # Any edit invalidates a previously prepared снимок/plan.
                st.session_state.pop("stocks_plan", None)
                # Do NOT force st.rerun() here. The custom component event is
                # already the current Streamlit run; changed/Предпросмотр/buttons
                # must be calculated from the updated buffer below. A forced
                # rerun can consume the component event before the button
                # disabled-state is recalculated, leaving Prepare disabled.
        # Selection is already part of this Streamlit run. Do not force a rerun:
        # the bulk control below must appear immediately after the row is selected.

        # The custom component event is delivered during this Streamlit run.
        # ``rows`` was materialized before the event was processed, so rebuild
        # its editable value from the updated buffer before calculating
        # ``changed``. Otherwise the buffer contains e.g. 4 while ``rows``
        # still contains 3 and the Prepare button remains disabled.
        if action == "stock":
            rows = [dict(r) for r in st.session_state.get("stocks_rows", [])]
            edit_buffer = st.session_state.setdefault("stocks_edit_buffer", {})
            for row in rows:
                key = str(row["row_key"])
                if key in edit_buffer:
                    row["new_free_stock"] = edit_buffer[key]
                else:
                    row["new_free_stock"] = _safe_int(row.get("free_stock"))

    changed = _changes_from_rows(rows)
    selected_ids = set(str(x) for x in st.session_state.get("stocks_selected_ids", []))
    selected_changes = [c for c in changed if c.key in selected_ids]

    bulk_col, prepare_col, clear_col = st.columns([1.5, 1, 1])
    with bulk_col:
        if selected_ids:
            bulk_value = st.number_input(
                f"Новое наличие для выбранных ({len(selected_ids)})",
                min_value=0, value=0, step=1, key="stocks_bulk_value",
            )
            if st.button("Применить к выбранным", use_container_width=True, key="stocks_bulk_apply"):
                for row in rows:
                    if str(row["row_key"]) in selected_ids:
                        edit_buffer[str(row["row_key"])] = int(bulk_value)
                st.session_state.stocks_edit_buffer = edit_buffer
                st.session_state.pop("stocks_plan", None)
                st.rerun()
        else:
            st.caption("Выберите товары в первом столбце таблицы для массового изменения.")
    with prepare_col:
        if st.button("Подготовить изменение", type="primary", disabled=not changed, use_container_width=True, key="stocks_prepare"):
            try:
                service = StockService(adapter, repository)
                with st.spinner("проверку актуальности и создание снимка…"):
                    plan = service.prepare(changed)
                st.session_state.stocks_plan = plan
                st.session_state.stocks_plan_kind = "UPDATE"
                st.success(f"Снимок создан: {len(changed)} товар–склад.")
            except Exception as exc:
                category = getattr(exc, "category", "")
                if category == "RATE_LIMIT":
                    st.error("Ozon ограничил частоту запросов. Изменение не отправлялось.")
                else:
                    st.error(f"Подготовка изменения заблокирована: {exc}")
    with clear_col:
        if st.button("Сбросить изменения", disabled=not edit_buffer, use_container_width=True, key="stocks_clear"):
            st.session_state.stocks_edit_buffer = {}
            st.session_state.pop("stocks_plan", None)
            st.session_state.pop("stocks_plan_kind", None)
            st.rerun()

    if changed:
        st.subheader("Предпросмотр")
        PACKAGE_EDITOR_COMPONENT(
            rows=_stock_preview_rows(changed, read_cache.names), selectable=False, selected_ids=[],
            mode="readonly", height=360, key="stocks_preview_table", default=None,
        )
        st.caption(f"Изменений: {len(changed)} · выбранных товар–склад: {len(selected_changes)}. Ozon API получает поле `stock`, то есть свободный остаток без резерва.")

    # Persist the last изменение result across the rerun triggered after a
    # successful изменение. Otherwise st.success()/st.warning() is rendered
    # and immediately destroyed by st.rerun(), making a completed изменение
    # look like "nothing happened".
    last_result = st.session_state.get("stocks_last_mutation_result")
    if last_result:
        status = last_result.get("status")
        if status == "SUCCESS":
            st.success(
                f"Остатки обновлены и подтверждены: {last_result.get('success_count', 0)}. "
                f"Идентификатор операции: {last_result.get('operation_id', 'Неизвестно')}"
            )
        elif status == "PARTIAL":
            st.warning(
                f"Изменение завершено частично: успешно {last_result.get('success_count', 0)}, "
                f"ошибок {last_result.get('failed_count', 0)}. "
                f"Идентификатор операции: {last_result.get('operation_id', 'Неизвестно')}"
            )
        elif status == "UNKNOWN_RESULT":
            st.warning(
                f"Результат изменения неизвестен: {last_result.get('message', 'проверка результата не завершена')}. "
                f"Повторная отправка запрещена. Идентификатор операции: {last_result.get('operation_id', 'Неизвестно')}"
            )
        elif status == "ERROR":
            st.error(
                f"Изменение не завершено: {last_result.get('message', 'Неизвестно')}. "
                f"Идентификатор операции: {last_result.get('operation_id', 'Неизвестно')}"
            )

    plan = st.session_state.get("stocks_plan")
    plan_kind = st.session_state.get("stocks_plan_kind", "UPDATE")

    if plan:
        _show_stock_confirmation_dialog(adapter, repository, plan, plan_kind)
