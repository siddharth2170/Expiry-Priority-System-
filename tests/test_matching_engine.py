import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.delivery_graph import DeliveryGraph
from src.matching.engine import (
    _distance,
    _route,
    allocate,
    build_path_index,
    find_all,
    find_candidates,
)
from src.models import Batch, Foodbank, FoodItem, FoodRequest, Urgency

TODAY = date.today()


def days(n):
    return TODAY + timedelta(days=n)


def bank(fb_id, category=None, expiry_days=5, quantity=100, name=None):
    """A foodbank optionally holding one product of ``category``."""
    items = []
    if category is not None:
        items.append(
            FoodItem(
                food_id=f"{fb_id}-{category}",
                name=name or f"{category} item",
                category=category,
                unit="Units",
                foodbank_id=fb_id,
                storage_type="Room Temperature",
                batches=[Batch(days(expiry_days), quantity)],
            )
        )
    return Foodbank(
        foodbank_id=fb_id,
        name=fb_id,
        contact="x",
        address="x",
        latitude=0.0,
        longitude=0.0,
        food_items=items,
    )


def request(dest, category="Dairy", quantity=10, urgency=Urgency.CRITICAL):
    return FoodRequest(
        request_id="REQ-T",
        foodbank_id=dest,
        category=category,
        quantity=quantity,
        urgency=urgency,
    )


def graph_with(edges):
    """Build a DeliveryGraph from explicit (a, b, km) edges (no haversine)."""
    g = DeliveryGraph()
    for a, b, km in edges:
        g.add_edge(a, b, km)
    return g


class TestFindCandidates(unittest.TestCase):
    def test_returns_top_two_in_score_order(self):
        """Only the best two sources are returned, ascending by score."""
        dest = bank("D")  # requester, no stock needed
        a = bank("A", "Dairy", expiry_days=2)   # score 1*1 + 2*2 = 5
        b = bank("B", "Dairy", expiry_days=5)   # score 1*1 + 2*5 = 11
        c = bank("C", "Dairy", expiry_days=2)   # score 5*1 + 2*2 = 9
        g = graph_with([("A", "D", 1.0), ("B", "D", 1.0), ("C", "D", 5.0)])

        out = find_candidates(request("D"), [dest, a, b, c], g, TODAY, top_n=2)

        self.assertEqual([c_.source_id for c_ in out], ["A", "C"])
        self.assertLess(out[0].score, out[1].score)

    def test_soon_expiry_can_outweigh_distance(self):
        """A farther but sooner-to-expire source can beat a near, later one."""
        dest = bank("D")
        near = bank("NEAR", "Dairy", expiry_days=10)  # 1*1 + 2*10 = 21
        far = bank("FAR", "Dairy", expiry_days=2)      # 5*1 + 2*2  = 9
        g = graph_with([("NEAR", "D", 1.0), ("FAR", "D", 5.0)])

        out = find_candidates(request("D"), [dest, near, far], g, TODAY)

        self.assertEqual(out[0].source_id, "FAR")

    def test_bank_cannot_serve_its_own_request(self):
        """The requesting bank is never one of its own candidates."""
        dest = bank("D", "Dairy")  # requester also holds Dairy
        a = bank("A", "Dairy")
        g = graph_with([("A", "D", 1.0)])

        out = find_candidates(request("D"), [dest, a], g, TODAY)

        self.assertEqual([c_.source_id for c_ in out], ["A"])

    def test_source_without_category_excluded(self):
        """Banks with no stock in the requested category are skipped."""
        dest = bank("D")
        a = bank("A", "Dairy")
        b = bank("B", "Bakery")  # wrong category
        g = graph_with([("A", "D", 1.0), ("B", "D", 1.0)])

        out = find_candidates(request("D", category="Dairy"), [dest, a, b], g, TODAY)

        self.assertEqual([c_.source_id for c_ in out], ["A"])

    def test_unreachable_source_excluded(self):
        """A source with no route to the destination is dropped."""
        dest = bank("D")
        a = bank("A", "Dairy")
        b = bank("B", "Dairy")  # present but disconnected
        g = graph_with([("A", "D", 1.0)])
        g.add_node("B")

        out = find_candidates(request("D"), [dest, a, b], g, TODAY)

        self.assertEqual([c_.source_id for c_ in out], ["A"])

    def test_expired_only_source_excluded(self):
        """A source whose only batch in the category is expired is skipped."""
        dest = bank("D")
        a = bank("A", "Dairy", expiry_days=-1)  # fully expired
        b = bank("B", "Dairy", expiry_days=3)
        g = graph_with([("A", "D", 1.0), ("B", "D", 1.0)])

        out = find_candidates(request("D"), [dest, a, b], g, TODAY)

        self.assertEqual([c_.source_id for c_ in out], ["B"])

    def test_partial_fill_when_stock_below_request(self):
        """fill_quantity caps at available stock and flags a partial match."""
        dest = bank("D")
        a = bank("A", "Dairy", quantity=4)
        g = graph_with([("A", "D", 1.0)])

        out = find_candidates(request("D", quantity=10), [dest, a], g, TODAY)

        self.assertEqual(out[0].fill_quantity, 4)
        self.assertTrue(out[0].is_partial)


