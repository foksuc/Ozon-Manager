from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TARGET_BOOST_BLOCKED_MESSAGE = (
    "Управление Target Boost напрямую не поддерживается текущим подтверждённым API-контрактом MVP. "
    "Для операции необходимо задать конкретный action_price."
)


def parse_action_price(value: str | int | float | Decimal) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("action_price должен быть числом")
    if not price.is_finite() or price <= 0:
        raise ValueError("action_price должен быть положительным конечным числом")
    return price


def reject_target_boost(_: object) -> None:
    raise ValueError(TARGET_BOOST_BLOCKED_MESSAGE)


def action_price_matches_requested(requested: Decimal, actual: Decimal) -> bool:
    """Return whether a read-back action price confirms the requested price.

    Ozon may return an action price rounded to whole RUB.  For example, a
    requested 18% discount from 1080 RUB is 885.60 RUB, while the observed
    read-back is 886 RUB (an effective 17.962962...% discount).  This is the
    same requested price for reconciliation purposes; it is not a new status
    or a separate "normalized" result.
    """
    requested = Decimal(str(requested))
    actual = Decimal(str(actual))
    return actual == requested or actual == requested.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
