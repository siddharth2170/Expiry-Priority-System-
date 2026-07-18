from dataclasses import dataclass, field

from .food_item import FoodItem


@dataclass
class Foodbank:
    foodbank_id: str
    name: str
    contact: str
    address: str
    latitude: float
    longitude: float
    food_items: list[FoodItem] = field(default_factory=list)
