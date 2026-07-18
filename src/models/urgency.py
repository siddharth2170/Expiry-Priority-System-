from enum import IntEnum


class Urgency(IntEnum):
    """Shortage severity for a food request.

    Values are ordered so that a lower value means higher priority, which lets
    the enum's value be used directly as a priority-queue rank.
    """

    CRITICAL = 0
    LOW = 1
    ROUTINE = 2

    @property
    def label(self) -> str:
        return {
            Urgency.CRITICAL: "Critical (out of stock)",
            Urgency.LOW: "Low (running short)",
            Urgency.ROUTINE: "Routine (restocking)",
        }[self]
