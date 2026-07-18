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
