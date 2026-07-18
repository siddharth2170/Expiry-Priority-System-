from __future__ import annotations

from datetime import date

from src.constants import MATCH_W_AGE, MATCH_W_DIST, MATCH_W_EXP, MATCH_W_URG
from src.data_structures.delivery_graph import DeliveryGraph
from src.data_structures.inventory import Inventory
from src.data_structures.priority_queue import PriorityQueue
from src.data_structures.request_queue import RequestQueue
from src.matching.models import MatchCandidate
from src.models import DonationRecord, FoodItem, Foodbank, FoodRequest
from src.utils import generate_donation_id


def score_pair(
    request: FoodRequest,
    distance_km: float,
    days_to_expiry: int,
    today: date | None = None,
) -> float:
    """Blend one (request, source) pairing into a single number; lower is better.

    Four signals decide who should win a *contested* item:
      - urgency: CRITICAL(0) < LOW(1) < ROUTINE(2), so urgent needs score lower.
      - expiry: fewer days of shelf life left = more worth rescuing = lower.
      - distance: shorter delivery = cheaper = lower.
      - aging: the longer a request has waited, the more we discount its score.

    Within one request, urgency and aging are constant, so only distance and
    expiry separate its candidate sources. They only change the outcome when
    *different* requests compete for the same stock (see ``allocate``).
    """
    today = today or date.today()
    age_days = max(0, (today - request.submitted_at).days)
    return (
        MATCH_W_URG * request.urgency.value
        + MATCH_W_EXP * days_to_expiry
        + MATCH_W_DIST * distance_km
        - MATCH_W_AGE * age_days
    )


# Optimization: precompute shortest paths once, then serve queries by lookup.
# A path index maps each destination to a single Dijkstra result rooted there:
# {dest_id: (distances, predecessors)}. Because the delivery graph is undirected,
# one run rooted at a destination answers the distance and route from *every*
# source to that destination, so callers replace per-pair Dijkstra with lookups.
PathIndex = dict


def build_path_index(graph: DeliveryGraph, destinations) -> PathIndex:
    """Run Dijkstra once per distinct destination and cache (dist, prev) maps."""
    # dict.fromkeys dedupes while preserving order, so each requester is solved once.
    return {dest: graph.dijkstra(dest) for dest in dict.fromkeys(destinations)}


def _distance(paths: PathIndex, source: str, dest: str) -> float | None:
    """Shortest source->dest distance from the index, or None if unreachable."""
    dist, _ = paths[dest]
    return dist.get(source)


def _route(paths: PathIndex, source: str, dest: str) -> list[str]:
    """Rebuild the source->dest path from the index (empty if unreachable).

    ``prev`` (rooted at ``dest``) points each node toward ``dest``, so walking it
    from ``source`` yields the hops in travel order (source -> ... -> dest).
    """
    dist, prev = paths[dest]
    if source not in dist:
        return []
    path = [source]
    while path[-1] != dest:
        path.append(prev[path[-1]])
    return path


