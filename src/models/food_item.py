from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .batch import Batch


@dataclass
class FoodItem:
    """A food product held by a foodbank.

    The stable ``food_id`` identifies the product (and its name). Actual stock
    lives in ``batches``, each with its own expiry date and quantity, so the
    same product can have different amounts expiring at different times.
    """

    food_id: str
    name: str
    category: str
    unit: str
    foodbank_id: str
    storage_type: str
    batches: list[Batch] = field(default_factory=list)
    status: str = "Available"

    def is_available(self) -> bool:
        return self.status == "Available"

    def active_batches(self) -> list[Batch]:
        return [b for b in self.batches if not b.is_expired()]

    def expired_batches(self) -> list[Batch]:
        return [b for b in self.batches if b.is_expired()]

    def total_quantity(self) -> int:
        return sum(b.quantity for b in self.active_batches())

    def earliest_expiry(self) -> date | None:
        return min((b.expiry_date for b in self.active_batches()), default=None)

    def is_expired(self) -> bool:
        # The product is "expired" (nothing usable) when no batch is still good.
        return not self.active_batches()
