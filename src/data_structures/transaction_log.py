from __future__ import annotations

from typing import Iterable

from src.models import DonationRecord


class TransactionLog:
    """Append-only log of confirmed donations (rescued food).

    Backed by a plain ``list`` used as raw storage. Each entry is a
    ``DonationRecord`` describing what was rescued, how much, and between which
    banks. Because a confirmed donation is a terminal "saved" event, this log is
    the sole record that a batch was rescued -- there is no per-item saved flag.
    Grouping by source bank lets us count how much each bank has rescued.
    """

    def __init__(self) -> None:
        self._records: list[DonationRecord] = []

    def __len__(self) -> int:
        return len(self._records)

    def append(self, record: DonationRecord) -> None:
        self._records.append(record)

    def all(self) -> list[DonationRecord]:
        return list(self._records)

    def total_rescued(self) -> int:
        """Total units of food rescued across every donation."""
        return sum(record.quantity for record in self._records)

    def by_source(self) -> dict[str, list[DonationRecord]]:
        """Donations grouped by the bank that gave the food."""
        groups: dict[str, list[DonationRecord]] = {}
        for record in self._records:
            groups.setdefault(record.from_foodbank_id, []).append(record)
        return groups

    def rescued_units_by_source(self) -> dict[str, int]:
        """Units rescued per source bank -- the "food saved" leaderboard."""
        totals: dict[str, int] = {}
        for record in self._records:
            totals[record.from_foodbank_id] = (
                totals.get(record.from_foodbank_id, 0) + record.quantity
            )
        return totals

    def for_source(self, foodbank_id: str) -> list[DonationRecord]:
        return [r for r in self._records if r.from_foodbank_id == foodbank_id]

    @classmethod
    def from_records(cls, records: Iterable[DonationRecord]) -> "TransactionLog":
        """Build a log view over an existing list of donation records."""
        log = cls()
        for record in records:
            log.append(record)
        return log