def find_candidates(
    request: FoodRequest,
    foodbanks: list[Foodbank],
    graph: DeliveryGraph,
    today: date | None = None,
    top_n: int = 2,
    paths: PathIndex | None = None,
) -> list[MatchCandidate]:
    """Rank the best source foodbanks for a single request (top ``top_n``).

    A candidate is any *other* bank that stocks the requested category and can be
    reached over the delivery graph. Each bank contributes its soonest-to-expire
    product in that category (the one most worth rescuing). Candidates are ranked
    by the blended score via the custom PriorityQueue, then the best few returned.

    ``paths`` is a prebuilt path index (see ``build_path_index``); when omitted it
    is built just for this request's destination so distances are still lookups.
    """
    today = today or date.today()
    if paths is None:
        # Only this request's destination is needed for a single-request lookup.
        paths = build_path_index(graph, [request.foodbank_id])
    # Sources are ranked in a min-heap keyed on score, so the best is popped first.
    ranked = PriorityQueue()

    for source in foodbanks:
        if source.foodbank_id == request.foodbank_id:
            continue  # a bank cannot serve its own request

        # Build the source's inventory and pull only the requested category,
        # already ordered soonest-expiry-first by the Inventory heap.
        lines = Inventory.from_foodbank(source).by_category(request.category)
        if not lines:
            continue  # nothing usable in this category here

        # by_category is sorted soonest-first, so the first line's product is the
        # one most worth rescuing from this bank.
        food_item, soonest_batch = lines[0]
        available = food_item.total_quantity()
        # Cap the offer at what the request needs; a smaller value = partial fill.
        fill_quantity = min(available, request.quantity)
        if fill_quantity <= 0:
            continue

        # Delivery cost from this source to the requester (may be multi-hop),
        # read from the precomputed index instead of a fresh Dijkstra.
        distance_km = _distance(paths, source.foodbank_id, request.foodbank_id)
        if distance_km is None:
            continue  # unreachable within the delivery network

        # Days of shelf life left on the batch we would rescue drives the score.
        days_to_expiry = (soonest_batch.expiry_date - today).days
        score = score_pair(request, distance_km, days_to_expiry, today)
        candidate = MatchCandidate(
            request=request,
            source_id=source.foodbank_id,
            dest_id=request.foodbank_id,
            food_item=food_item,
            fill_quantity=fill_quantity,
            days_to_expiry=days_to_expiry,
            distance_km=distance_km,
            route=[],  # filled in only for the returned top_n below
            score=score,
        )
        # Queue this source keyed on its score (lower = better).
        ranked.push(candidate, score)

    # Pop the best ``top_n`` sources; the heap yields them in ascending score.
    best: list[MatchCandidate] = []
    while not ranked.is_empty() and len(best) < top_n:
        best.append(ranked.pop())
    # Optimization: rebuild routes only for the few candidates we return, not every
    # source (route reconstruction is wasted on sources that never make the top_n).
    for candidate in best:
        candidate.route = _route(paths, candidate.source_id, request.foodbank_id)
    return best


def find_all(
    foodbanks: list[Foodbank],
    requests: list[FoodRequest],
    today: date | None = None,
    top_n: int = 2,
) -> list[tuple[FoodRequest, list[MatchCandidate]]]:
    """Candidates for every request, most-urgent request first.

    Requests are ordered by the RequestQueue (urgency blended with waiting time),
    so the returned list mirrors the order the network would actually serve them.
    """
    today = today or date.today()
    # Serve the most urgent request first (urgency blended with waiting time).
    ordered = RequestQueue.from_requests(requests, today).pending(today)
    # Build the delivery graph once and reuse it for every request's ranking.
    graph = graph_for(foodbanks)
    # One Dijkstra per distinct requester, reused across every candidate lookup.
    paths = build_path_index(graph, [r.foodbank_id for r in ordered])
    return [
        (request, find_candidates(request, foodbanks, graph, today, top_n, paths))
        for request in ordered
    ]


