from pathlib import Path


UI = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"


def test_promotion_header_does_not_render_raw_action_state_dict():
    source = UI.read_text(encoding="utf-8")
    assert 'st.write({"action_id": promotion.action_id, "title": promotion.title, "state": promotion.state})' not in source
    assert 'st.caption(f"Action ID: {promotion.action_id} · {promotion.title}")' not in source
    assert 'st.header("Акции")' not in source


def test_products_ui_has_separate_candidate_and_participant_actions():
    source = UI.read_text(encoding="utf-8")
    assert '"Кандидаты"' in source
    assert '"Участники"' in source
    assert '"Добавить товары"' in source
    assert '"Обновить цену"' in source
    assert '"Удалить из акции"' in source
    assert '"SKU для mutation' not in source
    assert 'обновлено: {current_time}' in source


def test_price_and_membership_services_are_wired():
    source = UI.read_text(encoding="utf-8")
    assert 'AddProductsService' in source
    assert 'UpdateParticipantPricesService' in source
    assert 'RemoveProductsService' in source
    assert 'calculate_price' in source


def test_candidate_and_participant_tables_use_single_primary_entry_buttons():
    source = UI.read_text(encoding="utf-8")
    assert '@st.dialog("Кандидаты", width="large")' in source
    assert '@st.dialog("Участники", width="large")' in source
    assert 'Открыть таблицу кандидатов' not in source
    assert 'Открыть таблицу участников' not in source
    assert 'f"Кандидаты — {len(candidate_rows)}"' in source
    assert 'key="candidates_hub_button"' in source
    assert 'f"Участники — {len(participants)}"' in source
    assert 'key="participants_hub_button"' in source
    assert 'show_candidates_dialog()' in source
    assert 'show_participants_dialog()' in source


def test_full_tables_are_not_paginated_and_use_original_display_columns():
    source = UI.read_text(encoding="utf-8")
    assert 'page_size = 100' not in source
    assert 'format_candidate_rows(candidate_rows, sku_map=read_cache.skus)' in source
    assert 'format_participant_rows(participants, sku_map=read_cache.skus)' in source
    assert 'height: int = 520' in source
    assert 'Всего кандидатов: {len(candidate_rows)}' in source


def test_selection_and_mutation_actions_live_inside_the_opened_tables():
    source = UI.read_text(encoding="utf-8")
    assert 'selected = _candidate_editor()' in source
    assert 'selected = _participant_editor()' in source
    assert 'st.button("Добавить товары", disabled=not selected' in source
    assert 'st.button("Обновить цену", disabled=not selected' in source
    assert 'st.button("Удалить из акции", disabled=not selected' in source
    assert 'SKU для mutation' not in source
    assert 'Mass Operation' not in source


def test_price_editor_is_not_wrapped_in_form_and_uses_per_product_elastic_bounds():
    source = UI.read_text(encoding="utf-8")
    assert 'with st.form(f"{mode}_price_form")' not in source
    assert 'calculate_candidate_elastic_price(' in source
    assert 'elastic_discount_bounds(' in source
    assert 'диапазон скидки рассчитывается индивидуально' in source
    assert 'Новая цена' in source
    assert 'st.slider(' not in source
    assert 'st.number_input(' in source  # global-percent control; no per-row fixed slider


def test_participant_price_dialog_has_no_hardcoded_1_to_18_rule():
    source = UI.read_text(encoding="utf-8")
    assert 'discount < Decimal("1")' not in source
    assert 'discount > Decimal("18")' not in source
    assert 'calculate_candidate_elastic_price(' in source
    assert 'price_min_elastic' in source
    assert 'price_max_elastic' in source

def test_candidate_columns_use_action_limit_as_informational_field():
    source = UI.read_text(encoding="utf-8")
    assert '"Ограничение для акций"' in source
    assert 'Минимальная цена бустинга' in source
    assert 'Максимальная цена бустинга' in source
    assert 'max_action_price' in source


def test_candidate_calculation_does_not_clamp_to_max_action_price():
    source = UI.read_text(encoding="utf-8")
    assert 'calculate_candidate_elastic_price(' in source
    assert 'action_limit' in source
    assert 'Для кандидатов итоговая цена не может быть ниже «Max action price»' not in source


