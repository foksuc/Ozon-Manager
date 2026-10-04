from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


ROUNDING_QUANTA = {
    "Без округления": None,
    "0.01": Decimal("0.01"),
    "1": Decimal("1"),
    "10": Decimal("10"),
    "100": Decimal("100"),
}


def calculate_price(base: Decimal, operation: str, value: Decimal, rounding: str = "Без округления", safety_floor: Decimal | None = None) -> Decimal:
    """Deterministic application-side price calculation; no Ozon dependency."""
    base = Decimal(str(base))
    value = Decimal(str(value))
    if base <= 0:
        raise ValueError("Базовая цена должна быть положительной")
    if value < 0:
        raise ValueError("Значение операции не может быть отрицательным")
    if operation == "−N%":
        result = base * (Decimal("1") - value / Decimal("100"))
    elif operation == "+N%":
        result = base * (Decimal("1") + value / Decimal("100"))
    elif operation == "−N ₽":
        result = base - value
    elif operation == "+N ₽":
        result = base + value
    elif operation == "Вручную":
        result = value
    else:
        raise ValueError(f"Неизвестная операция: {operation}")
    floor = None
    if safety_floor is not None:
        floor = Decimal(str(safety_floor))
        if floor <= 0:
            raise ValueError("Safety Floor должен быть положительным")
    quantum = ROUNDING_QUANTA.get(rounding, "UNKNOWN")
    if quantum == "UNKNOWN":
        raise ValueError(f"Неизвестное округление: {rounding}")
    if quantum is not None:
        result = result.quantize(quantum, rounding=ROUND_HALF_UP)
    # A floor is a hard lower bound. It must remain effective after rounding;
    # otherwise e.g. a floor of 2314 rounded to 100 could become 2300.
    if floor is not None:
        result = max(result, floor)
    if result <= 0:
        raise ValueError("Расчёт дал неположительную цену")
    return result


def elastic_discount_bounds(
    price: Decimal,
    price_min_elastic: Decimal | None,
    price_max_elastic: Decimal | None,
) -> tuple[Decimal, Decimal]:
    """Return the discount interval required by Ozon Elastic Boosting thresholds.

    ``price_min_elastic`` is the highest price at which the candidate can enter
    the elastic range; ``price_max_elastic`` is the deeper target threshold.
    The returned values are percentages calculated from the current product
    price, not a hard-coded application limit.
    """
    price = Decimal(str(price))
    minimum_price = None if price_min_elastic is None else Decimal(str(price_min_elastic))
    maximum_price = None if price_max_elastic is None else Decimal(str(price_max_elastic))
    if price <= 0:
        raise ValueError("Цена должна быть положительной")
    if minimum_price is None or maximum_price is None:
        raise ValueError("Ozon не вернул price_min_elastic и price_max_elastic; расчёт ADD заблокирован")
    if minimum_price <= 0 or maximum_price <= 0:
        raise ValueError("price_min_elastic и price_max_elastic должны быть положительными")
    if minimum_price > price:
        raise ValueError("price_min_elastic выше текущей цены; диапазон скидки некорректен")
    if maximum_price > minimum_price:
        raise ValueError("price_max_elastic выше price_min_elastic; диапазон скидки некорректен")

    min_discount = (price - minimum_price) / price * Decimal("100")
    max_discount = (price - maximum_price) / price * Decimal("100")
    return max(Decimal("0"), min_discount), max(Decimal("0"), max_discount)


