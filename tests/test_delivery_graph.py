import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.delivery_graph import DeliveryGraph, haversine
from src.models import Foodbank


def bank(fb_id, lat, lon):
    return Foodbank(
        foodbank_id=fb_id,
        name=fb_id,
        contact="x",
        address="y",
        latitude=lat,
        longitude=lon,
    )


class TestHaversine(unittest.TestCase):
    def test_zero_distance_for_same_point(self):
        """A point to itself is 0 km."""
        self.assertAlmostEqual(haversine(37.0, -122.0, 37.0, -122.0), 0.0, places=6)

    def test_one_degree_longitude_at_equator(self):
        """One degree of longitude at the equator is about 111 km."""
        self.assertAlmostEqual(haversine(0.0, 0.0, 0.0, 1.0), 111.19, delta=0.5)

    def test_symmetric(self):
        """Distance is the same in either direction."""
        d1 = haversine(37.77, -122.41, 37.80, -122.46)
        d2 = haversine(37.80, -122.46, 37.77, -122.41)
        self.assertAlmostEqual(d1, d2, places=9)


class TestDeliveryGraph(unittest.TestCase):
    def _triangle(self):
        # A-B = 1, B-C = 1, A-C = 5  (so A->C is cheaper via B)
        g = DeliveryGraph()
        g.add_edge("A", "B", 1.0)
        g.add_edge("B", "C", 1.0)
        g.add_edge("A", "C", 5.0)
        return g

    def test_edges_are_undirected(self):
        """add_edge records the edge in both directions."""
        g = DeliveryGraph()
        g.add_edge("A", "B", 2.5)
        self.assertIn(("B", 2.5), g.neighbors("A"))
        self.assertIn(("A", 2.5), g.neighbors("B"))

    def test_add_node_and_contains(self):
        """add_node registers an isolated node."""
        g = DeliveryGraph()
        g.add_node("solo")
        self.assertIn("solo", g)
        self.assertEqual(g.neighbors("solo"), [])

    def test_shortest_path_prefers_multi_hop_when_cheaper(self):
        """Dijkstra routes A->C through B (cost 2) instead of the direct edge (cost 5)."""
        g = self._triangle()
        distance, path = g.shortest_path("A", "C")
        self.assertEqual(distance, 2.0)
        self.assertEqual(path, ["A", "B", "C"])

    def test_shortest_path_same_node(self):
        """A path from a node to itself is zero length."""
        g = self._triangle()
        self.assertEqual(g.shortest_path("A", "A"), (0.0, ["A"]))

    def test_shortest_distances_all_nodes(self):
        """shortest_distances returns the minimum cost to every reachable node."""
        g = self._triangle()
        dist = g.shortest_distances("A")
        self.assertEqual(dist, {"A": 0.0, "B": 1.0, "C": 2.0})

    def test_unreachable_returns_none(self):
        """An isolated target is unreachable: (None, [])."""
        g = self._triangle()
        g.add_node("Z")
        self.assertEqual(g.shortest_path("A", "Z"), (None, []))
        self.assertNotIn("Z", g.shortest_distances("A"))

    def test_missing_nodes_return_none(self):
        """A path involving an unknown node is (None, [])."""
        g = self._triangle()
        self.assertEqual(g.shortest_path("A", "NOPE"), (None, []))

    def test_nearest_picks_closest(self):
        """nearest returns the closest reachable node to the source."""
        g = self._triangle()
        self.assertEqual(g.nearest("A"), ("B", 1.0))

    def test_nearest_respects_candidates(self):
        """nearest can be restricted to a candidate set."""
        g = self._triangle()
        self.assertEqual(g.nearest("A", candidates={"C"}), ("C", 2.0))

    def test_nearest_none_when_isolated(self):
        """nearest returns None when the source has no reachable neighbors."""
        g = DeliveryGraph()
        g.add_node("lonely")
        self.assertIsNone(g.nearest("lonely"))

    def test_from_foodbanks_fully_connected(self):
        """With no threshold every pair of banks is directly connected."""
        banks = [bank("A", 0.0, 0.0), bank("B", 0.0, 1.0), bank("C", 0.0, 2.0)]
        g = DeliveryGraph.from_foodbanks(banks)
        self.assertEqual(len(g.neighbors("A")), 2)

    def test_from_foodbanks_threshold_sparsifies(self):
        """A threshold drops long edges; A-C (~222 km) is excluded at 150 km."""
        banks = [bank("A", 0.0, 0.0), bank("B", 0.0, 1.0), bank("C", 0.0, 2.0)]
        g = DeliveryGraph.from_foodbanks(banks, threshold_km=150)
        a_neighbors = {n for n, _ in g.neighbors("A")}
        self.assertEqual(a_neighbors, {"B"})            # A-B ~111 km kept
        # A still reaches C, but only by routing through B.
        distance, path = g.shortest_path("A", "C")
        self.assertEqual(path, ["A", "B", "C"])
        self.assertAlmostEqual(distance, haversine(0, 0, 0, 1) + haversine(0, 1, 0, 2), places=6)


