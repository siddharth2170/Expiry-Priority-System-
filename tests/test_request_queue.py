import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.request_queue import RequestQueue
from src.models import FoodRequest, Urgency

TODAY = date(2026, 1, 1)  # fixed reference so aging math is deterministic


def request(request_id, urgency, days_ago, category="Bakery", quantity=5):
    return FoodRequest(
        request_id=request_id,
        foodbank_id="FB000",
        category=category,
        quantity=quantity,
        urgency=urgency,
        submitted_at=TODAY - timedelta(days=days_ago),
    )


class TestRequestQueue(unittest.TestCase):
    def test_orders_by_urgency_when_same_age(self):
        """With equal waiting time, requests order CRITICAL, LOW, ROUTINE."""
        q = RequestQueue()
        q.add(request("R-ROUTINE", Urgency.ROUTINE, 0), today=TODAY)
        q.add(request("R-CRIT", Urgency.CRITICAL, 0), today=TODAY)
        q.add(request("R-LOW", Urgency.LOW, 0), today=TODAY)
        ids = [r.request_id for r in q.pending(TODAY)]
        self.assertEqual(ids, ["R-CRIT", "R-LOW", "R-ROUTINE"])

    def test_aging_lets_old_request_overtake(self):
        """A routine request waiting long enough outranks a fresh critical one."""
        q = RequestQueue()
        fresh_critical = request("R-CRIT", Urgency.CRITICAL, days_ago=1)   # score ~ -1
        old_routine = request("R-OLD", Urgency.ROUTINE, days_ago=65)       # score 60-65 = -5
        q.add(fresh_critical, today=TODAY)
        q.add(old_routine, today=TODAY)
        self.assertEqual(q.pending(TODAY)[0].request_id, "R-OLD")

    def test_score_formula(self):
        """priority_score = urgency*URGENCY_WEIGHT - age_days (lower = more urgent)."""
        q = RequestQueue()
        r = request("R", Urgency.ROUTINE, days_ago=10)
        expected = Urgency.ROUTINE.value * q.URGENCY_WEIGHT - 10 * q.AGE_WEIGHT
        self.assertEqual(q.priority_score(r, TODAY), expected)

    def test_future_submission_treated_as_zero_age(self):
        """A submission date in the future clamps age to zero (no negative aging)."""
        q = RequestQueue()
        r = request("R", Urgency.LOW, days_ago=-5)  # submitted 5 days in the future
        self.assertEqual(q.priority_score(r, TODAY), Urgency.LOW.value * q.URGENCY_WEIGHT)

    def test_peek_does_not_remove_pop_does(self):
        """peek_most_urgent leaves the queue intact; pop_most_urgent removes the item."""
        q = RequestQueue()
        q.add(request("R-CRIT", Urgency.CRITICAL, 0), today=TODAY)
        q.add(request("R-LOW", Urgency.LOW, 0), today=TODAY)
        self.assertEqual(q.peek_most_urgent().request_id, "R-CRIT")
        self.assertEqual(len(q), 2)
        self.assertEqual(q.pop_most_urgent().request_id, "R-CRIT")
        self.assertEqual(len(q), 1)
        self.assertEqual(q.peek_most_urgent().request_id, "R-LOW")

    def test_remove_is_lazy_and_skipped(self):
        """A removed request is gone from reads and never surfaces from the heap."""
        q = RequestQueue()
        q.add(request("R-CRIT", Urgency.CRITICAL, 0), today=TODAY)
        q.add(request("R-LOW", Urgency.LOW, 0), today=TODAY)
        self.assertTrue(q.remove("R-CRIT"))
        self.assertEqual(len(q), 1)
        self.assertEqual(q.pop_most_urgent().request_id, "R-LOW")

    def test_remove_unknown_returns_false(self):
        """Removing an unknown id reports False."""
        self.assertFalse(RequestQueue().remove("NOPE"))

    def test_rebuild_refreshes_stale_scores(self):
        """rebuild recomputes aging so a request added earlier is re-prioritized.

        A low request is added on day 0; a critical request is added 40 days
        later. By stored (insertion-time) scores the critical looks best, but
        after rebuilding against day 40 the low request has aged past it.
        """
        q = RequestQueue()
        day0 = TODAY
        day40 = TODAY + timedelta(days=40)
        low = FoodRequest("R-LOW", "FB000", "Dairy", 5, Urgency.LOW, submitted_at=day0)
        crit = FoodRequest("R-CRIT", "FB000", "Bakery", 5, Urgency.CRITICAL, submitted_at=day40)
        q.add(low, today=day0)     # stored score 30
        q.add(crit, today=day40)   # stored score 0 -> looks most urgent by heap
        self.assertEqual(q.peek_most_urgent().request_id, "R-CRIT")
        q.rebuild(today=day40)     # low has now waited 40 days: 30 - 40 = -10
        self.assertEqual(q.peek_most_urgent().request_id, "R-LOW")

    def test_pending_is_accurate_without_rebuild(self):
        """pending always recomputes, so it is correct even if the heap is stale."""
        q = RequestQueue()
        day0 = TODAY
        day40 = TODAY + timedelta(days=40)
        low = FoodRequest("R-LOW", "FB000", "Dairy", 5, Urgency.LOW, submitted_at=day0)
        crit = FoodRequest("R-CRIT", "FB000", "Bakery", 5, Urgency.CRITICAL, submitted_at=day40)
        q.add(low, today=day0)
        q.add(crit, today=day40)
        self.assertEqual(q.pending(day40)[0].request_id, "R-LOW")

    def test_empty_queue(self):
        """An empty queue reports empty and returns None for peek/pop."""
        q = RequestQueue()
        self.assertTrue(q.is_empty())
        self.assertIsNone(q.peek_most_urgent())
        self.assertIsNone(q.pop_most_urgent())
        self.assertEqual(q.pending(TODAY), [])

    def test_from_requests_builds_queue(self):
        """from_requests loads an iterable of requests into the queue."""
        reqs = [request("A", Urgency.LOW, 0), request("B", Urgency.CRITICAL, 0)]
        q = RequestQueue.from_requests(reqs, today=TODAY)
        self.assertEqual(len(q), 2)
        self.assertEqual(q.pending(TODAY)[0].request_id, "B")


if __name__ == "__main__":
    unittest.main()
