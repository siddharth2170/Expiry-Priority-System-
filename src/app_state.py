from __future__ import annotations

import copy

import streamlit as st

from src.data import ALL_REQUESTS, FOODBANKS, OUR_FOODBANK
from src.matching.engine import MatchCandidate, execute_match
from src.models import DonationRecord, FoodItem, Foodbank, FoodRequest

FOODBANKS_KEY = "network_foodbanks"
REQUESTS_KEY = "network_requests"
DONATIONS_KEY = "network_donations"


def _ensure_state() -> None:
    # Deep-copy the whole network into session state so confirming a donation
    # mutates only this session's copy, never the pristine module-level seed data.
    if FOODBANKS_KEY not in st.session_state:
        st.session_state[FOODBANKS_KEY] = copy.deepcopy([OUR_FOODBANK] + FOODBANKS)
    if REQUESTS_KEY not in st.session_state:
        st.session_state[REQUESTS_KEY] = copy.deepcopy(ALL_REQUESTS)
    if DONATIONS_KEY not in st.session_state:
        st.session_state[DONATIONS_KEY] = []


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


def get_all_requests() -> list[FoodRequest]:
    _ensure_state()
    return st.session_state[REQUESTS_KEY]


def add_request(request: FoodRequest) -> None:
    _ensure_state()
    st.session_state[REQUESTS_KEY].append(request)


def remove_request(request_id: str) -> bool:
    _ensure_state()
    requests = st.session_state[REQUESTS_KEY]
    for i, request in enumerate(requests):
        if request.request_id == request_id:
            del requests[i]
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
            return


def record_donation(record: DonationRecord) -> None:
    _ensure_state()
    st.session_state[DONATIONS_KEY].append(record)


def get_donations() -> list[DonationRecord]:
    _ensure_state()
    return st.session_state[DONATIONS_KEY]


def confirm_match(candidate: MatchCandidate) -> DonationRecord:
    """Confirm a match: rescue the food, log the donation, serve the request.

    Removes the donated quantity from the source only (terminal rescue), records
    the donation, and reduces/removes the served request. If the source product
    is fully depleted, it is dropped from the source's inventory.
    """
    record = execute_match(candidate)
    record_donation(record)
    reduce_request(candidate.request.request_id, record.quantity)

    source = get_foodbank(candidate.source_id)
    if source is not None and not candidate.food_item.batches:
        source.food_items = [
            it for it in source.food_items if it is not candidate.food_item
        ]
    return record
