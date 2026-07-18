from dataclasses import dataclass
from datetime import date


@dataclass
class DonationRecord:
    record_id: str
    food_id: str
    from_foodbank_id: str
    to_foodbank_id: str
    quantity: int
    transfer_date: date
    status: str