def allocate(
    foodbanks: list[Foodbank],
    requests: list[FoodRequest],
    graph: DeliveryGraph,
    today: date | None = None,
    paths: PathIndex | None = None,
    inv_by_source: dict | None = None,
) -> list[MatchCandidate]:
    """Resolve contention: hand each scarce item to the requests that deserve it.

    Unlike ``find_candidates`` (which ranks sources for one request in isolation),
    this scores *every* feasible (request, source) pairing on one shared scale and
    then allocates greedily best-first. Because a source's stock is decremented as
    it is committed, a scarce item goes to whichever competing bank scores lowest
    -- so a close, low-urgency need can beat a far, critical one when the weights
    say the closer rescue is worth more, and vice versa. Requests can be filled
    across several sources; a source can serve several requests until it runs dry.

    ``paths`` (path index) and ``inv_by_source`` (persistent Inventory per bank)
    may be supplied by the caller to avoid rebuilding them on every call; both are
    built here when omitted, preserving the standalone behaviour.
    """
    today = today or date.today()
    if paths is None:
        # One Dijkstra per distinct requester covers every source->dest lookup.
        paths = build_path_index(graph, [r.foodbank_id for r in requests])
    if inv_by_source is None:
        inv_by_source = {fb.foodbank_id: Inventory.from_foodbank(fb) for fb in foodbanks}

    # Optimization: precompute each source's soonest-to-expire line per category
    # *once*, so the inner loop is an O(1) dict lookup instead of rebuilding a
    # category heap for every (request, source) pair. src -> category -> (item, batch).
    soonest_by_source: dict[str, dict[str, tuple]] = {}
    for fb in foodbanks:
        inv = inv_by_source[fb.foodbank_id]
        per_category: dict[str, tuple] = {}
        for category in inv.categories():
            lines = inv.by_category(category)
            if lines:
                per_category[category] = lines[0]  # soonest (product, batch) in category
        soonest_by_source[fb.foodbank_id] = per_category

    # Score every candidate pairing once, into a single min-heap.
    pairs = PriorityQueue()
    for request in requests:
        for source in foodbanks:
            if source.foodbank_id == request.foodbank_id:
                continue  # a bank cannot serve its own request

            entry = soonest_by_source[source.foodbank_id].get(request.category)
            if entry is None:
                continue  # nothing usable in this category here
            food_item, soonest_batch = entry  # soonest-to-expire = most worth rescuing

            distance_km = _distance(paths, source.foodbank_id, request.foodbank_id)
            if distance_km is None:
                continue  # unreachable within the delivery network

            days_to_expiry = (soonest_batch.expiry_date - today).days
            score = score_pair(request, distance_km, days_to_expiry, today)
            # Item carries everything needed to build the allocation once popped.
            pairs.push(
                (request, source.foodbank_id, food_item, days_to_expiry, distance_km),
                score,
            )

    # Shared ledgers so competing pairings see each other's commitments.
    remaining_need = {r.request_id: r.quantity for r in requests}
    remaining_stock: dict[tuple[str, str], int] = {}

    allocations: list[MatchCandidate] = []
    # Drain best-first: each pop is the globally best still-standing pairing.
    while not pairs.is_empty():
        request, source_id, food_item, days_to_expiry, distance_km = pairs.pop()

        need = remaining_need.get(request.request_id, 0)
        if need <= 0:
            continue  # this request is already fully covered by better pairings

        key = (source_id, food_item.food_id)
        # First time we touch this product, seed its live available quantity.
        if key not in remaining_stock:
            remaining_stock[key] = food_item.total_quantity()
        available = remaining_stock[key]
        if available <= 0:
            continue  # this product's stock was claimed by better pairings

        fill = min(need, available)  # partial fill when either side is smaller
        remaining_need[request.request_id] = need - fill
        remaining_stock[key] = available - fill

        # Recompute the score for the actual (request, source) so it reflects the
        # winning pairing (score_pair is stable, so this equals the heap key).
        score = score_pair(request, distance_km, days_to_expiry, today)
        # Optimization: rebuild the route only for pairings that actually win stock,
        # not for every scored pair (most pairs lose contention and are discarded).
        route = _route(paths, source_id, request.foodbank_id)
        allocations.append(
            MatchCandidate(
                request=request,
                source_id=source_id,
                dest_id=request.foodbank_id,
                food_item=food_item,
                fill_quantity=fill,
                days_to_expiry=days_to_expiry,
                distance_km=distance_km,
                route=route,
                score=score,
            )
        )

    return allocations


def graph_for(foodbanks: list[Foodbank]) -> DeliveryGraph:
    """Build the delivery graph used for matching (shared threshold)."""
    from src.constants import DELIVERY_THRESHOLD_KM

    return DeliveryGraph.from_foodbanks(foodbanks, threshold_km=DELIVERY_THRESHOLD_KM)


def apply_transfer(food_item: FoodItem, quantity: int) -> int:
    """Remove ``quantity`` from a product's active batches, soonest-first.

    Depleted batches are dropped. Returns the amount actually removed (which is
    less than ``quantity`` only if the product held less than requested).
    """
    remaining = quantity
    for batch in sorted(food_item.active_batches(), key=lambda b: b.expiry_date):
        if remaining <= 0:
            break
        taken = min(batch.quantity, remaining)
        batch.quantity -= taken
        remaining -= taken
    # Drop emptied batches so they never resurface as stock.
    food_item.batches = [b for b in food_item.batches if b.quantity > 0]
    return quantity - remaining


def execute_match(candidate: MatchCandidate, today: date | None = None) -> DonationRecord:
    """Rescue the matched food: remove it from the source only, and record it.

    The donated quantity is taken out of the source inventory and is deliberately
    *not* added to the destination -- a confirmed donation means the food was
    rescued/used, and re-stocking the receiver would just move the same
    near-expiry batch and raise a false expiry alarm elsewhere. The returned
    DonationRecord is the sole evidence the batch was saved.
    """
    removed = apply_transfer(candidate.food_item, candidate.fill_quantity)
    return DonationRecord(
        record_id=generate_donation_id(),
        food_id=candidate.food_item.food_id,
        from_foodbank_id=candidate.source_id,
        to_foodbank_id=candidate.dest_id,
        quantity=removed,
        transfer_date=today or date.today(),
        status="Fulfilled",
    )
