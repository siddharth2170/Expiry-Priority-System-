from __future__ import annotations

from datetime import date

from src.data_structures.priority_queue import PriorityQueue
from src.models import FoodRequest


class RequestQueue:
    """Orders food requests by a weighted urgency-plus-aging score.

    Each request gets a numeric score; the smallest score is the most urgent
    (served first by the underlying min-heap)::

        score = urgency.value * URGENCY_WEIGHT - age_days * AGE_WEIGHT

    Because ``Urgency`` is ordered CRITICAL(0) < LOW(1) < ROUTINE(2), a lower
    urgency value already means a smaller score. Subtracting the waiting time
    lets a long-neglected request climb: with the defaults below, every
    ``URGENCY_WEIGHT`` days of waiting is worth one urgency level, so a request
    ignored long enough eventually overtakes fresher, higher-urgency ones.

    Scores are computed when a request is added and stored in the heap, so they
    grow stale as real days pass. ``rebuild`` recomputes every score against the
    current date to re-sync the heap; ``pending`` always recomputes and is
    therefore accurate regardless of staleness. ``_by_id`` is the source of
    truth, and removal is lazy (an id is forgotten and its heap entry skipped
    when it surfaces), mirroring the Inventory.
    """

    # A whole urgency level is worth this many days of waiting.
    URGENCY_WEIGHT = 30
    AGE_WEIGHT = 1

    def __init__(self) -> None:
        self._pq = PriorityQueue()
        self._by_id: dict[str, FoodRequest] = {}

    def __len__(self) -> int:
        return len(self._by_id)

    def is_empty(self) -> bool:
        return not self._by_id

    def priority_score(self, request: FoodRequest, today: date | None = None) -> int:
        today = today or date.today()
        age_days = max(0, (today - request.submitted_at).days)
        return request.urgency.value * self.URGENCY_WEIGHT - age_days * self.AGE_WEIGHT

    def add(self, request: FoodRequest, today: date | None = None) -> None:
        self._by_id[request.request_id] = request
        self._pq.push(request.request_id, self.priority_score(request, today))

    def remove(self, request_id: str) -> bool:
        # Lazy deletion: forget the id; its heap entry is skipped when it rises.
        return self._by_id.pop(request_id, None) is not None

    def get(self, request_id: str) -> FoodRequest | None:
        return self._by_id.get(request_id)

    def peek_most_urgent(self) -> FoodRequest | None:
        """Return the most urgent request by stored score (call rebuild to refresh)."""
        self._discard_invalid()
        if self._pq.is_empty():
            return None
        return self._by_id[self._pq.peek()]

    def pop_most_urgent(self) -> FoodRequest | None:
        """Remove and return the most urgent request (it is served)."""
        self._discard_invalid()
        if self._pq.is_empty():
            return None
        request_id = self._pq.pop()
        return self._by_id.pop(request_id, None)

    def pending(self, today: date | None = None) -> list[FoodRequest]:
        """All queued requests, most-urgent first, scored against ``today``.

        Always recomputes scores, so the order is correct even if the heap has
        gone stale since the requests were added.
        """
        scratch = PriorityQueue()
        for request in self._by_id.values():
            scratch.push(request.request_id, self.priority_score(request, today))
        return [self._by_id[scratch.pop()] for _ in range(len(scratch))]

    def rebuild(self, today: date | None = None) -> None:
        """Recompute every score against ``today`` and rebuild the heap.

        Call this when time has passed so the stored scores reflect current
        waiting times (aging), keeping peek/pop accurate.
        """
        self._pq = PriorityQueue()
        for request in self._by_id.values():
            self._pq.push(request.request_id, self.priority_score(request, today))

    def _discard_invalid(self) -> None:
        # Drop heap entries whose request has been removed from the source map.
        while not self._pq.is_empty() and self._pq.peek() not in self._by_id:
            self._pq.pop()

    @classmethod
    def from_requests(cls, requests, today: date | None = None) -> "RequestQueue":
        queue = cls()
        for request in requests:
            queue.add(request, today)
        return queue
