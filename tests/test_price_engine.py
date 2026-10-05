from decimal import Decimal
import pytest

from app.services.price_engine import calculate_candidate_elastic_price, calculate_elastic_boost_price, calculate_price, elastic_discount_bounds


def test_percent_examples():
    assert calculate_price(Decimal("1000"), "−N%", Decimal("5")) == Decimal("950")
    assert calculate_price(Decimal("1000"), "+N%", Decimal("5")) == Decimal("1050")
    assert calculate_price(Decimal("1000"), "−N%", Decimal("1")) == Decimal("990")
    assert calculate_price(Decimal("1000"), "+N%", Decimal("1")) == Decimal("1010")
    assert calculate_price(Decimal("1999"), "−N%", Decimal("5"), "0.01") == Decimal("1899.05")


def test_rounding_and_floor():
    assert calculate_price(Decimal("1999"), "−N%", Decimal("5"), "1") == Decimal("1899")
    assert calculate_price(Decimal("100"), "−N%", Decimal("21"), "0.01", Decimal("90")) == Decimal("90")


def test_manual_price():
    assert calculate_price(Decimal("1000"), "Вручную", Decimal("877.50")) == Decimal("877.50")


def test_non_positive_result_is_blocked():
    with pytest.raises(ValueError):
        calculate_price(Decimal("100"), "−N%", Decimal("101"))


def test_elastic_boost_uses_price_not_action_limit():
    # 2700 - 22% would be 2106, but 22% is forbidden by the application rule.
    with pytest.raises(ValueError):
        calculate_elastic_boost_price(Decimal("2700"), Decimal("22"))


def test_elastic_boost_14_percent_example():
    # 2700 - 14% = 2322, matching the participant-table example.
    assert calculate_elastic_boost_price(Decimal("2700"), Decimal("14")) == Decimal("2322")


def test_elastic_boost_18_percent_is_the_lowest_allowed_price():
    assert calculate_elastic_boost_price(Decimal("2700"), Decimal("18")) == Decimal("2214")


def test_elastic_boost_1_percent_is_allowed():
    assert calculate_elastic_boost_price(Decimal("2700"), Decimal("1")) == Decimal("2673")


def test_elastic_boost_below_1_percent_is_blocked():
    with pytest.raises(ValueError):
        calculate_elastic_boost_price(Decimal("2700"), Decimal("0"))


def test_elastic_boost_never_uses_max_action_price_as_floor():
    # Informational Ozon max_action_price must not override the 18% application floor.
    assert calculate_elastic_boost_price(Decimal("2700"), Decimal("18")) == Decimal("2214")


def test_action_price_matching_accepts_whole_ruble_readback():
    from app.domain.validation import action_price_matches_requested

    assert action_price_matches_requested(Decimal("885.60"), Decimal("886"))
    assert action_price_matches_requested(Decimal("820.00"), Decimal("820"))
    assert not action_price_matches_requested(Decimal("885.60"), Decimal("887"))
    assert not action_price_matches_requested(Decimal("880"), Decimal("881"))


def test_candidate_elastic_discount_bounds_example():
    minimum, maximum = elastic_discount_bounds(Decimal("2700"), Decimal("2314"), Decimal("1913"))
    assert minimum.quantize(Decimal("0.01")) == Decimal("14.30")
    assert maximum.quantize(Decimal("0.01")) == Decimal("29.15")


def test_candidate_elastic_price_accepts_activation_boundary():
    minimum, _ = elastic_discount_bounds(Decimal("2700"), Decimal("2314"), Decimal("1913"))
    assert calculate_candidate_elastic_price(Decimal("2700"), minimum, Decimal("2314"), Decimal("1913")) == Decimal("2314.000000000000000000000000")


def test_candidate_elastic_price_blocks_below_minimum_discount():
    with pytest.raises(ValueError, match="диапазон Ozon Elastic Boosting"):
        calculate_candidate_elastic_price(Decimal("2700"), Decimal("14"), Decimal("2314"), Decimal("1913"))


def test_candidate_elastic_price_blocks_above_maximum_discount():
    with pytest.raises(ValueError, match="диапазон Ozon Elastic Boosting"):
        calculate_candidate_elastic_price(Decimal("2700"), Decimal("30"), Decimal("2314"), Decimal("1913"))


def test_candidate_elastic_price_snaps_displayed_min_boundary_to_ozon_price():
    # 14.30% is the two-decimal display of the exact 14.296296...% boundary.
    assert calculate_candidate_elastic_price(
        Decimal("2700"), Decimal("14.30"), Decimal("2314"), Decimal("1913")
    ) == Decimal("2314")


def test_candidate_elastic_price_snaps_second_displayed_min_boundary_to_ozon_price():
    # 14.31% is the two-decimal display of the exact 14.305555...% boundary.
    assert calculate_candidate_elastic_price(
        Decimal("2160"), Decimal("14.31"), Decimal("1851"), Decimal("1530")
    ) == Decimal("1851")


def test_candidate_elastic_price_snaps_displayed_max_boundary_to_ozon_price():
    assert calculate_candidate_elastic_price(
        Decimal("2700"), Decimal("29.15"), Decimal("2314"), Decimal("1913")
    ) == Decimal("1913")


def test_candidate_elastic_price_accepts_exact_displayed_min_boundary():
    assert calculate_candidate_elastic_price(Decimal("2700"), Decimal("14.30"), Decimal("2314"), Decimal("1913")) == Decimal("2314.00")

