from dataclasses import dataclass
from datetime import date


@dataclass
class FoodItem:
    food_id: str
    name: str
    category: str
    quantity: int
    unit: str
    expiry_date: date
    foodbank_id: str
    storage_type: str
    status: str = "Available"

    def is_available(self):
        return self.status == "Available"

    def is_expired(self):
        return date.today() > self.expiry_date