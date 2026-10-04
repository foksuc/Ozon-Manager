from decimal import Decimal

import pytest

from app.adapters.ozon import OzonAPIError, OzonCredentials, OzonPromotionsAdapter


class Response:
    status_code = 200
    content = b"{}"

    def __init__(self, body):
        self.body = body
        self.content = b"{}"

    def json(self):
        return self.body


class Session:
    def __init__(self, responses):
        self.calls = []
        self.headers = {}
        self.responses = list(responses)

    def request(self, method, url, json, timeout):
        self.calls.append((method, url, json))
        return self.responses.pop(0)


def adapter(body):
    s = Session([Response(body)])
    return OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s, use_sdk=False), s


def test_list_promotions_uses_result_envelope():
    a, _ = adapter({"result": [{"id": 10, "title": "Elastic", "action_type": "DISCOUNT", "date_start": "s", "date_end": "e"}]})
    rows = a.list_promotions()
    assert len(rows) == 1
    assert rows[0].action_id == "10"
    assert rows[0].title == "Elastic"
    assert rows[0].start_at == "s"
    assert rows[0].end_at == "e"


def test_list_participants_uses_v2_top_level_products_and_last_id():
    first = Response({"products": [{"id": 20, "price": {"amount": "1000", "currency": "RUB"}, "action_price": {"amount": "900", "currency": "RUB"}, "current_boost": 3, "min_boost": 12, "max_boost": 15, "price_min_elastic": {"amount": "800", "currency": "RUB"}, "price_max_elastic": {"amount": "950", "currency": "RUB"}, "stock": 4}], "total": 1, "last_id": "cursor"})
    second = Response({"products": [], "total": 1, "last_id": "cursor"})
    s = Session([first, second])
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s)
    rows = a.list_participants("10")
    assert len(rows) == 1
    assert rows[0].product_id == "20"
    assert rows[0].price == Decimal("1000")
    assert rows[0].action_price == Decimal("900")
    assert rows[0].current_boost == Decimal("3")
    assert rows[0].min_boost == Decimal("12")
    assert rows[0].max_boost == Decimal("15")
    assert rows[0].price_min_elastic == Decimal("800")
    assert rows[0].price_max_elastic == Decimal("950")
    assert s.calls[1][2]["last_id"] == "cursor"


def test_read_after_write_uses_v2_participants_endpoint():
    a, s = adapter({"products": [], "total": 0, "last_id": ""})
    a.read_participants("10")
    assert s.calls[0][0] == "POST"
    assert s.calls[0][1].endswith("/v2/actions/products")


def test_candidates_use_v2_cursor_contract():
    a, s = adapter({"products": [], "total": 0, "last_id": ""})
    a.list_candidates("10", limit=100)
    assert s.calls[0][1].endswith("/v2/actions/candidates")
    assert s.calls[0][2] == {"action_id": 10, "limit": 100, "last_id": ""}


def test_update_products_uses_live_verified_activate_contract():
    a, s = adapter({"result": {"product_ids": [20], "rejected": []}})
    result = a.update_products("10", [{"product_id": "20", "action_price": Decimal("850.00")}])
    assert s.calls[0][0] == "POST"
    assert s.calls[0][1].endswith("/v1/actions/products/activate")
    assert s.calls[0][2] == {
        "action_id": 10,
        "products": [{"product_id": 20, "action_price": 850}],
    }
    assert result.active_product_ids == ("20",)
    assert result.transport_status == 200



def test_activate_products_serializes_decimal_at_http_boundary():
    a, s = adapter({"result": {"product_ids": [20], "rejected": []}})
    result = a.activate_products(
        "10", ["20"], prices={"20": Decimal("1899.05")}
    )
    payload_price = s.calls[0][2]["products"][0]["action_price"]
    assert payload_price == 1899.05
    assert isinstance(payload_price, float)
    assert result.active_product_ids == ("20",)


