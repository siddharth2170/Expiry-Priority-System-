from __future__ import annotations

from dataclasses import dataclass, field

from src.models import FoodItem, FoodRequest


@dataclass
class MatchCandidate:
    """One possible way to serve a request: a source bank donating one product.

    A transient result produced by the matching engine (not a persisted domain
    entity). ``food_item`` is the soonest-to-expire product of the requested
    category held by ``source_id``; ``fill_quantity`` is how much of the request
    it can cover (``min(available, requested)``, so a partial fill is possible).
    """

    request: FoodRequest
    source_id: str
    dest_id: str
    food_item: FoodItem
    fill_quantity: int
    days_to_expiry: int
    distance_km: float
    route: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def is_partial(self) -> bool:
        return self.fill_quantity < self.request.quantity
