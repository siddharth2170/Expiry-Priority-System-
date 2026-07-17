from dataclasses import dataclass


@dataclass
class Donor:
    donor_id: str
    name: str
    organization: str
    contact: str
    address: str