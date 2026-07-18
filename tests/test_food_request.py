import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import FoodRequest, Urgency


def make_request(quantity, urgency=Urgency.ROUTINE):
    return FoodRequest(
        request_id="REQ-1",
        foodbank_id="FB001",
        category="Bakery",
        quantity=quantity,
        urgency=urgency,
    )


class TestFoodRequest(unittest.TestCase):
    def test_valid_request_constructs(self):
        req = make_request(5, Urgency.CRITICAL)
        self.assertEqual(req.quantity, 5)
        self.assertEqual(req.urgency, Urgency.CRITICAL)
        self.assertEqual(req.submitted_at, date.today())

    def test_zero_quantity_rejected(self):
        with self.assertRaises(ValueError):
            make_request(0)

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValueError):
            make_request(-5)

    def test_urgency_orders_as_priority_rank(self):
        # Lower value = higher priority, so the enum value can be a queue rank.
        self.assertLess(Urgency.CRITICAL, Urgency.LOW)
        self.assertLess(Urgency.LOW, Urgency.ROUTINE)
        self.assertEqual(int(Urgency.CRITICAL), 0)

    def test_urgency_sort_by_value(self):
        order = sorted([Urgency.ROUTINE, Urgency.CRITICAL, Urgency.LOW])
        self.assertEqual(order, [Urgency.CRITICAL, Urgency.LOW, Urgency.ROUTINE])


if __name__ == "__main__":
    unittest.main()
