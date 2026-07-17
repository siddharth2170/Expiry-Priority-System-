from dataclasses import dataclass


@dataclass
class Recipient:
    recipient_id: str
    name: str
    recipient_type: str      # Food Bank / Shelter
    contact: str
    address: str