def test_activate_products_preserves_optional_stock_and_partial_result():
    a, s = adapter({
        "result": {
            "product_ids": [20],
            "rejected": [{"product_id": 21, "reason": "bad price"}],
        }
    })
    result = a.activate_products(
        "10", ["20", "21"],
        prices={"20": "850", "21": "851"},
        stocks={"20": 0},
    )
    assert s.calls[0][2]["products"][0] == {
        "product_id": 20, "action_price": "850", "stock": 0
    }
    assert s.calls[0][2]["products"][1] == {
        "product_id": 21, "action_price": "851"
    }
    assert result.active_product_ids == ("20",)
    assert result.rejected[0]["product_id"] == 21


def test_deactivate_uses_v1_contract_and_partial_result():
    a, s = adapter({"result": {"product_ids": [20], "rejected": [{"product_id": 21, "reason": "not active"}]}})
    result = a.deactivate_products("10", ["20", "21"])
    assert s.calls[0][1].endswith("/v1/actions/products/deactivate")
    assert s.calls[0][2] == {"action_id": 10, "product_ids": [20, 21]}
    assert result.deactivated_product_ids == ("20",)
    assert result.rejected[0]["product_id"] == 21


def test_update_products_rejects_duplicate_product_ids():
    a, s = adapter({})
    with pytest.raises(OzonAPIError) as exc:
        a.update_products("10", [
            {"product_id": "20", "action_price": "850"},
            {"product_id": "20", "action_price": "851"},
        ])
    assert exc.value.category == "VALIDATION_ERROR"
    assert s.calls == []


def test_v2_participant_without_legacy_membership_fields_is_accepted():
    a, _ = adapter({"products": [{"id": 20, "price": {"amount": "1000", "currency": "RUB"}, "action_price": {"amount": "900", "currency": "RUB"}, "current_boost": 3, "min_boost": 1, "max_boost": 5, "add_mode": "SELLER"}], "total": 1, "last_id": ""})
    rows = a.list_participants("10")
    assert rows[0].product_id == "20"
    assert rows[0].membership is None
    assert rows[0].availability is None


def test_list_all_candidates_follows_v2_cursor():
    first = Response({"products": [{"id": 20}], "total": 2, "last_id": "cursor"})
    second = Response({"products": [{"id": 21}], "total": 2, "last_id": ""})
    s = Session([first, second])
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s)
    rows = a.list_all_candidates("10", limit=100)
    assert [row["id"] for row in rows] == [20, 21]
    assert s.calls[1][2]["last_id"] == "cursor"


def test_list_all_candidates_reads_all_863_products_across_cursor_pages():
    responses = []
    product_id = 1
    for page in range(8):
        rows = [{"id": i} for i in range(product_id, product_id + 100)]
        product_id += 100
        responses.append(Response({"products": rows, "total": 863, "last_id": str(page + 1)}))
    rows = [{"id": i} for i in range(product_id, 864)]
    responses.append(Response({"products": rows, "total": 863, "last_id": ""}))

    s = Session(responses)
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s)
    result = a.list_all_candidates("10", limit=100)

    assert len(result) == 863
    assert [row["id"] for row in result] == list(range(1, 864))
    assert len(s.calls) == 9
    assert s.calls[0][2]["last_id"] == ""
    assert s.calls[-1][2]["last_id"] == "8"


def test_list_participants_reads_all_863_products_across_cursor_pages():
    responses = []
    product_id = 1
    for page in range(8):
        rows = [{"id": i, "action_price": {"amount": "100"}} for i in range(product_id, product_id + 100)]
        product_id += 100
        responses.append(Response({"products": rows, "total": 863, "last_id": str(page + 1)}))
    rows = [{"id": i, "action_price": {"amount": "100"}} for i in range(product_id, 864)]
    responses.append(Response({"products": rows, "total": 863, "last_id": ""}))

    s = Session(responses)
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s)
    result = a.list_participants("10", limit=100)

    assert len(result) == 863
    assert [p.product_id for p in result] == [str(i) for i in range(1, 864)]
    assert len(s.calls) == 9


