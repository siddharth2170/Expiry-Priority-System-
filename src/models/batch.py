from dataclasses import dataclass
from datetime import date


@dataclass
class Batch:
    """A quantity of a food product that shares a single expiry date.

    A product (FoodItem) holds one or more batches, so different amounts can
    expire at different times.
    """

    expiry_date: date
    quantity: int

    def is_expired(self) -> bool:
        return date.today() > self.expiry_date