def test_dialogs_have_no_close_button_and_explain_x_or_escape():
    source = UI.read_text(encoding="utf-8")
    assert 'st.button("Закрыть"' not in source
    assert '× вверху окна или Esc' not in source
    assert 'Что означает каждый столбец' not in source


def test_participant_table_has_only_requested_columns():
    source = UI.read_text(encoding="utf-8")
    assert 'format_participant_rows(participants, sku_map=read_cache.skus)' in source
    assert 'Action price' not in source
    assert 'Current boost' not in source
    assert 'Offer ID' not in source
    assert 'Минимальная цена бустинга' in source
    assert 'Максимальная цена бустинга' in source
    assert 'Min boost' not in source
    assert 'Max boost' not in source
    assert '"Скидка"' in source
    assert '"Ограничение для акции"' in source


def test_dialog_lifecycle_uses_one_shot_pending_dispatch_not_persistent_flags():
    source = UI.read_text(encoding="utf-8")
    assert 'st.session_state["_pending_dialog"]' in source
    assert 'st.session_state.pop("_pending_dialog", None)' in source
    assert 'st.session_state.show_candidate_dialog' not in source
    assert 'st.session_state.show_participant_dialog' not in source
    assert 'st.session_state.show_add_price_dialog' not in source
    assert 'st.session_state.show_update_price_dialog' not in source
    assert 'st.session_state.show_delete_dialog' not in source


def test_dialog_transitions_schedule_next_dialog_before_rerun():
    source = UI.read_text(encoding="utf-8")
    assert '_request_dialog("add_price")' in source
    assert '_request_dialog("update_price")' in source
    assert '_request_dialog("delete")' in source
    assert 'st.rerun()' in source


def test_add_uses_one_accumulated_package_and_merges_new_selection():
    source = UI.read_text(encoding="utf-8")
    assert 'st.session_state.get("add_price_plan", {})' in source
    assert 'existing_ids = [str(pid) for pid in existing.get("selected_ids", [])]' in source
    assert 'new_ids = [str(pid) for pid in selected_ids if str(pid) not in existing_ids]' in source
    assert 'working_ids = existing_ids + new_ids' in source
    assert 'candidate_package["selected_ids"]' in source
    assert 'st.session_state[plan_key] = candidate_package' in source


def test_add_package_has_single_native_table_and_clear_controls():
    source = UI.read_text(encoding="utf-8")
    assert 'st.button("Очистить", key="add_package_clear"' in source
    assert 'PACKAGE_EDITOR_COMPONENT' in source
    component_source = (UI.parent / 'package_editor.py').read_text(encoding='utf-8')
    assert 'components.declare_component' in component_source
    assert 'add_package_editor_version' in source
    assert 'add_package_confirm_version' in source
    assert 'remove_from_add_package' not in source
    component = Path(__file__).parents[1] / 'app' / 'ui' / 'components' / 'ozon_package_editor' / 'index.html'
    html = component.read_text(encoding='utf-8')
    assert 'streamlit:componentReady' in html
    assert 'streamlit:setComponentValue' in html
    assert 'streamlit:render' in html
    assert '.sku-cell:hover .sku-delete' in html
    assert 'class="sku-cell"' in html


def test_add_package_discount_is_inline_editable_without_navigation():
    source = UI.read_text(encoding="utf-8")
    assert 'Двойной клик ЛКМ' in source
    assert 'calculate_candidate_elastic_price(' in source
    assert 'window.top.location.href' not in source
    component = Path(__file__).parents[1] / 'app' / 'ui' / 'components' / 'ozon_package_editor' / 'index.html'
    html = component.read_text(encoding='utf-8')
    assert '.discount-cell' in html
    assert "e.key==='Enter'" in html
    assert "action:'discount'" in html


def test_ui_preserves_ozon_action_metadata_for_auto_add():
    source = UI.read_text(encoding="utf-8")
    assert 'promotions = adapter.list_promotions()' in source
    assert 'promotion = next((p for p in promotions if str(p.action_id) == FIXED_ACTION_ID), None)' in source


def test_ui_uses_only_audited_action_and_removes_promotion_selector():
    source = UI.read_text(encoding="utf-8")
    assert 'FIXED_ACTION_ID = "1977747"' in source
    assert 'FIXED_ACTION_TITLE = "Эластичный бустинг. Без ограничения срока действия"' in source
    assert 'st.selectbox("Акция"' not in source
    assert 'promotion_service.list_promotions()' not in source
    assert 'labels = {f"{p.action_id} — {p.title}": p for p in promotions}' not in source


