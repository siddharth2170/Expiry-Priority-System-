import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.transaction_log import TransactionLog
from src.matching.engine import MatchCandidate, apply_transfer, execute_match
from src.models import Batch, DonationRecord, FoodItem, FoodRequest, Urgency

TODAY = date.today()


def days(n):
    return TODAY + timedelta(days=n)


def donation(record_id, source, quantity):
    return DonationRecord(
        record_id=record_id,
        food_id="F1",
        from_foodbank_id=source,
        to_foodbank_id="D",
        quantity=quantity,
        transfer_date=TODAY,
        status="Fulfilled",
    )


def product(batches):
    return FoodItem(
        food_id="F1",
        name="Milk",
        category="Dairy",
        unit="Liters",
        foodbank_id="A",
        storage_type="Refrigerated",
        batches=batches,
    )


def candidate(food_item, fill_quantity, request_qty=None):
    req = FoodRequest("REQ-T", "D", "Dairy", request_qty or fill_quantity, Urgency.CRITICAL)
    return MatchCandidate(
        request=req,
        source_id="A",
        dest_id="D",
        food_item=food_item,
        fill_quantity=fill_quantity,
        days_to_expiry=2,
        distance_km=1.0,
    )


class TestTransactionLog(unittest.TestCase):
    def test_total_and_per_source_rescued(self):
        """Totals sum all donations; per-source groups by giver."""
        log = TransactionLog()
        log.append(donation("D1", "A", 10))
        log.append(donation("D2", "A", 5))
        log.append(donation("D3", "B", 20))

        self.assertEqual(len(log), 3)
        self.assertEqual(log.total_rescued(), 35)
        self.assertEqual(log.rescued_units_by_source(), {"A": 15, "B": 20})
        self.assertEqual(len(log.for_source("A")), 2)

    def test_empty_log(self):
        """An empty log rescues nothing and groups to nothing."""
        log = TransactionLog()
        self.assertEqual(log.total_rescued(), 0)
        self.assertEqual(log.rescued_units_by_source(), {})

    def test_from_records_builds_view(self):
        """from_records wraps an existing list of donations."""
        records = [donation("D1", "A", 3), donation("D2", "B", 4)]
        log = TransactionLog.from_records(records)
        self.assertEqual(log.total_rescued(), 7)


class TestApplyTransfer(unittest.TestCase):
    def test_removes_soonest_batches_first(self):
        """Quantity is drawn from the soonest-expiring batch first."""
        item = product([Batch(days(6), 20), Batch(days(2), 10)])
        removed = apply_transfer(item, 15)

        self.assertEqual(removed, 15)
        # Soonest (10) fully consumed and dropped; 5 taken from the later batch.
        self.assertEqual(len(item.batches), 1)
        self.assertEqual(item.batches[0].expiry_date, days(6))
        self.assertEqual(item.batches[0].quantity, 15)

    def test_depleted_product_left_with_no_batches(self):
        """Taking everything empties the product's batch list."""
        item = product([Batch(days(2), 5)])
        removed = apply_transfer(item, 5)

        self.assertEqual(removed, 5)
        self.assertEqual(item.batches, [])

    def test_returns_only_what_was_available(self):
        """Removing more than exists returns just the available amount."""
        item = product([Batch(days(2), 4)])
        self.assertEqual(apply_transfer(item, 10), 4)


class TestExecuteMatch(unittest.TestCase):
    def test_source_decremented_and_record_created(self):
        """execute_match removes from the source and returns a donation record."""
        item = product([Batch(days(2), 30)])
        rec = execute_match(candidate(item, 12), TODAY)

        self.assertEqual(item.total_quantity(), 18)  # source reduced
        self.assertEqual(rec.quantity, 12)
        self.assertEqual(rec.from_foodbank_id, "A")
        self.assertEqual(rec.to_foodbank_id, "D")
        self.assertEqual(rec.food_id, "F1")
        self.assertEqual(rec.status, "Fulfilled")

    def test_destination_inventory_untouched(self):
        """The destination bank's stock is never credited by a match."""
        source_item = product([Batch(days(2), 30)])
        dest_item = FoodItem(
            food_id="F2",
            name="Milk",
            category="Dairy",
            unit="Liters",
            foodbank_id="D",
            storage_type="Refrigerated",
            batches=[Batch(days(4), 5)],
        )
        dest_before = dest_item.total_quantity()

        execute_match(candidate(source_item, 12), TODAY)

        self.assertEqual(dest_item.total_quantity(), dest_before)

    def test_partial_match_records_available_only(self):
        """A partial match rescues (and records) only what the source had."""
        item = product([Batch(days(2), 4)])
        rec = execute_match(candidate(item, 4, request_qty=10), TODAY)

        self.assertEqual(rec.quantity, 4)
        self.assertEqual(item.batches, [])


if __name__ == "__main__":
    unittest.main()
