from __future__ import annotations

from src.data_structures.priority_queue import PriorityQueue
from src.models import Batch, Foodbank, FoodItem

# An inventory line is one batch of a product: (product, batch).
Line = tuple[FoodItem, "Batch"]


class Inventory:
    """A foodbank's stock, indexed for expiry-priority retrieval per batch.

    The unit of expiry is a *batch*, not a product, so a product with several
    batches contributes several lines. Storage is split in two:

    - ``_heaps``: one min-heap per category holding ``(product, batch)`` lines
      ordered by batch expiry date, so the soonest-to-spoil batch is on top.
    - ``_by_id``: a ``food_id -> FoodItem`` map for O(1) lookup and removal.

    Removal is *lazy*: ``remove`` drops the id from ``_by_id``; stale or expired
    heap lines are skipped and discarded when they surface (see
    ``_discard_invalid``).
    """

    def __init__(self) -> None:
        self._heaps: dict[str, PriorityQueue] = {}
        self._by_id: dict[str, FoodItem] = {}

    def __len__(self) -> int:
        return len(self._by_id)

    def add(self, item: FoodItem) -> None:
        self._by_id[item.food_id] = item
        # One heap per category so "most urgent in category X" is a cheap lookup.
        heap = self._heaps.setdefault(item.category, PriorityQueue())
        # Push every batch (even already-expired ones): the expiry date as an
        # ordinal is the priority key, and invalid lines are filtered lazily
        # when they reach the top rather than being screened out here.
        for batch in item.batches:
            heap.push((item, batch), batch.expiry_date.toordinal())

    def remove(self, food_id: str) -> bool:
        # Lazy deletion: forget the id now; its heap lines are purged on the next
        # peek/pop that surfaces them (see _discard_invalid).
        return self._by_id.pop(food_id, None) is not None

    def get(self, food_id: str) -> FoodItem | None:
        return self._by_id.get(food_id)

    def peek_most_urgent(self, category: str | None = None) -> Line | None:
        """Return the soonest-to-expire usable line without removing it.

        With ``category`` given, looks only in that category; otherwise scans
        every category and returns the most urgent line overall.
        """
        if category is not None:
            heap = self._heaps.get(category)
            if heap is None:
                return None
            # Purge stale/expired lines first so the top is guaranteed usable.
            self._discard_invalid(heap)
            return None if heap.is_empty() else heap.peek()

        # No category given: take each category's current best, then compare
        # those winners on batch expiry to find the single most urgent line.
        best: Line | None = None
        for heap in self._heaps.values():
            self._discard_invalid(heap)
            if not heap.is_empty():
                top = heap.peek()
                # top[1] is the batch; order by its expiry date, earliest wins.
                if best is None or top[1].expiry_date < best[1].expiry_date:
                    best = top
        return best

    def pop_most_urgent(self, category: str | None = None) -> Line | None:
        """Remove and return the soonest-to-expire usable line."""
        if category is None:
            # Find the globally most urgent line first, then pop from *its*
            # category's heap (target[0] is the product, which carries category).
            target = self.peek_most_urgent(None)
            if target is None:
                return None
            category = target[0].category

        heap = self._heaps.get(category)
        if heap is None:
            return None
        self._discard_invalid(heap)
        if heap.is_empty():
            return None
        return heap.pop()

    def by_category(self, category: str) -> list[Line]:
        """Usable lines in a category, soonest-to-expire first (read-only)."""
        # active_batches() drops expired batches at read time (evaluated live
        # against today's date), so this reflects current stock without mutating.
        return self._ordered(
            (item, batch)
            for item in self._by_id.values()
            if item.category == category and item.is_available()
            for batch in item.active_batches()
        )

    def items(self) -> list[Line]:
        """All usable lines across categories, soonest-to-expire first."""
        # Read from _by_id (source of truth) rather than the heaps, so this view
        # never surfaces lines that were only lazily deleted from a heap.
        return self._ordered(
            (item, batch)
            for item in self._by_id.values()
            if item.is_available()
            for batch in item.active_batches()
        )

    def total_quantity(self, category: str) -> int:
        # Sum only active batches: expired quantity is excluded from usable stock.
        return sum(
            batch.quantity
            for item in self._by_id.values()
            if item.category == category and item.is_available()
            for batch in item.active_batches()
        )

    def categories(self) -> list[str]:
        return sorted(
            {
                item.category
                for item in self._by_id.values()
                if item.is_available() and item.active_batches()
            }
        )

    def _is_current(self, item: FoodItem) -> bool:
        # True only if this exact object is still the one indexed under its id
        # (guards against removed or superseded products lingering in a heap).
        return self._by_id.get(item.food_id) is item

    def _discard_invalid(self, heap: PriorityQueue) -> None:
        """Drop stale/expired lines from the top of a heap."""
        while not heap.is_empty():
            item, batch = heap.peek()
            if not self._is_current(item) or not item.is_available():
                heap.pop()  # product removed, superseded, or unavailable
                continue
            if batch.is_expired():
                heap.pop()  # skip the expired batch; other batches may be good
                continue
            break

    @staticmethod
    def _ordered(lines) -> list[Line]:
        # Sort by expiry using a throwaway min-heap keyed on the expiry ordinal:
        # loading then draining it yields the lines in soonest-first order.
        pq = PriorityQueue()
        for item, batch in lines:
            pq.push((item, batch), batch.expiry_date.toordinal())
        return [pq.pop() for _ in range(len(pq))]

    @classmethod
    def from_foodbank(cls, foodbank: Foodbank) -> "Inventory":
        inventory = cls()
        for item in foodbank.food_items:
            inventory.add(item)
        return inventory