def test_candidate_elastic_price_accepts_displayed_max_boundary():
    assert calculate_candidate_elastic_price(Decimal("2160"), Decimal("29.17"), Decimal("1851"), Decimal("1530")) == Decimal("1530.00")


def test_candidate_elastic_price_accepts_float_serialized_exact_minimum_boundaries():
    # The first two real products exposed a float-conversion defect:
    # str(float(exact_minimum)) can be a tiny amount below the exact Decimal,
    # even though the displayed percentage is correct.
    for price, minimum_price, maximum_price in (
        (Decimal("2700"), Decimal("2314"), Decimal("1913")),
        (Decimal("2160"), Decimal("1851"), Decimal("1530")),
    ):
        exact_min, _ = elastic_discount_bounds(price, minimum_price, maximum_price)
        serialized = Decimal(str(float(exact_min)))
        assert serialized < exact_min
        # UI state may still contain a float-derived value; the engine must
        # accept the value as the displayed activation boundary.
        assert calculate_candidate_elastic_price(
            price, serialized, minimum_price, maximum_price
        ) == minimum_price


def test_global_elastic_discount_requires_each_product_minimum():
    from app.services.price_engine import validate_global_elastic_discount

    rows = [
        {
            "product_id": "1", "name": "A", "base_price": Decimal("2700"),
            "price_min_elastic": Decimal("2314"), "price_max_elastic": Decimal("1913"),
            "min_discount": Decimal("14.296296296296296296"), "max_discount": Decimal("29.148148148148148148"),
        },
        {
            "product_id": "2", "name": "B", "base_price": Decimal("2160"),
            "price_min_elastic": Decimal("1851"), "price_max_elastic": Decimal("1530"),
            "min_discount": Decimal("14.305555555555555555"), "max_discount": Decimal("29.166666666666666666"),
        },
    ]
    errors, prices = validate_global_elastic_discount(rows, Decimal("14.30"))
    assert len(errors) == 1
    assert errors[0].startswith("2 — B:")
    assert prices == {"1": Decimal("2314")}


def test_global_elastic_discount_is_atomic_at_ui_plan_boundary():
    from app.services.price_engine import validate_global_elastic_discount

    rows = [
        {
            "product_id": "1", "name": "A", "base_price": Decimal("2700"),
            "price_min_elastic": Decimal("2314"), "price_max_elastic": Decimal("1913"),
            "min_discount": Decimal("14.296296296296296296"), "max_discount": Decimal("29.148148148148148148"),
        },
        {
            "product_id": "2", "name": "B", "base_price": Decimal("2160"),
            "price_min_elastic": Decimal("1851"), "price_max_elastic": Decimal("1530"),
            "min_discount": Decimal("14.305555555555555555"), "max_discount": Decimal("29.166666666666666666"),
        },
    ]
    errors, prices = validate_global_elastic_discount(rows, Decimal("15"))
    assert errors == []
    assert set(prices) == {"1", "2"}
    assert prices["1"] == Decimal("2295")
    assert prices["2"] == Decimal("1836")


def test_global_elastic_discount_uses_canonical_threshold_keys_from_ui():
    from app.services.price_engine import validate_global_elastic_discount
    rows = [{
        "product_id": "4467441547", "name": "A", "base_price": Decimal("1000"),
        "price_min_elastic": Decimal("903.3"), "price_max_elastic": Decimal("740"),
        "min_discount": Decimal("9.67"), "max_discount": Decimal("26.00"),
    }, {
        "product_id": "2979024682", "name": "B", "base_price": Decimal("1000"),
        "price_min_elastic": Decimal("860"), "price_max_elastic": Decimal("705"),
        "min_discount": Decimal("14.00"), "max_discount": Decimal("29.50"),
    }]
    errors, prices = validate_global_elastic_discount(rows, Decimal("16"))
    assert errors == []
    assert prices == {"4467441547": Decimal("840"), "2979024682": Decimal("840")}


def test_elastic_discount_bounds_preserve_negative_ozon_minimum():
    minimum, maximum = elastic_discount_bounds(
        Decimal("1000"), Decimal("1050"), Decimal("800")
    )
    assert minimum == Decimal("-5.00")
    assert maximum == Decimal("20.0")


def test_candidate_elastic_price_accepts_negative_ozon_discount_boundary():
    assert calculate_candidate_elastic_price(
        Decimal("1000"), Decimal("-5"), Decimal("1050"), Decimal("800")
    ) == Decimal("1050.00")


def test_candidate_elastic_price_accepts_negative_discount_inside_signed_range():
    assert calculate_candidate_elastic_price(
        Decimal("1000"), Decimal("-2.5"), Decimal("1050"), Decimal("800")
    ) == Decimal("1025.00")


def test_candidate_elastic_price_blocks_discount_below_negative_ozon_minimum():
    with pytest.raises(ValueError, match="диапазон Ozon Elastic Boosting"):
        calculate_candidate_elastic_price(
            Decimal("1000"), Decimal("-5.01"), Decimal("1050"), Decimal("800")
        )


def test_global_elastic_discount_accepts_signed_ozon_range():
    from app.services.price_engine import validate_global_elastic_discount

    rows = [{
        "product_id": "1",
        "name": "Negative minimum",
        "base_price": Decimal("1000"),
        "price_min_elastic": Decimal("1050"),
        "price_max_elastic": Decimal("800"),
        "min_discount": Decimal("-5"),
        "max_discount": Decimal("20"),
    }]
    errors, prices = validate_global_elastic_discount(rows, Decimal("-2.5"))
    assert errors == []
    assert prices == {"1": Decimal("1025.00")}