def calculate_candidate_elastic_price(
    price: Decimal,
    discount_percent: Decimal,
    price_min_elastic: Decimal | None,
    price_max_elastic: Decimal | None,
    rounding: str = "Без округления",
) -> Decimal:
    """Calculate and validate a candidate ADD price against Ozon thresholds."""
    price = Decimal(str(price))
    discount_percent = Decimal(str(discount_percent))
    min_discount, max_discount = elastic_discount_bounds(price, price_min_elastic, price_max_elastic)
    # The displayed percentages are rounded to two decimals. Validate the
    # resulting monetary value against Ozon's exact thresholds instead of
    # comparing the rounded percentage itself. This allows e.g. 29.15% when
    # the exact calculated boundary is 29.148148...%.
    rounded_min_display = min_discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rounded_max_display = max_discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    min_price = Decimal(str(price_min_elastic))
    max_price = Decimal(str(price_max_elastic))

    # The UI exposes the boundary to two decimals. A displayed boundary is a
    # user-facing alias for the exact Ozon monetary threshold, not a request
    # to recalculate that threshold from the rounded percentage.
    boundary_epsilon = Decimal("0.000000000000001")
    if min_discount - boundary_epsilon <= discount_percent <= rounded_min_display:
        result = min_price
    elif max_discount - boundary_epsilon <= discount_percent <= rounded_max_display:
        result = max_price
    else:
        result = calculate_price(price, "−N%", discount_percent, rounding)

    # Eliminate harmless Decimal representation noise at the currency scale.
    # Never silently clamp a real out-of-range discount: only the two displayed
    # boundary aliases above may map directly to Ozon's exact thresholds.
    result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if result > min_price or result < max_price:
        raise ValueError(
            "Рассчитанная цена не попадает в диапазон Ozon Elastic Boosting: "
            f"{price_max_elastic}–{price_min_elastic} ₽"
        )
    return result


def validate_global_elastic_discount(
    rows: list[dict], discount_percent: Decimal,
) -> tuple[list[str], dict[str, Decimal]]:
    """Validate one discount against every product's individual Elastic range.

    This is application/domain logic and deliberately has no Ozon transport dependency.
    ``rows`` must provide: product_id, name, base_price, price_min_elastic,
    price_max_elastic, min_discount and max_discount.
    """
    discount_percent = Decimal(str(discount_percent))
    errors: list[str] = []
    prices: dict[str, Decimal] = {}
    for row in rows:
        pid = str(row["product_id"])
        name = str(row.get("name") or "UNKNOWN")
        label = f"{pid} — {name}"
        minimum = Decimal(str(row["min_discount"]))
        maximum = Decimal(str(row["max_discount"]))
        if discount_percent < minimum:
            errors.append(
                f"{label}: задано {discount_percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%, "
                f"минимально допустимо {minimum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
            )
            continue
        if discount_percent > maximum:
            errors.append(
                f"{label}: задано {discount_percent.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%, "
                f"максимально допустимо {maximum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
            )
            continue
        try:
            prices[pid] = calculate_candidate_elastic_price(
                Decimal(str(row["base_price"])),
                discount_percent,
                Decimal(str(row["price_min_elastic"])),
                Decimal(str(row["price_max_elastic"])),
                "Без округления",
            )
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    return errors, prices


def calculate_elastic_boost_price(
    price: Decimal,
    boost_percent: Decimal,
    rounding: str = "Без округления",
    max_discount_percent: Decimal = Decimal("18"),
) -> Decimal:
    """Calculate Elastic Boosting price from the product ``Цена``.

    The UI exposes a 1%..18% discount slider. The business safety rule is
    independent of Ozon's ``max_action_price``: the resulting price may not
    be lower than 82% of the source ``Цена`` (maximum 18% discount).

    ``max_action_price`` is deliberately not used as a lower bound here. It is
    a separate informational/API field shown in the tables as
    ``Ограничение для акции``.
    """
    price = Decimal(str(price))
    boost_percent = Decimal(str(boost_percent))
    max_discount_percent = Decimal(str(max_discount_percent))
    if price <= 0:
        raise ValueError("Цена должна быть положительной")
    if max_discount_percent <= 0:
        raise ValueError("Максимальная скидка должна быть положительной")
    if boost_percent < Decimal("1") or boost_percent > max_discount_percent:
        raise ValueError(
            f"Скидка Elastic Boosting должна быть от 1% до {format(max_discount_percent, 'f').rstrip('0').rstrip('.') }%"
        )
    result = calculate_price(price, "−N%", boost_percent, rounding)
    minimum_price = price * (Decimal("1") - max_discount_percent / Decimal("100"))
    return max(result, minimum_price)
