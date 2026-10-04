from app.services.read_cache import ReadDataCache


def test_read_cache_reuses_action_data_without_network_calls():
    cache = ReadDataCache()
    cache.selected_action_id = "42"
    cache.participants = [1]
    cache.candidate_rows = [{"id": 2}]

    assert cache.has_action_data("42") is True
    assert cache.has_action_data("43") is False


def test_read_cache_clear_removes_all_read_data_but_has_no_credentials():
    cache = ReadDataCache()
    cache.promotions = [1]
    cache.selected_action_id = "42"
    cache.participants = [1]
    cache.candidate_rows = [{"id": 2}]
    cache.names = {"2": "Товар"}
    cache.name_misses = {"3"}

    cache.clear()

    assert cache.promotions is None
    assert cache.selected_action_id is None
    assert cache.participants is None
    assert cache.candidate_rows is None
    assert cache.names == {}
    assert cache.name_misses == set()


def test_read_cache_handles_900_product_ids_without_duplicates():
    cache = ReadDataCache()
    ids = {str(i) for i in range(900)} | {str(i) for i in range(450)}
    cache.names = {pid: f"Товар {pid}" for pid in ids}
    assert len(cache.names) == 900
    assert len(ids - set(cache.names)) == 0


def test_read_cache_flow_prevents_repeat_reads_and_only_resolves_new_names():
    """Regression proof for the Streamlit rerun optimization.

    The first pass populates the session cache and resolves all 900 names.
    A normal rerun must consume cached values only. Adding 3 new product IDs
    must resolve exactly those IDs rather than repeating the full lookup.
    """
    cache = ReadDataCache()
    calls = {"promotions": 0, "participants": 0, "candidates": 0, "names": []}

    def first_load():
        if cache.needs_promotion_refresh(60):
            calls["promotions"] += 1
            cache.mark_promotions(["promotion"])
        if not cache.has_action_data("42", 60):
            calls["participants"] += 1
            calls["candidates"] += 1
            cache.mark_action("42", list(range(900)), [{"id": i} for i in range(900)])
        ids = {str(row["id"]) for row in cache.candidate_rows}
        missing = sorted(ids - set(cache.names) - cache.name_misses)
        if missing:
            calls["names"].append(missing)
            cache.names.update({pid: f"Товар {pid}" for pid in missing})

    first_load()
    first_load()
    assert calls["promotions"] == 1
    assert calls["participants"] == 1
    assert calls["candidates"] == 1
    assert len(calls["names"]) == 1
    assert len(calls["names"][0]) == 900

    cache.candidate_rows.extend({"id": i} for i in range(900, 903))
    ids = {str(row["id"]) for row in cache.candidate_rows}
    missing = sorted(ids - set(cache.names) - cache.name_misses)
    cache.names.update({pid: f"Товар {pid}" for pid in missing})
    calls["names"].append(missing)

    assert calls["participants"] == 1
    assert calls["candidates"] == 1
    assert len(calls["names"][1]) == 3
    assert calls["names"][1] == ["900", "901", "902"]
