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


def find_candidates(
    request: FoodRequest,
    foodbanks: list[Foodbank],
    graph: DeliveryGraph,
    today: date | None = None,
    top_n: int = 2,
) -> list[MatchCandidate]:
    """Rank the best source foodbanks for a single request (top ``top_n``).

    A candidate is any *other* bank that stocks the requested category and can be
    reached over the delivery graph. Each bank contributes its soonest-to-expire
    product in that category (the one most worth rescuing). Candidates are ranked
    by the blended score via the custom PriorityQueue, then the best few returned.
    """
    today = today or date.today()
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

        # Delivery cost from this source to the requester (may be multi-hop).
        distance_km, route = graph.shortest_path(
            source.foodbank_id, request.foodbank_id
        )
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
            route=route,
            score=score,
        )
        # Queue this source keyed on its score (lower = better).
        ranked.push(candidate, score)

    # Pop the best ``top_n`` sources; the heap yields them in ascending score.
    best: list[MatchCandidate] = []
    while not ranked.is_empty() and len(best) < top_n:
        best.append(ranked.pop())
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
    return [
        (request, find_candidates(request, foodbanks, graph, today, top_n))
        for request in ordered
    ]


def allocate(
    foodbanks: list[Foodbank],
    requests: list[FoodRequest],
    graph: DeliveryGraph,
    today: date | None = None,
) -> list[MatchCandidate]:
    """Resolve contention: hand each scarce item to the requests that deserve it.

    Unlike ``find_candidates`` (which ranks sources for one request in isolation),
    this scores *every* feasible (request, source) pairing on one shared scale and
    then allocates greedily best-first. Because a source's stock is decremented as
    it is committed, a scarce item goes to whichever competing bank scores lowest
    -- so a close, low-urgency need can beat a far, critical one when the weights
    say the closer rescue is worth more, and vice versa. Requests can be filled
    across several sources; a source can serve several requests until it runs dry.
    """
    today = today or date.today()

    # Score every candidate pairing once, into a single min-heap. We build each
    # source's Inventory a single time (not per request) and reuse it.
    pairs = PriorityQueue()
    inv_by_source = {fb.foodbank_id: Inventory.from_foodbank(fb) for fb in foodbanks}
    for request in requests:
        for source in foodbanks:
            if source.foodbank_id == request.foodbank_id:
                continue  # a bank cannot serve its own request

            lines = inv_by_source[source.foodbank_id].by_category(request.category)
            if not lines:
                continue  # nothing usable in this category here

            food_item, soonest_batch = lines[0]  # soonest-to-expire = most worth rescuing
            distance_km, route = graph.shortest_path(
                source.foodbank_id, request.foodbank_id
            )
            if distance_km is None:
                continue  # unreachable within the delivery network

            days_to_expiry = (soonest_batch.expiry_date - today).days
            score = score_pair(request, distance_km, days_to_expiry, today)
            # Item carries everything needed to build the allocation once popped.
            pairs.push(
                (request, source.foodbank_id, food_item, days_to_expiry, distance_km, route),
                score,
            )

    # Shared ledgers so competing pairings see each other's commitments.
    remaining_need = {r.request_id: r.quantity for r in requests}
    remaining_stock: dict[tuple[str, str], int] = {}

    allocations: list[MatchCandidate] = []
    # Drain best-first: each pop is the globally best still-standing pairing.
    while not pairs.is_empty():
        request, source_id, food_item, days_to_expiry, distance_km, route = pairs.pop()

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