def test_sidebar_has_actions_and_stocks_navigation_without_home_screen():
    source = UI.read_text(encoding="utf-8")
    assert 'st.button("🎯 Акции"' in source
    assert 'st.button("📦 Остатки"' in source
    assert 'st.session_state.ui_page = "actions"' in source
    assert 'st.session_state.ui_page = "stocks"' in source
    assert 'Данный раздел ещё в разработке' not in source
    assert 'render_stocks_page(adapter, repo, read_cache)' in source
    assert 'Главный экран' not in source
    assert 'Назад к меню' not in source


def test_history_is_a_sidebar_destination_and_contains_existing_history_tools():
    source = UI.read_text(encoding="utf-8")
    assert 'st.button("📜 История"' in source
    assert 'def _render_history():' in source
    assert 'st.title("История")' in source
    assert 'Сверка результата добавления' in source
    assert 'Безопасный откат' in source
    assert 'Подтвердить откат' in source
    assert 'st.header("5. History")' not in source


def test_account_and_sidebar_layout_contract():
    source = UI.read_text(encoding="utf-8")
    assert 'st.set_page_config(page_title="Менеджер Ozon"' in source
    assert 'st.title("Менеджер Ozon")' in source
    assert 'st.caption("Elastic Boosting — расчёт от цены товара")' not in source
    assert 'st.button("👤 Аккаунт"' in source
    assert 'Mock mode' not in source
    assert 'st.button("🔄 Обновить данные"' in source
    assert 'st.button("📜 История"' in source
    assert 'st.button("Проверить подключение к Ozon"' in source
    assert '_back_to_home' not in source
    sidebar_start = source.index('with st.sidebar:')
    sidebar = source[sidebar_start:]
    labels = [line.strip() for line in sidebar.splitlines() if 'st.button(' in line or 'st.checkbox(' in line]
    assert labels.index('if st.button("👤 Аккаунт", use_container_width=True):') < labels.index('if st.button("🔄 Обновить данные", use_container_width=True):')
    assert 'Mock mode' not in source
    assert labels.index('if st.button("🔄 Обновить данные", use_container_width=True):') < labels.index('if st.button("🎯 Акции", use_container_width=True):')
    assert labels.index('if st.button("🎯 Акции", use_container_width=True):') < labels.index('if st.button("📦 Остатки", use_container_width=True):')
    assert labels.index('if st.button("📦 Остатки", use_container_width=True):') < labels.index('if st.button("📜 История", use_container_width=True):')


def test_account_credentials_are_not_rendered_in_sidebar_fields():
    source = UI.read_text(encoding="utf-8")
    sidebar_block = source[source.index('with st.sidebar:'):source.index('client_id = st.session_state.get')]
    assert 'st.text_input("Client ID"' not in sidebar_block
    assert 'st.text_input("API Key"' not in sidebar_block
    assert '@st.dialog("Аккаунт")' in source



def test_add_price_editor_uses_per_product_elastic_bounds():
    source = UI.read_text(encoding="utf-8")
    assert 'elastic_discount_bounds(' in source
    assert 'calculate_candidate_elastic_price(' in source
    assert '"__min_discount"' in source
    assert '"__max_discount"' in source
    assert 'price_min_elastic' in source
    assert 'price_max_elastic' in source



def test_package_editor_discount_and_remove_contract_is_explicit():
    component = Path(__file__).parents[1] / 'app' / 'ui' / 'components' / 'ozon_package_editor' / 'index.html'
    html = component.read_text(encoding='utf-8')
    assert 'c===\'Скидка\'||c===\'discount\'' in html
    assert 'action:\'discount\'' in html
    assert 'action:\'remove\'' in html
    assert 'aria-label="Удалить товар"' in html
    assert '🗑️' not in html


def test_add_package_editor_supports_lowercase_sku_and_unique_mutation_events():
    component = Path(__file__).parents[1] / 'app' / 'ui' / 'components' / 'ozon_package_editor' / 'index.html'
    html = component.read_text(encoding='utf-8')
    assert "c==='SKU'||c==='sku'" in html
    assert "aria-label=\"Удалить товар\"" in html
    assert "action:'remove'" in html
    assert "action:'discount'" in html
    assert 'event_id:' in html
    assert 'crypto.randomUUID' in html
    assert '🗑️' not in html