class TestAllocate(unittest.TestCase):
    """Contention: one shared, scarce stock split across competing requests."""

    def _by_request(self, allocations):
        out = {}
        for a in allocations:
            out.setdefault(a.request.request_id, []).append(a)
        return out

    def test_scarce_stock_goes_to_better_scoring_request(self):
        """Two equal-urgency requests, one source: the closer one wins the stock."""
        s = bank("S", "Dairy", expiry_days=5, quantity=10)
        d1, d2 = bank("D1"), bank("D2")
        r1 = FoodRequest("R1", "D1", "Dairy", 10, Urgency.CRITICAL)  # dist 1 -> score 11
        r2 = FoodRequest("R2", "D2", "Dairy", 10, Urgency.CRITICAL)  # dist 5 -> score 15
        g = graph_with([("S", "D1", 1.0), ("S", "D2", 5.0)])

        allocs = self._by_request(allocate([s, d1, d2], [r1, r2], g, TODAY))

        self.assertEqual(allocs["R1"][0].source_id, "S")
        self.assertEqual(allocs["R1"][0].fill_quantity, 10)
        self.assertNotIn("R2", allocs)  # stock exhausted by the better match

    def test_urgency_wins_when_distances_are_close(self):
        """A CRITICAL-but-far need beats a LOW-but-close one for a small gap."""
        s = bank("S", "Dairy", expiry_days=5, quantity=10)
        d1, d2 = bank("D1"), bank("D2")
        r_crit = FoodRequest("CRIT", "D1", "Dairy", 10, Urgency.CRITICAL)  # 0+10+8 = 18
        r_low = FoodRequest("LOW", "D2", "Dairy", 10, Urgency.LOW)          # 10+10+1 = 21
        g = graph_with([("S", "D1", 8.0), ("S", "D2", 1.0)])

        allocs = self._by_request(allocate([s, d1, d2], [r_crit, r_low], g, TODAY))

        self.assertEqual(allocs["CRIT"][0].fill_quantity, 10)
        self.assertNotIn("LOW", allocs)

    def test_proximity_wins_when_far_enough(self):
        """A big distance gap lets a LOW-close need out-score a CRITICAL-far one."""
        s = bank("S", "Dairy", expiry_days=5, quantity=10)
        d1, d2 = bank("D1"), bank("D2")
        r_crit = FoodRequest("CRIT", "D1", "Dairy", 10, Urgency.CRITICAL)  # 0+10+15 = 25
        r_low = FoodRequest("LOW", "D2", "Dairy", 10, Urgency.LOW)          # 10+10+1 = 21
        g = graph_with([("S", "D1", 15.0), ("S", "D2", 1.0)])

        allocs = self._by_request(allocate([s, d1, d2], [r_crit, r_low], g, TODAY))

        self.assertEqual(allocs["LOW"][0].fill_quantity, 10)
        self.assertNotIn("CRIT", allocs)

    def test_request_filled_across_multiple_sources(self):
        """A request bigger than any one source draws from the best sources first."""
        a = bank("A", "Dairy", expiry_days=5, quantity=10)  # dist 1 -> score 11
        b = bank("B", "Dairy", expiry_days=5, quantity=10)  # dist 3 -> score 13
        d = bank("D")
        r = FoodRequest("R", "D", "Dairy", 15, Urgency.CRITICAL)
        g = graph_with([("A", "D", 1.0), ("B", "D", 3.0)])

        allocs = self._by_request(allocate([a, b, d], [r], g, TODAY))["R"]
        by_source = {x.source_id: x.fill_quantity for x in allocs}

        self.assertEqual(by_source, {"A": 10, "B": 5})  # A drained first, B tops up

    def test_one_source_serves_two_requests_until_dry(self):
        """A source with leftover stock partially fills the next-best request."""
        s = bank("S", "Dairy", expiry_days=5, quantity=15)
        d1, d2 = bank("D1"), bank("D2")
        r1 = FoodRequest("R1", "D1", "Dairy", 10, Urgency.CRITICAL)  # dist 1, wins first
        r2 = FoodRequest("R2", "D2", "Dairy", 10, Urgency.CRITICAL)  # dist 2, gets remainder
        g = graph_with([("S", "D1", 1.0), ("S", "D2", 2.0)])

        allocs = self._by_request(allocate([s, d1, d2], [r1, r2], g, TODAY))

        self.assertEqual(allocs["R1"][0].fill_quantity, 10)
        self.assertEqual(allocs["R2"][0].fill_quantity, 5)
        self.assertTrue(allocs["R2"][0].is_partial)


