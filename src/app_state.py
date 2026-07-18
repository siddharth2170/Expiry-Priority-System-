from __future__ import annotations

import copy

import streamlit as st

from src.data import ALL_REQUESTS, FOODBANKS, OUR_FOODBANK
from src.data_structures.delivery_graph import DeliveryGraph
from src.data_structures.inventory import Inventory
from src.matching.engine import (
    MatchCandidate,
    allocate,
    build_path_index,
    execute_match,
    graph_for,
)
from src.models import DonationRecord, FoodItem, Foodbank, FoodRequest

FOODBANKS_KEY = "network_foodbanks"
REQUESTS_KEY = "network_requests"
DONATIONS_KEY = "network_donations"
VERSION_KEY = "network_version"

# Optimization: Streamlit reruns the whole script on every interaction, so cache
# derived structures in session state instead of rebuilding them each time.
# Graph/path-index depend only on (static) coordinates; the inventories are
# persistent and mutated in place; allocations are memoized on the network version
# so idle reruns (e.g. clicking a marker) reuse the result rather than recompute.
GRAPH_KEY = "cache_graph"
PATHIDX_KEY = "cache_path_index"
INVENTORIES_KEY = "cache_inventories"
ALLOC_KEY = "cache_allocations"


def _ensure_state() -> None:
    # Deep-copy the whole network into session state so confirming a donation
    # mutates only this session's copy, never the pristine module-level seed data.
    if FOODBANKS_KEY not in st.session_state:
        st.session_state[FOODBANKS_KEY] = copy.deepcopy([OUR_FOODBANK] + FOODBANKS)
    if REQUESTS_KEY not in st.session_state:
        st.session_state[REQUESTS_KEY] = copy.deepcopy(ALL_REQUESTS)
    if DONATIONS_KEY not in st.session_state:
        st.session_state[DONATIONS_KEY] = []
    if VERSION_KEY not in st.session_state:
        st.session_state[VERSION_KEY] = 0


def _version() -> int:
    _ensure_state()
    return st.session_state[VERSION_KEY]


def _bump_version() -> None:
    # Any mutation of stock or requests invalidates the memoized allocations.
    _ensure_state()
    st.session_state[VERSION_KEY] += 1


def get_foodbanks() -> list[Foodbank]:
    _ensure_state()
    return st.session_state[FOODBANKS_KEY]


def get_foodbank(foodbank_id: str) -> Foodbank | None:
    return next((fb for fb in get_foodbanks() if fb.foodbank_id == foodbank_id), None)


def get_inventory() -> list[FoodItem]:
    """Our own hub's inventory (the mutable session copy)."""
    hub = get_foodbank(OUR_FOODBANK.foodbank_id)
    return hub.food_items if hub else []


def add_food_item(item: FoodItem) -> None:
    hub = get_foodbank(OUR_FOODBANK.foodbank_id)
    if hub is not None:
        hub.food_items.append(item)
        # Keep the persistent inventory in sync instead of rebuilding it.
        inventories = st.session_state.get(INVENTORIES_KEY)
        if inventories is not None and hub.foodbank_id in inventories:
            inventories[hub.foodbank_id].add(item)
        _bump_version()


def get_all_requests() -> list[FoodRequest]:
    _ensure_state()
    return st.session_state[REQUESTS_KEY]


def add_request(request: FoodRequest) -> None:
    _ensure_state()
    st.session_state[REQUESTS_KEY].append(request)
    _bump_version()


def remove_request(request_id: str) -> bool:
    _ensure_state()
    requests = st.session_state[REQUESTS_KEY]
    for i, request in enumerate(requests):
        if request.request_id == request_id:
            del requests[i]
            _bump_version()
            return True
    return False


def reduce_request(request_id: str, quantity: int) -> None:
    """Reduce a request's outstanding quantity; remove it once fully served."""
    _ensure_state()
    for request in st.session_state[REQUESTS_KEY]:
        if request.request_id == request_id:
            request.quantity -= quantity
            if request.quantity <= 0:
                remove_request(request_id)
            else:
                _bump_version()
            return


def record_donation(record: DonationRecord) -> None:
    _ensure_state()
    st.session_state[DONATIONS_KEY].append(record)
    _bump_version()


def get_donations() -> list[DonationRecord]:
    _ensure_state()
    return st.session_state[DONATIONS_KEY]


# --- Cached derived structures -------------------------------------------


def get_graph() -> DeliveryGraph:
    """Delivery graph, built once per session (coordinates never change)."""
    _ensure_state()
    graph = st.session_state.get(GRAPH_KEY)
    if graph is None:
        graph = graph_for(get_foodbanks())
        st.session_state[GRAPH_KEY] = graph
    return graph


def get_path_index():
    """Path index (one Dijkstra per bank), built once per session."""
    _ensure_state()
    paths = st.session_state.get(PATHIDX_KEY)
    if paths is None:
        paths = build_path_index(get_graph(), [fb.foodbank_id for fb in get_foodbanks()])
        st.session_state[PATHIDX_KEY] = paths
    return paths


def get_inventories() -> dict[str, Inventory]:
    """Persistent per-bank inventories, built once and mutated in place.

    Safe to keep long-lived because ``Inventory.by_category``/``items`` read live
    from ``_by_id`` + ``active_batches()``, so in-place batch changes (from a
    confirmed transfer) are reflected without a rebuild.
    """
    _ensure_state()
    inventories = st.session_state.get(INVENTORIES_KEY)
    if inventories is None:
        inventories = {
            fb.foodbank_id: Inventory.from_foodbank(fb) for fb in get_foodbanks()
        }
        st.session_state[INVENTORIES_KEY] = inventories
    return inventories


def get_allocations(today=None) -> list[MatchCandidate]:
    """Contention-aware allocation plan, memoized on the network version.

    Recomputed only when stock/requests change (or the day rolls over); idle
    reruns such as clicking a map marker reuse the cached plan.
    """
    _ensure_state()
    from datetime import date

    today = today or date.today()
    key = (_version(), today.toordinal())
    cached = st.session_state.get(ALLOC_KEY)
    if cached is None or cached[0] != key:
        allocations = allocate(
            get_foodbanks(),
            get_all_requests(),
            get_graph(),
            today,
            paths=get_path_index(),
            inv_by_source=get_inventories(),
        )
        st.session_state[ALLOC_KEY] = (key, allocations)
    return st.session_state[ALLOC_KEY][1]


def confirm_match(candidate: MatchCandidate) -> DonationRecord:
    """Confirm a match: rescue the food, log the donation, serve the request.

    Removes the donated quantity from the source only (terminal rescue), records
    the donation, and reduces/removes the served request. If the source product
    is fully depleted, it is dropped from the source's inventory (both the
    foodbank's list and the persistent Inventory index).
    """
    record = execute_match(candidate)
    record_donation(record)
    reduce_request(candidate.request.request_id, record.quantity)

    source = get_foodbank(candidate.source_id)
    if source is not None and not candidate.food_item.batches:
        source.food_items = [
            it for it in source.food_items if it is not candidate.food_item
        ]
        inventories = st.session_state.get(INVENTORIES_KEY)
        if inventories is not None and candidate.source_id in inventories:
            inventories[candidate.source_id].remove(candidate.food_item.food_id)
    _bump_version()
    return record
