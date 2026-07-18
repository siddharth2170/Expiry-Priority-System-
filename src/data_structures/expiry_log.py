from __future__ import annotations

from typing import Iterable

from src.models import Batch, Foodbank, FoodItem

# An expired entry is one expired batch of a product: (product, batch).
Entry = tuple[FoodItem, "Batch"]


class ExpiryLog:
    """Append-only log of expired food batches, tagged by their foodbank.

    Backed by a plain ``list`` used purely as raw storage (append-only). Each
    entry is a ``(product, batch)`` pair: the product carries the name and
    ``foodbank_id`` while the batch carries the expired ``quantity`` and
    ``expiry_date`` -- so we know exactly what and how much expired, and where.
    """

    def __init__(self) -> None:
        self._records: list[Entry] = []

    def __len__(self) -> int:
        return len(self._records)

    def append(self, item: FoodItem, batch: Batch) -> None:
        self._records.append((item, batch))

    def all(self) -> list[Entry]:
        return list(self._records)

    def for_foodbank(self, foodbank_id: str) -> list[Entry]:
        return [(i, b) for (i, b) in self._records if i.foodbank_id == foodbank_id]

    def grouped_by_foodbank(self) -> dict[str, list[Entry]]:
        groups: dict[str, list[Entry]] = {}
        for item, batch in self._records:
            groups.setdefault(item.foodbank_id, []).append((item, batch))
        return groups

    def total_expired_quantity(self) -> int:
        return sum(batch.quantity for _, batch in self._records)

    @classmethod
    def from_foodbanks(cls, foodbanks: Iterable[Foodbank]) -> "ExpiryLog":
        """Sweep every foodbank's stock and log each expired batch."""
        log = cls()
        for foodbank in foodbanks:
            for item in foodbank.food_items:
                for batch in item.expired_batches():
                    log.append(item, batch)
        return log
