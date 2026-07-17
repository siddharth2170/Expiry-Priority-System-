from dataclasses import dataclass
from datetime import date


@dataclass
class DonationRecord:
    record_id: str
    food_id: str
    donor_id: str
    recipient_id: str
    quantity: int
    donation_date: date
    status: str