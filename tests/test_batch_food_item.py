import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Batch, FoodItem

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def make_item(batches, **overrides):
    fields = dict(
        food_id="FOOD-1",
        name="Bread",
        category="Bakery",
        unit="Packets",
        foodbank_id="FB001",
        storage_type="Room Temperature",
        batches=batches,
    )
    fields.update(overrides)
    return FoodItem(**fields)


class TestBatch(unittest.TestCase):
    def test_batch_expiring_today_is_not_expired(self):
        """Boundary: a batch dated exactly today is still usable (today > expiry is False)."""
        self.assertFalse(Batch(expiry_date=TODAY, quantity=5).is_expired())

    def test_batch_already_expired(self):
        """A batch dated in the past is expired."""
        self.assertTrue(Batch(expiry_date=YESTERDAY, quantity=5).is_expired())

    def test_future_batch_not_expired(self):
        """A batch dated in the future is not expired."""
        self.assertFalse(Batch(expiry_date=TOMORROW, quantity=5).is_expired())


class TestFoodItem(unittest.TestCase):
    def test_active_vs_expired_split(self):
        """active_batches()/expired_batches() split a product's batches by date (today counts as active)."""
        item = make_item([
            Batch(expiry_date=TODAY, quantity=3),
            Batch(expiry_date=TOMORROW, quantity=4),
            Batch(expiry_date=YESTERDAY, quantity=9),
        ])
        self.assertEqual(len(item.active_batches()), 2)
        self.assertEqual(len(item.expired_batches()), 1)
        self.assertEqual(item.expired_batches()[0].quantity, 9)

    def test_total_quantity_counts_active_only(self):
        """total_quantity() sums active batches and ignores expired stock."""
        item = make_item([
            Batch(expiry_date=TOMORROW, quantity=4),
            Batch(expiry_date=YESTERDAY, quantity=9),
        ])
        self.assertEqual(item.total_quantity(), 4)

    def test_earliest_expiry_ignores_expired(self):
        """earliest_expiry() returns the soonest active date, skipping expired batches."""
        item = make_item([
            Batch(expiry_date=TOMORROW, quantity=4),
            Batch(expiry_date=YESTERDAY, quantity=9),
            Batch(expiry_date=TODAY, quantity=1),
        ])
        self.assertEqual(item.earliest_expiry(), TODAY)

    def test_earliest_expiry_none_when_all_expired(self):
        """earliest_expiry() is None when the product has no active batches."""
        item = make_item([Batch(expiry_date=YESTERDAY, quantity=9)])
        self.assertIsNone(item.earliest_expiry())

    def test_is_expired_true_only_when_no_active_batch(self):
        """A product is 'expired' only when every batch is expired (or it has none)."""
        all_expired = make_item([Batch(expiry_date=YESTERDAY, quantity=9)])
        self.assertTrue(all_expired.is_expired())

        empty = make_item([])
        self.assertTrue(empty.is_expired())

        has_active = make_item([
            Batch(expiry_date=YESTERDAY, quantity=9),
            Batch(expiry_date=TODAY, quantity=1),
        ])
        self.assertFalse(has_active.is_expired())


if __name__ == "__main__":
    unittest.main()