def test_candidate_product_id_falls_back_when_id_is_none():
    from app.services.workflow import ProductNameService

    class NameAdapter:
        def __init__(self):
            self.requested = None

        def resolve_product_names(self, product_ids):
            self.requested = set(product_ids)
            return {"123": "Товар 123"}

    adapter = NameAdapter()
    candidates, participants, names = ProductNameService(adapter).enrich(
        [{"id": None, "product_id": 123}], []
    )

    assert adapter.requested == {"123"}
    assert candidates[0]["name"] == "Товар 123"
    assert names == {"123": "Товар 123"}


def test_product_mapping_preserves_ozon_max_action_price_for_participants():
    raw = {
        "product_id": 1494258615,
        "offer_id": "1",
        "name": "Миниатюры",
        "price": {"amount": "2700", "currency": "RUB"},
        "action_price": {"amount": "2322", "currency": "RUB"},
        "max_action_price": {"amount": "2314", "currency": "RUB"},
        "current_boost": 20,
        "min_boost": 15,
        "max_boost": 55,
        "price_min_elastic": {"amount": "2314"},
        "price_max_elastic": {"amount": "1913"},
    }
    product = OzonPromotionsAdapter._product("1977747", raw)
    assert product.max_action_price == Decimal("2314")


def test_resolve_product_cards_uses_direct_v3_product_info_contract_and_sources_sku():
    a, s = adapter({
        "items": [
            {
                "id": 1494258615,
                "name": "Миниатюры",
                "sources": [{"sku": 1940085241}],
            },
            {
                "id": 1508648261,
                "name": "Базуки",
                "sku": 1950676321,
            },
        ]
    })
    cards = a.resolve_product_cards(["1508648261", "1494258615"])
    assert cards == {
        "1494258615": {"name": "Миниатюры", "sku": "1940085241"},
        "1508648261": {"name": "Базуки", "sku": "1950676321"},
    }
    assert s.calls[0][1].endswith("/v3/product/info/list")
    assert s.calls[0][2] == {"product_id": [1494258615, 1508648261]}


def test_resolve_product_cards_batches_over_confirmed_1000_identifier_boundary():
    ids = [str(i) for i in range(1, 1003)]
    first = {"items": [{"id": i, "name": f"T{i}", "sources": [{"sku": i + 10000}]} for i in range(1, 1001)]}
    second = {"items": [{"id": i, "name": f"T{i}", "sources": [{"sku": i + 10000}]} for i in range(1001, 1003)]}
    s = Session([Response(first), Response(second)])
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s, use_sdk=True)
    cards = a.resolve_product_cards(ids)
    assert len(cards) == 1002
    assert len(s.calls) == 2
    assert len(s.calls[0][2]["product_id"]) == 1000
    assert len(s.calls[1][2]["product_id"]) == 2
    assert cards["1001"]["sku"] == "11001"


def test_resolve_product_cards_uses_configured_batch_size():
    ids = [str(i) for i in range(1, 8)]
    responses = [
        {"items": [{"id": i, "name": f"T{i}", "sources": [{"sku": i + 10000}]} for i in range(1, 4)]},
        {"items": [{"id": i, "name": f"T{i}", "sources": [{"sku": i + 10000}]} for i in range(4, 7)]},
        {"items": [{"id": 7, "name": "T7", "sources": [{"sku": 10007}]}]},
    ]
    s = Session([Response(body) for body in responses])
    a = OzonPromotionsAdapter(OzonCredentials("cid", "key"), session=s, use_sdk=False, product_info_batch_size=3)
    cards = a.resolve_product_cards(ids)
    assert len(cards) == 7
    assert [len(call[2]["product_id"]) for call in s.calls] == [3, 3, 1]


def test_resolve_product_cards_preserves_partial_raw_response():
    a, s = adapter({"items": [{"id": 123, "name": "Товар", "sources": [{"sku": 456}]}]})
    cards = a.resolve_product_cards(["123", "999"])
    assert cards == {"123": {"name": "Товар", "sku": "456"}}
    assert s.calls[0][2] == {"product_id": [123, 999]}