def test_price_dialog_uses_product_id_as_component_row_identity():
    source = Path("app/ui/streamlit_app.py").read_text(encoding="utf-8")
    marker = '"__id": pid,\n            "SKU": _display_id_for_product(pid)'
    assert marker in source


def test_candidate_selection_uses_source_product_id_not_reverse_sku_lookup():
    source = Path("app/ui/streamlit_app.py").read_text(encoding="utf-8")
    assert 'for display_row, source_row in zip(rows, candidate_rows):' in source
    assert 'pid = source_row.get("id", source_row.get("product_id"))' in source
    assert 'display_row["__id"] = str(pid) if pid not in (None, "") else ""' in source
    assert 'next((pid for pid, value in read_cache.skus.items()' not in source


def test_add_package_rejects_stale_candidate_ids_before_price_calculation():
    source = Path("app/ui/streamlit_app.py").read_text(encoding="utf-8")
    assert 'valid_package_ids = [pid for pid in selected_ids if pid in candidate_by_id]' in source
    assert 'stale_package_ids = [pid for pid in selected_ids if pid not in candidate_by_id]' in source
    assert 'st.session_state["add_price_plan"] = {}' in source


def test_update_price_confirmation_uses_pending_batch_and_loading_result():
    source = UI.read_text(encoding="utf-8")
    assert 'st.session_state["update_price_plans"]' in source
    assert 'st.session_state["update_price_plan"] = {}' in source
    assert 'def _loading_overlay(' in source
    assert 'oz-loading-backdrop' in source
    assert 'Обновление цены" if mode == "update"' in source
    assert 'last_update_operation_result' in source


def test_add_send_has_loading_and_persistent_confirmation_result():
    source = UI.read_text(encoding="utf-8")
    assert 'with _loading_overlay("Добавление товаров в Ozon"' in source
    assert 'last_add_operation_result' in source
    assert 'Подтверждение операции: добавление товаров' in source


def test_participant_update_has_global_discount_control_and_per_product_validation():
    source = UI.read_text(encoding="utf-8")
    assert 'Единый процент для всех выбранных товаров' in source
    assert 'Введите один процент' in source
    assert 'update_global_discount_value' in source
    assert 'Выбор процента' not in source
    assert 'Применить ко всем' in source
    assert 'validate_global_elastic_discount(validation_rows, target)' in source
    engine = Path('app/services/price_engine.py').read_text(encoding='utf-8')
    assert 'if discount_percent < minimum:' in engine
    assert 'if discount_percent > maximum:' in engine
    assert 'изменения не применяются ни к одному товару' in source
    assert 'next_package["discounts"] = {str(x[0]): str(target) for x in source_rows}' in source
    assert 'st.number_input(' in source
    assert '"Процент", step=0.01' in source
    assert 'st.session_state["update_global_discount_value"] = global_value' in source


def test_loading_overlay_is_used_for_read_and_mutation_paths():
    source = UI.read_text(encoding="utf-8")
    for title in (
        'Проверка подключения', 'Загрузка данных Ozon', 'Загрузка товаров',
        'Загрузка автодобавления', 'Загрузка карточек', 'Сверка результата',
        'Подготовка отката', 'Удаление товаров', 'Удаление из автодобавления',
        'Откат автодобавления', 'Откат', 'Добавление товаров в Ozon',
    ):
        assert f'_loading_overlay("{title}"' in source


def test_stocks_inline_edit_does_not_force_rerun_before_prepare_state_is_recalculated():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'stocks.py').read_text(encoding='utf-8')
    stock_block = source.split('elif action == "stock":', 1)[1].split('    changed = _changes_from_rows(rows)', 1)[0]
    assert 'st.session_state.stocks_edit_buffer = edit_buffer' in stock_block
    assert 'st.session_state.pop("stocks_plan", None)' in stock_block
    assert 'stocks_last_mutation_result' in source
    assert 'st.session_state["stocks_rows"] = refreshed_rows' in source
    assert not any(line.strip().startswith('st.rerun()') for line in stock_block.splitlines())
    assert 'disabled=not changed' in source
    assert 'rows = [dict(r) for r in st.session_state.get("stocks_rows", [])]' in source
    assert 'row["new_free_stock"] = edit_buffer[key]' in source


