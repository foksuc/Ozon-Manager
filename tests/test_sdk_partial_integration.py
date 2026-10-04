from decimal import Decimal
import sys
import types

from app.adapters.ozon_sdk import OzonSDKPromotionsReader


def test_sdk_reader_maps_actions_without_touching_product_contract(monkeypatch):
    class FakeResponse:
        def model_dump(self):
            return {"result": [{"id": 42, "title": "Elastic Boost", "action_type": "ELASTIC_BOOSTING", "date_start": "s", "date_end": "e"}]}

    class FakeAPI:
        def __init__(self, config):
            self.config = config
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def actions(self):
            assert self.config.client_id == "cid"
            assert self.config.api_key == "key"
            return FakeResponse()

    fake_seller = types.ModuleType("ozonapi.seller")
    fake_seller.SellerAPI = FakeAPI
    fake_seller.SellerAPIConfig = type("SellerAPIConfig", (), {"__init__": lambda self, client_id, api_key: setattr(self, "client_id", client_id) or setattr(self, "api_key", api_key)})
    fake_ozonapi = types.ModuleType("ozonapi")
    fake_ozonapi.seller = fake_seller
    monkeypatch.setitem(sys.modules, "ozonapi", fake_ozonapi)
    monkeypatch.setitem(sys.modules, "ozonapi.seller", fake_seller)

    rows = OzonSDKPromotionsReader("cid", "key").list_promotions()
    assert rows[0].action_id == "42"
    assert rows[0].title == "Elastic Boost"
    assert rows[0].metadata["action_type"] == "ELASTIC_BOOSTING"


def test_sdk_reader_resolves_product_names(monkeypatch):
    class FakeResponse:
        def model_dump(self):
            return {"items": [
                {"id": 123, "name": "Кофемолка"},
                {"id": 456, "name": "Органайзер"},
            ]}

    class FakeAPI:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def product_info_list(self, request):
            assert request.product_id == [123, 456]
            return FakeResponse()

    class FakeRequest:
        def __init__(self, product_id):
            self.product_id = product_id

    fake_seller = types.ModuleType("ozonapi.seller")
    fake_seller.SellerAPI = FakeAPI
    fake_seller.SellerAPIConfig = type(
        "SellerAPIConfig", (),
        {"__init__": lambda self, client_id, api_key: (setattr(self, "client_id", client_id), setattr(self, "api_key", api_key))[-1]},
    )
    fake_products = types.ModuleType("ozonapi.seller.schemas.products")
    fake_products.ProductInfoListRequest = FakeRequest
    fake_ozonapi = types.ModuleType("ozonapi")
    fake_ozonapi.seller = fake_seller
    monkeypatch.setitem(sys.modules, "ozonapi", fake_ozonapi)
    monkeypatch.setitem(sys.modules, "ozonapi.seller", fake_seller)
    monkeypatch.setitem(sys.modules, "ozonapi.seller.schemas.products", fake_products)

    rows = OzonSDKPromotionsReader("cid", "key").resolve_product_names(["456", "123", "123"])
    assert rows == {"123": "Кофемолка", "456": "Органайзер"}


def test_sdk_reader_resolves_product_card_names_and_skus(monkeypatch):
    class FakeResponse:
        def model_dump(self):
            return {"items": [
                {
                    "id": 1494258615,
                    "name": "Миниатюры",
                    "sources": [{"sku": 1940085241, "source": "sds"}],
                },
            ]}

    class FakeAPI:
        def __init__(self, config):
            self.config = config
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def product_info_list(self, request):
            assert request.product_id == [1494258615]
            return FakeResponse()

    class FakeRequest:
        def __init__(self, product_id):
            self.product_id = product_id

    fake_seller = types.ModuleType("ozonapi.seller")
    fake_seller.SellerAPI = FakeAPI
    fake_seller.SellerAPIConfig = type(
        "SellerAPIConfig", (),
        {"__init__": lambda self, client_id, api_key: (setattr(self, "client_id", client_id), setattr(self, "api_key", api_key))[-1]},
    )
    fake_products = types.ModuleType("ozonapi.seller.schemas.products")
    fake_products.ProductInfoListRequest = FakeRequest
    fake_ozonapi = types.ModuleType("ozonapi")
    fake_ozonapi.seller = fake_seller
    monkeypatch.setitem(sys.modules, "ozonapi", fake_ozonapi)
    monkeypatch.setitem(sys.modules, "ozonapi.seller", fake_seller)
    monkeypatch.setitem(sys.modules, "ozonapi.seller.schemas.products", fake_products)

    cards = OzonSDKPromotionsReader("cid", "key").resolve_product_cards(["1494258615"])
    assert cards == {"1494258615": {"name": "Миниатюры", "sku": "1940085241"}}
