import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.expiry_log import ExpiryLog
from src.models import Batch, Foodbank, FoodItem

TODAY = date.today()


def item(food_id, name, foodbank_id, batches):
    return FoodItem(
        food_id=food_id,
        name=name,
        category="Bakery",
        unit="Packets",
        foodbank_id=foodbank_id,
        storage_type="Room Temperature",
        batches=batches,
    )


def foodbank(fb_id, food_items):
    return Foodbank(
        foodbank_id=fb_id,
        name=fb_id,
        contact="x",
        address="y",
        latitude=0.0,
        longitude=0.0,
        food_items=food_items,
    )


class TestExpiryLog(unittest.TestCase):
    def setUp(self):
        # FB001: Bagels with one active + one expired batch (same product name).
        bagels = item("F1", "Bagels", "FB001", [
            Batch(TODAY + timedelta(days=2), 30),
            Batch(TODAY - timedelta(days=1), 15),
        ])
        # FB002: Sandwiches fully expired.
        sandwiches = item("F2", "Sandwiches", "FB002", [
            Batch(TODAY - timedelta(days=3), 12),
        ])
        # FB002: fresh milk, nothing expired.
        milk = item("F3", "Milk", "FB002", [Batch(TODAY + timedelta(days=5), 40)])
        self.banks = [foodbank("FB001", [bagels]), foodbank("FB002", [sandwiches, milk])]

    def test_records_only_expired_batches(self):
        log = ExpiryLog.from_foodbanks(self.banks)
        self.assertEqual(len(log), 2)
        names = sorted(it.name for it, _ in log.all())
        self.assertEqual(names, ["Bagels", "Sandwiches"])

    def test_expired_batch_keeps_product_name(self):
        # The expired batch is logged under the real product name, not a variant.
        log = ExpiryLog.from_foodbanks(self.banks)
        bagel_entries = [b for it, b in log.all() if it.name == "Bagels"]
        self.assertEqual(len(bagel_entries), 1)
        self.assertEqual(bagel_entries[0].quantity, 15)

    def test_total_expired_quantity(self):
        log = ExpiryLog.from_foodbanks(self.banks)
        self.assertEqual(log.total_expired_quantity(), 27)  # 15 + 12

    def test_grouped_by_foodbank(self):
        log = ExpiryLog.from_foodbanks(self.banks)
        grouped = log.grouped_by_foodbank()
        self.assertEqual(set(grouped), {"FB001", "FB002"})
        self.assertEqual(len(grouped["FB001"]), 1)
        self.assertEqual(len(grouped["FB002"]), 1)

    def test_for_foodbank_filters(self):
        log = ExpiryLog.from_foodbanks(self.banks)
        self.assertEqual(len(log.for_foodbank("FB001")), 1)
        self.assertEqual(log.for_foodbank("NONE"), [])

    def test_empty_when_nothing_expired(self):
        fresh = foodbank("FB003", [item("F4", "Rice", "FB003", [Batch(TODAY + timedelta(days=90), 200)])])
        log = ExpiryLog.from_foodbanks([fresh])
        self.assertEqual(len(log), 0)
        self.assertEqual(log.total_expired_quantity(), 0)

    def test_manual_append(self):
        log = ExpiryLog()
        it = item("F5", "Cake", "FB004", [Batch(TODAY - timedelta(days=1), 3)])
        log.append(it, it.batches[0])
        self.assertEqual(len(log), 1)


if __name__ == "__main__":
    unittest.main()
