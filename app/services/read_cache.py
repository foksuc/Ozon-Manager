from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass
class ReadDataCache:
    """Per-session cache for read-only Ozon data.

    This cache intentionally contains no credentials and is scoped to the
    Streamlit session. It prevents widget-triggered reruns from repeating
    network reads while keeping an explicit refresh path.
    """

    promotions: list[Any] | None = None
    promotion_loaded_at: float | None = None
    selected_action_id: str | None = None
    action_loaded_at: float | None = None
    participants: list[Any] | None = None
    candidate_rows: list[dict] | None = None
    auto_add_rows: list[dict] | None = None
    auto_add_date: str | None = None
    names: dict[str, str] = field(default_factory=dict)
    skus: dict[str, str] = field(default_factory=dict)
    name_misses: set[str] = field(default_factory=set)
    sku_misses: set[str] = field(default_factory=set)

    def clear(self) -> None:
        self.promotions = None
        self.promotion_loaded_at = None
        self.selected_action_id = None
        self.action_loaded_at = None
        self.participants = None
        self.candidate_rows = None
        self.auto_add_rows = None
        self.auto_add_date = None
        self.names.clear()
        self.skus.clear()
        self.name_misses.clear()
        self.sku_misses.clear()

    def invalidate_action(self) -> None:
        self.selected_action_id = None
        self.action_loaded_at = None
        self.participants = None
        self.candidate_rows = None
        self.auto_add_rows = None
        self.auto_add_date = None

    def needs_promotion_refresh(self, ttl_seconds: float) -> bool:
        if self.promotions is None or self.promotion_loaded_at is None:
            return True
        return monotonic() - self.promotion_loaded_at >= ttl_seconds

    def mark_promotions(self, promotions: list[Any]) -> None:
        self.promotions = promotions
        self.promotion_loaded_at = monotonic()

    def mark_action(self, action_id: str, participants: list[Any], candidate_rows: list[dict]) -> None:
        self.selected_action_id = str(action_id)
        self.action_loaded_at = monotonic()
        self.participants = participants
        self.candidate_rows = candidate_rows

    def mark_auto_add(self, action_id: str, auto_add_date: str, rows: list[dict]) -> None:
        self.selected_action_id = str(action_id)
        self.auto_add_date = str(auto_add_date)
        self.auto_add_rows = rows

    def has_auto_add_data(self, action_id: str, ttl_seconds: float | None = None) -> bool:
        if self.selected_action_id != str(action_id):
            return False
        return self.auto_add_rows is not None and bool(self.auto_add_date)

    def has_action_data(self, action_id: str, ttl_seconds: float | None = None) -> bool:
        if self.selected_action_id != str(action_id):
            return False
        if self.participants is None or self.candidate_rows is None:
            return False
        if ttl_seconds is not None and (self.action_loaded_at is None or monotonic() - self.action_loaded_at >= ttl_seconds):
            return False
        return True