class TestPathIndex(unittest.TestCase):
    """The precomputed path index must agree with graph.shortest_path."""

    def test_distance_and_route_match_shortest_path(self):
        g = graph_with([("A", "B", 1.0), ("B", "C", 1.0), ("A", "C", 5.0)])
        paths = build_path_index(g, ["C", "B"])
        # A->C routes through B (cost 2), matching shortest_path.
        self.assertEqual(_distance(paths, "A", "C"), 2.0)
        self.assertEqual(_route(paths, "A", "C"), ["A", "B", "C"])
        dist, route = g.shortest_path("A", "C")
        self.assertEqual((_distance(paths, "A", "C"), _route(paths, "A", "C")), (dist, route))

    def test_unreachable_distance_is_none(self):
        g = graph_with([("A", "B", 1.0)])
        g.add_node("Z")
        paths = build_path_index(g, ["Z"])
        self.assertIsNone(_distance(paths, "A", "Z"))
        self.assertEqual(_route(paths, "A", "Z"), [])

    def test_dedupes_destinations(self):
        g = graph_with([("A", "B", 1.0)])
        paths = build_path_index(g, ["B", "B", "A"])
        self.assertEqual(set(paths), {"A", "B"})


class TestPrecomputedParity(unittest.TestCase):
    """Passing a prebuilt path index must not change results."""

    def _network(self):
        s = bank("S", "Dairy", expiry_days=5, quantity=10)
        d1, d2 = bank("D1"), bank("D2")
        reqs = [
            FoodRequest("R1", "D1", "Dairy", 6, Urgency.CRITICAL),
            FoodRequest("R2", "D2", "Dairy", 6, Urgency.LOW),
        ]
        g = graph_with([("S", "D1", 1.0), ("S", "D2", 2.0), ("D1", "D2", 1.0)])
        return [s, d1, d2], reqs, g

    def _sig(self, allocs):
        return [
            (a.source_id, a.dest_id, a.food_item.food_id, a.fill_quantity,
             round(a.score, 6), tuple(a.route))
            for a in allocs
        ]

    def test_allocate_parity_with_and_without_paths(self):
        foodbanks, reqs, g = self._network()
        paths = build_path_index(g, [r.foodbank_id for r in reqs])
        without = allocate(foodbanks, reqs, g, TODAY)
        with_paths = allocate(foodbanks, reqs, g, TODAY, paths=paths)
        self.assertEqual(self._sig(without), self._sig(with_paths))

    def test_find_candidates_parity_with_and_without_paths(self):
        foodbanks, reqs, g = self._network()
        req = reqs[0]
        paths = build_path_index(g, [req.foodbank_id])
        without = find_candidates(req, foodbanks, g, TODAY, top_n=2)
        with_paths = find_candidates(req, foodbanks, g, TODAY, top_n=2, paths=paths)
        self.assertEqual(
            [(c.source_id, c.score, tuple(c.route)) for c in without],
            [(c.source_id, c.score, tuple(c.route)) for c in with_paths],
        )


class TestFindAll(unittest.TestCase):
    def test_orders_requests_by_urgency(self):
        """find_all returns one entry per request, most urgent first."""
        # Two SoMa/Mission-style banks so each request has a source.
        a = bank("A", "Dairy", quantity=100)
        b = bank("B", "Bakery", quantity=100)
        d1 = bank("D1")
        d2 = bank("D2")
        reqs = [
            FoodRequest("R1", "D1", "Dairy", 5, Urgency.ROUTINE),
            FoodRequest("R2", "D2", "Bakery", 5, Urgency.CRITICAL),
        ]
        foodbanks = [a, b, d1, d2]

        out = find_all(foodbanks, reqs, TODAY)

        # RequestQueue puts the CRITICAL request first.
        self.assertEqual(out[0][0].request_id, "R2")
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