def test_stocks_mutation_result_is_not_lost_and_confirmation_is_dialog():
    source = (Path(__file__).parents[1] / "app" / "ui" / "stocks.py").read_text(encoding="utf-8")
    assert '_show_stock_confirmation_dialog(adapter, repository, plan, plan_kind)' in source
    assert 'def _show_stock_confirmation_dialog' in source
    assert 'service.execute(plan, confirmed=True)' in source
    assert 'adapter.list_stocks_by_warehouse()' in source
    assert 'stocks_last_mutation_result' in source
    assert 'st.session_state.pop("stocks_plan", None)' in source
    assert 'st.rerun()' in source
    assert 'last_result = st.session_state.get("stocks_last_mutation_result")' in source

def test_stocks_confirmation_is_a_separate_dialog_with_mutation_action():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'stocks.py').read_text(encoding='utf-8')
    assert '@st.dialog("Подтверждение изменения остатков", width="large")' in source
    assert 'key="stocks_confirmation_table"' in source
    assert 'key="stocks_confirmation_execute"' in source
    assert 'Подтвердить и отправить в Ozon' in source
    assert 'service.execute(plan, confirmed=True)' in source
    assert 'st.session_state.pop("stocks_plan", None)' in source


def test_stocks_uses_shared_ozon_loading_overlay_for_read_and_mutation():
    stocks = (Path(__file__).parents[1] / 'app' / 'ui' / 'stocks.py').read_text(encoding='utf-8')
    loading = (Path(__file__).parents[1] / 'app' / 'ui' / 'loading.py').read_text(encoding='utf-8')
    assert 'from app.ui.loading import loading_overlay' in stocks
    assert 'with loading_overlay("Загрузка остатков"' in stocks
    assert '"Изменение остатков"' in stocks
    assert 'def loading_overlay(' in loading
    assert 'oz-loading-backdrop' in loading


def test_history_owns_stocks_history_rollback_and_unknown_result_state():
    history_source = (Path(__file__).parents[1] / 'app' / 'ui' / 'streamlit_app.py').read_text(encoding='utf-8')
    stocks_source = (Path(__file__).parents[1] / 'app' / 'ui' / 'stocks.py').read_text(encoding='utf-8')
    assert '@st.dialog("История — Остатки", width="large")' in history_source
    assert 'repo.list_stock_operations(limit=100)' in history_source
    assert 'repository.list_stock_operations' not in history_source
    assert 'repository.list_stock_operation_items' not in history_source
    assert 'Подготовить откат' in history_source
    assert 'StockService(adapter, repo).prepare_rollback(str(source["snapshot_id"]))' in history_source
    assert 'r["status"] == "SUCCESS" and r["snapshot_id"]' in history_source
    assert 'dict(r) for r in history' in history_source
    assert 'Успешная операция для отката' in history_source
    assert 'StockService(adapter, repository)' not in history_source
    assert 'stocks_plan_kind = "ROLLBACK"' in history_source
    assert 'UNKNOWN_RESULT' in history_source
    assert 'Повторная отправка изменения запрещена' in history_source
    assert 'show_stock_confirmation_dialog(adapter, repo)' in history_source
    assert 'def show_stock_confirmation_dialog' in stocks_source


def test_history_has_separate_stocks_and_promotions_entry_points():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'streamlit_app.py').read_text(encoding='utf-8')
    assert 'st.button("Остатки"' in source
    assert 'st.button("Акции"' in source
    assert '@st.dialog("История — Остатки", width="large")' in source
    assert '@st.dialog("История — Акции", width="large")' in source
    assert 'st.session_state.get("history_modal") == "stocks"' in source
    assert 'st.session_state.get("history_modal") == "promotions"' in source
    assert "repository.list_stock_operations" not in source
    assert "repository.list_stock_operation_items" not in source
    assert "StockService(adapter, repository)" not in source
    assert "repo.list_stock_operations(limit=100)" in source

def test_stocks_mutation_requires_operation_and_snapshot_persistence():
    source = (Path(__file__).parents[1] / 'app' / 'services' / 'stocks.py').read_text(encoding='utf-8')
    assert 'Mutation требует operation_id и snapshot_id' in source
    assert 'Snapshot отсутствует; mutation запрещена' in source
    assert 'Операция уже завершена' in source


