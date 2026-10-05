from pathlib import Path


UI = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"


def _source() -> str:
    return UI.read_text(encoding="utf-8")


def test_auto_add_main_button_has_no_count_and_is_centered():
    source = _source()
    assert 'st.info(f"Автодобавление Ozon —' not in source
    assert '"Автодобавление Ozon",\n        key="auto_add_hub_button"' in source
    assert '.st-key-auto_add_hub_button button {{ min-height:54px !important; justify-content:center !important; text-align:center !important; }}' in source.replace('.st-key-candidates_hub_button button,\n.st-key-participants_hub_button button,\n', '')
    assert '.st-key-auto_add_hub_button button p {{ width:100%; text-align:center !important; margin:0 !important; }}' in source.replace('.st-key-candidates_hub_button button p,\n.st-key-participants_hub_button button p,\n', '')


def test_auto_add_hub_discovers_all_promotions_from_ozon_metadata():
    source = _source()
    assert 'for _promotion_item in promotions:' in source
    assert 'values = metadata.get("auto_add_dates")' in source
    assert 'auto_add_promotions.append((_promotion_item, _dates))' in source
    assert 'hub_columns = st.columns(2)' in source
    assert 'key=f"auto_add_open_action_{item.action_id}"' in source


def test_auto_add_hub_is_not_scoped_to_fixed_elastic_action():
    source = _source()
    start = source.index('@st.dialog("Автодобавление Ozon"')
    end = source.index('candidate_dialog_help = [', start)
    block = source[start:end]
    assert 'FIXED_ACTION_ID' not in block
    assert 'str(selected_promotion.action_id)' in block
    assert 'auto_add_date=str(auto_add_date)' not in block  # no leaked fixed-action global date
    assert 'available_dates' in block
    assert 'st.selectbox(' in block


def test_auto_add_delete_plan_uses_selected_action_and_exact_ozon_date():
    source = _source()
    start = source.index('@st.dialog("Автодобавление Ozon"')
    end = source.index('candidate_dialog_help = [', start)
    block = source[start:end]
    assert '"action_id": str(selected_promotion.action_id)' in block
    assert '"auto_add_date": str(selected_date)' in block
    assert '_load_auto_add_rows_for(selected_promotion.action_id, selected_date)' in block


def test_auto_add_hub_reuses_existing_delete_dialog_and_safe_service():
    source = _source()
    assert '_request_dialog("auto_add_delete")' in source
    assert 'service = AutoAddDeleteService(adapter, repo)' in source
    assert 'service.build_operation(' in source
    assert 'service.execute(' in source
    assert 'elif pending_dialog == "auto_add_hub":' in source
    assert 'show_auto_add_dialog()' in source


def test_refresh_clears_multi_action_auto_add_ui_cache():
    source = _source()
    start = source.index('with st.sidebar:')
    end = source.index('client_id = st.session_state.get', start)
    sidebar = source[start:end]
    assert 'st.session_state.pop("auto_add_rows_by_source", None)' in sidebar
    assert 'st.session_state.pop("auto_add_selected_action_id", None)' in sidebar
    assert 'st.session_state.pop("auto_add_selected_date", None)' in sidebar


def test_actions_entry_buttons_share_auto_add_visual_contract():
    source = _source()
    assert '.st-key-candidates_hub_button button,' in source
    assert '.st-key-participants_hub_button button,' in source
    assert '.st-key-auto_add_hub_button button {{' in source
    assert 'min-height:54px !important' in source
    assert 'justify-content:center !important' in source
    assert 'text-align:center !important' in source
    assert 'key="candidates_hub_button"' in source
    assert 'key="participants_hub_button"' in source
    assert 'key="auto_add_hub_button"' in source
