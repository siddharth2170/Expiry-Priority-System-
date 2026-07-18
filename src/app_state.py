import copy

import streamlit as st

from src.data import OUR_INVENTORY
from src.models import FoodItem, FoodRequest

INVENTORY_KEY = "our_inventory"
REQUESTS_KEY = "our_requests"


def _ensure_state() -> None:
    if INVENTORY_KEY not in st.session_state:
        st.session_state[INVENTORY_KEY] = copy.deepcopy(OUR_INVENTORY)
    if REQUESTS_KEY not in st.session_state:
        st.session_state[REQUESTS_KEY] = []


def get_inventory() -> list[FoodItem]:
    _ensure_state()
    return st.session_state[INVENTORY_KEY]


def add_food_item(item: FoodItem) -> None:
    _ensure_state()
    st.session_state[INVENTORY_KEY].append(item)


def get_requests() -> list[FoodRequest]:
    _ensure_state()
    return st.session_state[REQUESTS_KEY]


def add_request(request: FoodRequest) -> None:
    _ensure_state()
    st.session_state[REQUESTS_KEY].append(request)
