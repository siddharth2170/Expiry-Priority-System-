from dataclasses import dataclass


@dataclass
class Foodbank:
    foodbank_id: str
    name: str
    contact: str
    address: str
