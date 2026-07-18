import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.inventory import Inventory
from src.models import Batch, Foodbank, FoodItem

TODAY = date.today()


def days(n):
    return TODAY + timedelta(days=n)


def item(food_id, name, category, batches, unit="Packets"):
    return FoodItem(
        food_id=food_id,
        name=name,
        category=category,
        unit=unit,
        foodbank_id="FB001",
        storage_type="Room Temperature",
        batches=batches,
    )


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.bread = item("F1", "Bread", "Bakery", [
            Batch(days(2), 30),
            Batch(days(6), 25),   # same product, later batch
        ])
        self.milk = item("F2", "Milk", "Dairy", [Batch(days(4), 60)], unit="Liters")
        self.yogurt = item("F3", "Yogurt", "Dairy", [Batch(days(-2), 20)])  # fully expired
        self.inv = Inventory()
        for it in (self.bread, self.milk, self.yogurt):
            self.inv.add(it)

    def test_items_sorted_by_expiry(self):
        expiries = [batch.expiry_date for _, batch in self.inv.items()]
        self.assertEqual(expiries, sorted(expiries))

    def test_same_product_yields_one_row_per_active_batch(self):
        names = [it.name for it, _ in self.inv.items()]
        self.assertEqual(names.count("Bread"), 2)

    def test_fully_expired_product_excluded(self):
        names = [it.name for it, _ in self.inv.items()]
        self.assertNotIn("Yogurt", names)
        # ...and it should not count toward category totals either.
        self.assertEqual(self.inv.total_quantity("Dairy"), 60)

    def test_peek_most_urgent_overall(self):
        it, batch = self.inv.peek_most_urgent()
        self.assertEqual(it.name, "Bread")
        self.assertEqual(batch.expiry_date, days(2))
        # peek must not remove anything
        self.assertEqual(len(self.inv.items()), 3)

    def test_pop_most_urgent_drains_in_expiry_order(self):
        # pop_most_urgent is a heap primitive: each call returns the next
        # soonest-to-expire active batch, and the expired yogurt is never served.
        popped = []
        while True:
            line = self.inv.pop_most_urgent()
            if line is None:
                break
            popped.append(line[1].expiry_date)
        self.assertEqual(popped, [days(2), days(4), days(6)])

    def test_by_category_filters_and_orders(self):
        bakery = self.inv.by_category("Bakery")
        self.assertEqual({it.name for it, _ in bakery}, {"Bread"})
        self.assertEqual([b.expiry_date for _, b in bakery], [days(2), days(6)])

    def test_total_quantity_active_only(self):
        self.assertEqual(self.inv.total_quantity("Bakery"), 55)  # 30 + 25

    def test_remove_is_lazy_but_excluded_from_reads(self):
        self.assertTrue(self.inv.remove("F1"))
        names = [it.name for it, _ in self.inv.items()]
        self.assertNotIn("Bread", names)
        # popping should now surface Milk (next soonest), skipping removed lines
        it, _ = self.inv.pop_most_urgent()
        self.assertEqual(it.name, "Milk")

    def test_remove_unknown_returns_false(self):
        self.assertFalse(self.inv.remove("NOPE"))

    def test_peek_unknown_category_returns_none(self):
        self.assertIsNone(self.inv.peek_most_urgent("Frozen"))

    def test_tie_on_same_expiry_keeps_both_and_is_deterministic(self):
        # Edge case: two active batches with identical expiry dates.
        tie = item("F9", "Buns", "Bakery", [Batch(days(1), 5), Batch(days(1), 7)])
        inv = Inventory()
        inv.add(tie)
        lines = inv.by_category("Bakery")
        self.assertEqual(len(lines), 2)
        # Stable order (insertion order preserved for equal priority).
        self.assertEqual([b.quantity for _, b in lines], [5, 7])

    def test_from_foodbank_builds_from_food_items(self):
        fb = Foodbank(
            foodbank_id="FB001",
            name="Test Bank",
            contact="x",
            address="y",
            latitude=0.0,
            longitude=0.0,
            food_items=[self.bread, self.milk],
        )
        inv = Inventory.from_foodbank(fb)
        self.assertEqual(len(inv.items()), 3)  # 2 bread batches + 1 milk

    def test_empty_inventory(self):
        inv = Inventory()
        self.assertEqual(inv.items(), [])
        self.assertIsNone(inv.peek_most_urgent())
        self.assertIsNone(inv.pop_most_urgent())


if __name__ == "__main__":
    unittest.main()