class TestDijkstra(unittest.TestCase):
    def _triangle(self):
        g = DeliveryGraph()
        g.add_edge("A", "B", 1.0)
        g.add_edge("B", "C", 1.0)
        g.add_edge("A", "C", 5.0)
        return g

    def test_distances_match_shortest_distances(self):
        """dijkstra distances agree with shortest_distances."""
        g = self._triangle()
        dist, _ = g.dijkstra("A")
        self.assertEqual(dist, g.shortest_distances("A"))

    def test_predecessors_rebuild_shortest_path(self):
        """Walking predecessors from source rebuilds the shortest_path route."""
        g = self._triangle()
        dist, prev = g.dijkstra("C")  # root at the destination (graph is undirected)
        # Rebuild A->C by following predecessors from A toward C.
        path = ["A"]
        while path[-1] != "C":
            path.append(prev[path[-1]])
        self.assertEqual(path, ["A", "B", "C"])
        self.assertEqual(dist["A"], 2.0)

    def test_unreachable_absent_from_distances(self):
        """An isolated node never appears in the distance map."""
        g = self._triangle()
        g.add_node("Z")
        dist, prev = g.dijkstra("A")
        self.assertNotIn("Z", dist)
        self.assertNotIn("Z", prev)


class TestGridConstruction(unittest.TestCase):
    """The spatial-grid builder must yield the exact same edges as brute force."""

    def _brute_force(self, banks, threshold_km):
        g = DeliveryGraph()
        for fb in banks:
            g.add_node(fb.foodbank_id)
        for i in range(len(banks)):
            for j in range(i + 1, len(banks)):
                a, b = banks[i], banks[j]
                d = haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                if d <= threshold_km:
                    g.add_edge(a.foodbank_id, b.foodbank_id, d)
        return g

    def _edge_set(self, g):
        return {frozenset((n, nb)) for n in g.nodes() for nb, _ in g.neighbors(n)}

    def test_grid_matches_brute_force_various_thresholds(self):
        """Grid edges equal brute-force edges across a spread of thresholds."""
        banks = [
            bank("A", 37.77, -122.41),
            bank("B", 37.80, -122.46),
            bank("C", 37.75, -122.39),
            bank("D", 37.72, -122.48),
            bank("E", 38.10, -122.20),
        ]
        for thr in [0.5, 1.0, 2.5, 5.0, 10.0, 50.0, 200.0]:
            grid = DeliveryGraph.from_foodbanks(banks, threshold_km=thr)
            brute = self._brute_force(banks, thr)
            self.assertEqual(
                self._edge_set(grid), self._edge_set(brute), msg=f"threshold={thr}"
            )

    def test_grid_matches_brute_force_high_latitude(self):
        """Correct near the poles, where longitude degrees are short (kx small)."""
        banks = [
            bank("A", 69.0, 18.0),
            bank("B", 69.0, 18.5),
            bank("C", 69.2, 18.1),
            bank("D", 60.0, 10.0),
        ]
        for thr in [1.0, 5.0, 20.0, 30.0, 100.0]:
            grid = DeliveryGraph.from_foodbanks(banks, threshold_km=thr)
            brute = self._brute_force(banks, thr)
            self.assertEqual(
                self._edge_set(grid), self._edge_set(brute), msg=f"threshold={thr}"
            )

    def test_grid_handles_empty_and_single(self):
        """Empty and single-bank inputs produce no edges and don't error."""
        self.assertEqual(len(DeliveryGraph.from_foodbanks([], threshold_km=5.0)), 0)
        g = DeliveryGraph.from_foodbanks([bank("A", 0.0, 0.0)], threshold_km=5.0)
        self.assertEqual(g.neighbors("A"), [])


if __name__ == "__main__":
    unittest.main()
