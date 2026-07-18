from dataclasses import dataclass, field
from datetime import date

from .urgency import Urgency


@dataclass
class FoodRequest:
    request_id: str
    foodbank_id: str
    category: str
    quantity: int
    urgency: Urgency
    submitted_at: date = field(default_factory=date.today)

    def __post_init__(self) -> None:
        # A request for zero or a negative amount is meaningless; reject it at
        # construction so bad data can never enter the queue.
        if self.quantity <= 0:
            raise ValueError("FoodRequest.quantity must be a positive integer")
