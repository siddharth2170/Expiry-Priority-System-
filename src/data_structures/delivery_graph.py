from __future__ import annotations

import math

from src.data_structures.priority_queue import PriorityQueue
from src.models import Foodbank

EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/long points, in kilometers.

    The *haversine formula* computes the distance between two points on a
    sphere from their latitudes and longitudes. Unlike a straight-line
    (Euclidean) distance, it follows the curved surface of the Earth, which is
    why it is the standard choice for "how far apart are these two places."

    We use it here to weight the graph edges between foodbanks: given each
    bank's coordinates, this returns the on-the-ground distance a delivery
    would roughly cover, so routing can compare far vs. near transfers.

    How it works:
      - Latitudes/longitudes are converted from degrees to radians.
      - ``a`` is the square of half the chord length between the points,
        combining the latitude gap and the longitude gap (scaled by how far
        the points sit from the equator via ``cos(phi)``).
      - ``2 * asin(sqrt(a))`` is the central angle between the points, and
        multiplying by the Earth's radius turns that angle into a distance.

    Note: it assumes a perfect sphere, so it is accurate to a fraction of a
    percent -- more than enough for comparing delivery routes.

    References:
      - Veness, C. (n.d.). Calculating distance, bearing and more between
        latitude/longitude points. Movable Type Scripts.
        https://www.movable-type.co.uk/scripts/latlong.html
      - Haversine formula. (n.d.). In Wikipedia. Retrieved from
        https://en.wikipedia.org/wiki/Haversine_formula
    """
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    # chord_term = sin^2(dLat/2) + cos(lat1)*cos(lat2)*sin^2(dLon/2) -> the
    # haversine of the central angle; asin(sqrt(...)) recovers half that angle.
    chord_term = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    central_angle = 2 * math.asin(math.sqrt(chord_term))
    return EARTH_RADIUS_KM * central_angle


class DeliveryGraph:
    """Undirected weighted graph of foodbanks for routing transfers.

    The graph is a plain adjacency map built by hand (no graph library):
    ``_adj`` maps a node id to a list of ``(neighbor_id, distance_km)`` edges.
    Shortest paths use Dijkstra's algorithm driven by the custom PriorityQueue,
    so the network can weigh how far near-expiry food must travel.
    """

    def __init__(self) -> None:
        self._adj: dict[str, list[tuple[str, float]]] = {}

    def __len__(self) -> int:
        return len(self._adj)

    def __contains__(self, node: str) -> bool:
        return node in self._adj

    def nodes(self) -> list[str]:
        return list(self._adj)

    def add_node(self, node: str) -> None:
        self._adj.setdefault(node, [])

    def add_edge(self, a: str, b: str, distance_km: float) -> None:
        """Add an undirected edge (stored in both directions)."""
        self.add_node(a)
        self.add_node(b)
        self._adj[a].append((b, distance_km))
        self._adj[b].append((a, distance_km))

    def neighbors(self, node: str) -> list[tuple[str, float]]:
        return list(self._adj.get(node, []))

    def shortest_distances(self, source: str) -> dict[str, float]:
        """Dijkstra: shortest distance from ``source`` to every reachable node."""
        dist: dict[str, float] = {source: 0.0}
        visited: set[str] = set()
        pq = PriorityQueue()
        pq.push(source, 0.0)

        while not pq.is_empty():
            # The min-heap always hands back the closest unvisited node next.
            node = pq.pop()
            # Lazy deletion: a node can be queued more than once; the first time
            # it pops it carries its final (smallest) distance, so skip repeats.
            if node in visited:
                continue
            visited.add(node)

            for neighbor, weight in self._adj.get(node, []):
                new_dist = dist[node] + weight
                # Relaxation: if reaching `neighbor` via `node` is cheaper than any
                # route found so far, record the shorter distance and re-queue it.
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    pq.push(neighbor, new_dist)
        return dist

    def shortest_path(self, source: str, target: str) -> tuple[float | None, list[str]]:
        """Dijkstra with predecessor tracking; returns (distance, path).

        Returns ``(None, [])`` when ``target`` is unreachable from ``source``.
        """
        if source not in self._adj or target not in self._adj:
            return (None, [])
        if source == target:
            return (0.0, [source])

        dist: dict[str, float] = {source: 0.0}
        prev: dict[str, str] = {}
        visited: set[str] = set()
        pq = PriorityQueue()
        pq.push(source, 0.0)

        while not pq.is_empty():
            node = pq.pop()
            if node in visited:
                continue
            visited.add(node)
            # Once the target is finalized its distance is optimal; stop early.
            if node == target:
                break
            for neighbor, weight in self._adj.get(node, []):
                new_dist = dist[node] + weight
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    # Remember how we reached `neighbor` so the path can be rebuilt.
                    prev[neighbor] = node
                    pq.push(neighbor, new_dist)

        if target not in dist:
            return (None, [])

        # Walk predecessors back from target to source, then reverse to get the
        # path in travel order (source -> ... -> target).
        path = [target]
        while path[-1] != source:
            path.append(prev[path[-1]])
        path.reverse()
        return (dist[target], path)

    def nearest(self, source: str, candidates=None) -> tuple[str, float] | None:
        """Closest reachable node to ``source`` (optionally within ``candidates``).

        Ties are broken by node id for deterministic results. Returns ``None``
        when nothing qualifies.
        """
        dist = self.shortest_distances(source)
        dist.pop(source, None)  # never return the source itself
        if candidates is not None:
            # Keep only the nodes the caller is interested in.
            allowed = set(candidates)
            dist = {n: d for n, d in dist.items() if n in allowed}
        if not dist:
            return None
        # Pick the closest node; on equal distance, the smaller id wins (stable).
        node = min(dist, key=lambda n: (dist[n], n))
        return (node, dist[node])

    @classmethod
    def from_foodbanks(cls, foodbanks, threshold_km: float | None = None) -> "DeliveryGraph":
        """Build a graph from foodbank coordinates using haversine distances.

        Every pair within ``threshold_km`` gets an edge; with ``threshold_km``
        None the graph is fully connected. A threshold yields a sparser graph
        where some trips route through intermediate banks.
        """
        graph = cls()
        banks = list(foodbanks)
        # Register every bank first so isolated banks still exist as nodes.
        for fb in banks:
            graph.add_node(fb.foodbank_id)
        # j starts at i+1 so each unordered pair is measured exactly once.
        for i in range(len(banks)):
            for j in range(i + 1, len(banks)):
                a, b = banks[i], banks[j]
                distance = haversine(a.latitude, a.longitude, b.latitude, b.longitude)
                # Skip pairs beyond the threshold so far banks route via closer ones.
                if threshold_km is None or distance <= threshold_km:
                    graph.add_edge(a.foodbank_id, b.foodbank_id, distance)
        return graph
