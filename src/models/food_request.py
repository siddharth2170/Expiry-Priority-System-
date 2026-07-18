from dataclasses import dataclass
from datetime import date


@dataclass
class FoodRequest:
    request_id: str
    foodbank_id: str
    category: str
    quantity: int
    request_date: date