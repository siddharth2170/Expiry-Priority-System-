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
        """items() returns every active batch ordered soonest-to-expire first."""
        expiries = [batch.expiry_date for _, batch in self.inv.items()]
        self.assertEqual(expiries, sorted(expiries))

    def test_same_product_yields_one_row_per_active_batch(self):
        """A product with two active batches appears as two separate rows."""
        names = [it.name for it, _ in self.inv.items()]
        self.assertEqual(names.count("Bread"), 2)

    def test_fully_expired_product_excluded(self):
        """A product whose batches are all expired is left out of usable stock and totals."""
        names = [it.name for it, _ in self.inv.items()]
        self.assertNotIn("Yogurt", names)
        self.assertEqual(self.inv.total_quantity("Dairy"), 60)

    def test_peek_most_urgent_overall(self):
        """peek_most_urgent() returns the soonest batch network-wide without removing it."""
        it, batch = self.inv.peek_most_urgent()
        self.assertEqual(it.name, "Bread")
        self.assertEqual(batch.expiry_date, days(2))
        self.assertEqual(len(self.inv.items()), 3)

    def test_pop_most_urgent_drains_in_expiry_order(self):
        """pop_most_urgent() serves batches soonest-first and never serves expired ones."""
        popped = []
        while True:
            line = self.inv.pop_most_urgent()
            if line is None:
                break
            popped.append(line[1].expiry_date)
        self.assertEqual(popped, [days(2), days(4), days(6)])

    def test_by_category_filters_and_orders(self):
        """by_category() returns only that category's active batches, expiry-ordered."""
        bakery = self.inv.by_category("Bakery")
        self.assertEqual({it.name for it, _ in bakery}, {"Bread"})
        self.assertEqual([b.expiry_date for _, b in bakery], [days(2), days(6)])

    def test_total_quantity_active_only(self):
        """total_quantity() sums a category's active batch quantities."""
        self.assertEqual(self.inv.total_quantity("Bakery"), 55)  # 30 + 25

    def test_remove_is_lazy_but_excluded_from_reads(self):
        """remove() hides a product from reads immediately; pops skip its stale lines."""
        self.assertTrue(self.inv.remove("F1"))
        names = [it.name for it, _ in self.inv.items()]
        self.assertNotIn("Bread", names)
        it, _ = self.inv.pop_most_urgent()
        self.assertEqual(it.name, "Milk")

    def test_remove_unknown_returns_false(self):
        """remove() of an unknown id reports False and changes nothing."""
        self.assertFalse(self.inv.remove("NOPE"))

    def test_peek_unknown_category_returns_none(self):
        """peek_most_urgent() for a category with no stock returns None."""
        self.assertIsNone(self.inv.peek_most_urgent("Frozen"))

    def test_tie_on_same_expiry_keeps_both_and_is_deterministic(self):
        """Two active batches with identical expiry dates both appear, in insertion order."""
        tie = item("F9", "Buns", "Bakery", [Batch(days(1), 5), Batch(days(1), 7)])
        inv = Inventory()
        inv.add(tie)
        lines = inv.by_category("Bakery")
        self.assertEqual(len(lines), 2)
        self.assertEqual([b.quantity for _, b in lines], [5, 7])

    def test_from_foodbank_builds_from_food_items(self):
        """from_foodbank() loads every batch of every product on the foodbank."""
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
        """An empty inventory yields no items and None for peek/pop."""
        inv = Inventory()
        self.assertEqual(inv.items(), [])
        self.assertIsNone(inv.peek_most_urgent())
        self.assertIsNone(inv.pop_most_urgent())


if __name__ == "__main__":
    unittest.main()
