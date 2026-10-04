from decimal import Decimal
import pytest
from app.domain.models import OperationStatus
from app.domain.state_machine import transition
from app.domain.validation import parse_action_price, TARGET_BOOST_BLOCKED_MESSAGE, reject_target_boost


def test_invalid_direct_transition_is_blocked():
    with pytest.raises(ValueError):
        transition(OperationStatus.DRAFT, OperationStatus.RUNNING)


def test_valid_mutation_gate_transitions():
    s = OperationStatus.DRAFT
    for target in [OperationStatus.PREVIEWED, OperationStatus.FRESH_CHECKED, OperationStatus.SNAPSHOTTED, OperationStatus.CONFIRMED, OperationStatus.RUNNING]:
        s = transition(s, target)
    assert s == OperationStatus.RUNNING


def test_action_price_validation():
    assert parse_action_price("1999.05") == Decimal("1999.05")
    with pytest.raises(ValueError): parse_action_price("0")
    with pytest.raises(ValueError): parse_action_price("-1")


def test_target_boost_is_blocked():
    with pytest.raises(ValueError, match="Target Boost"):
        reject_target_boost(25)
    assert "action_price" in TARGET_BOOST_BLOCKED_MESSAGE