def test_stock_preview_helper_is_module_level_for_confirmation_dialog():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'stocks.py').read_text(encoding='utf-8')
    helper_pos = source.index('def _stock_preview_rows')
    dialog_pos = source.index('def _show_stock_confirmation_dialog')
    render_pos = source.index('def render_stocks_page')
    assert helper_pos < dialog_pos < render_pos
    assert source.count('def _stock_preview_rows') == 1
    assert 'names.get(str(c.product_id), "Неизвестно")' in source


def test_history_page_never_opens_two_dialogs_in_one_script_run():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'streamlit_app.py').read_text(encoding='utf-8')
    block = source.split('if st.session_state.ui_page == "history":', 1)[1].split('if st.session_state.ui_page == "stocks":', 1)[0]
    assert 'pending_dialog = st.session_state.pop("_pending_dialog", None)' in block
    assert 'if pending_dialog == "auto_add_rollback":' in block
    assert 'elif st.session_state.get("stocks_plan"):' in block
    assert 'elif st.session_state.get("history_modal") == "stocks":' in block
    assert 'elif st.session_state.get("history_modal") == "promotions":' in block
    assert block.index('show_auto_add_rollback_dialog()') < block.index('show_stock_confirmation_dialog(adapter, repo)')


def test_auto_add_rollback_clears_history_modal_before_pending_dialog():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'streamlit_app.py').read_text(encoding='utf-8')
    marker = 'if st.button("Подготовить откат автодобавления"'
    block = source[source.index(marker):source.index('@st.dialog("Откат автодобавления Ozon"', source.index(marker))]
    assert 'st.session_state.history_modal = None' in block
    assert '_request_dialog("auto_add_rollback")' in block


def test_startup_account_dialog_is_one_shot():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'streamlit_app.py').read_text(encoding='utf-8')
    assert 'if "startup_account_dialog_pending" not in st.session_state:' in source
    assert 'pending_dialog = "account"' in source
    assert 'if pending_dialog == "account":' in source
    assert 'if not (st.session_state.get("ozon_client_id") and st.session_state.get("ozon_api_key")):' in source


def test_table_filter_input_does_not_restore_previous_value():
    source = (Path(__file__).parents[1] / 'app' / 'ui' / 'components' / 'ozon_package_editor' / 'index.html').read_text(encoding='utf-8')
    assert 'autocomplete="off"' in source
    assert "inp.value='';inp.dataset.col=c" in source
    assert "inp.value=state.filters[c]||''" not in source


def test_mock_mode_is_removed_from_runtime_ui():
    source = UI.read_text(encoding="utf-8")
    config = (Path(__file__).parents[1] / "app" / "config.py").read_text(encoding="utf-8")
    assert 'Mock mode' not in source
    assert 'MockOzonAdapter' not in source
    assert 'mock_mode' not in config
    assert 'OZON_MOCK_MODE' not in source


def test_stocks_selection_reveals_bulk_control_without_rerun():
    source = (Path(__file__).parents[1] / "app" / "ui" / "stocks.py").read_text(encoding="utf-8")
    event_block = source.split('if isinstance(event, dict):', 1)[1].split('changed = _changes_from_rows(rows)', 1)[0]
    selection_block = event_block.split('if action == "selection":', 1)[1].split('elif action == "stock":', 1)[0]
    assert 'st.session_state.stocks_selected_ids' in selection_block
    assert 'st.rerun()' not in selection_block
    assert 'Новое наличие для выбранных' in source


def test_design_system_layout_and_surfaces_are_applied():
    source = UI.read_text(encoding="utf-8")
    component = (Path(__file__).parents[1] / "app" / "ui" / "components" / "ozon_package_editor" / "index.html").read_text(encoding="utf-8")
    assert 'max-width:1216px' in source
    assert 'padding:1.5rem 24px 3rem' in source
    assert '--oz-radius-card: 16px' in source
    assert '--oz-radius-dialog: 20px' in source
    assert 'border-radius:16px;background:var(--oz-surface)' in component
    assert 'applyTheme(e.data.theme||{})' in component
    assert "r.colorScheme='dark'" in component and "r.colorScheme='light'" in component


def test_sidebar_stop_button_is_present_and_uses_existing_stop_script():
    source = UI.read_text(encoding="utf-8")
    assert 'st.button("Выключить", use_container_width=True, key="sidebar_stop_manager")' in source
    assert 'STOP_OZON_MANAGER.bat' in source
    assert 'subprocess.Popen(["cmd.exe", "/c", str(stop_script)]' in source

def test_sidebar_stop_button_style_is_scoped_and_navigation_is_not_destructive():
    source = UI.read_text(encoding="utf-8")
    assert '.st-key-sidebar_stop button {' in source
    assert '.st-key-sidebar_stop button:hover {' in source
    assert '.stButton:last-of-type button' not in source
    assert 'with st.container(key="sidebar_stop"):' in source


def test_candidate_discount_is_embedded_into_elastic_price_columns():
    source = UI.read_text(encoding="utf-8")
    assert '"Скидка"' not in source[source.index('def _candidate_editor'):source.index('def _participant_editor')]
    display_source = (UI.parent / "display.py").read_text(encoding="utf-8")
    assert '_candidate_discount_threshold_display' in display_source


def test_update_price_editor_keeps_manual_discount_column():
    source = UI.read_text(encoding="utf-8")
    start = source.index('def _price_plan_dialog')
    end = source.index('@st.dialog("Добавление товаров"', start)
    section = source[start:end]
    assert '"Скидка": float(Decimal(str(discounts.get(pid, default_boost)))' in section
    assert "c==='Скидка'||c==='discount'" in (UI.parent / "components" / "ozon_package_editor" / "index.html").read_text(encoding="utf-8")


def test_table_filter_supports_contains_equal_and_numeric_comparisons():
    component = (Path(__file__).parents[1] / "app" / "ui" / "components" / "ozon_package_editor" / "index.html").read_text(encoding="utf-8")
    assert '<option value="contains">Содержит</option>' in component
    assert '<option value="eq">Равно</option>' in component
    assert '<option value="gte">Больше или равно</option>' in component
    assert '<option value="lte">Меньше или равно</option>' in component
    assert "function matchesFilter(value,filter)" in component
    assert "let preferPercent=needle.includes('%')" in component
    assert "if(op==='gte')return nv>=nn" in component
    assert "if(op==='lte')return nv<=nn" in component
    assert '-?\\d+' in component  # signed numeric/percentage filters, e.g. -5%


def test_bulk_discount_actions_reuse_existing_safe_dialogs():
    source = UI.read_text(encoding="utf-8")
    candidate = source[source.index('@st.dialog("Кандидаты"'):source.index('@st.dialog("Участники"')]
    participant = source[source.index('@st.dialog("Участники"'):source.index('col_candidates, col_participants')]
    assert 'candidate_bulk_add_below_threshold' in candidate
    assert '_candidate_minimum_discount(row) < threshold' in candidate
    assert 'st.session_state.add_selected_ids = sorted(set(bulk_ids))' in candidate
    assert '_request_dialog("add_price")' in candidate
    assert 'AddProductsService(' not in candidate
    assert 'participant_bulk_remove_above_threshold' in participant
    assert 'discount > threshold' in participant
    assert 'st.session_state.delete_selected_ids = sorted(set(bulk_ids))' in participant
    assert '_request_dialog("delete")' in participant
    assert 'RemoveProductsService(' not in participant


def test_dark_theme_config_is_present_without_removing_emoji_navigation():
    root = Path(__file__).parents[1]
    config = (root / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    source = UI.read_text(encoding='utf-8')
    assert '[theme.light]' in config
    assert '[theme.dark]' in config
    assert 'backgroundColor = "#0B121A"' in config
    assert 'secondaryBackgroundColor = "#141E29"' in config
    assert '"👤 Аккаунт"' in source
    assert '"🔄 Обновить данные"' in source
    assert '"🎯 Акции"' in source
    assert '"📦 Остатки"' in source
    assert '"📜 История"' in source


def test_signed_discounts_are_not_artificially_blocked_in_ui_controls():
    source = UI.read_text(encoding="utf-8")
    engine = (UI.parent.parent / "services" / "price_engine.py").read_text(encoding="utf-8")
    assert 'Порог скидки не может быть отрицательным' not in source
    assert '"Процент", min_value=0.0' not in source
    assert 'return max(Decimal("0"), min_discount)' not in engine
    assert 'price_min_elastic выше текущей цены' not in engine
