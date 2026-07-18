from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.data import FOODBANKS, OUR_FOODBANK
from src.data_structures.priority_queue import PriorityQueue

st.set_page_config(
    page_title="Food Rescue Network",
    page_icon="🍎",
    layout="wide",
)


def order_by_expiry(food_items):
    """Return food items soonest-to-expire first, ordered via the min-heap."""
    pq = PriorityQueue()
    for item in food_items:
        pq.push(item, item.expiry_date.toordinal())
    return [pq.pop() for _ in range(len(pq))]


st.title("Food Rescue Network")
st.caption("Foodbank locations across the network")

map_col, panel_col = st.columns([3, 2])

with map_col:
    fmap = folium.Map(
        location=[OUR_FOODBANK.latitude, OUR_FOODBANK.longitude],
        zoom_start=12,
        tiles="cartodbpositron",
    )

    folium.Marker(
        location=[OUR_FOODBANK.latitude, OUR_FOODBANK.longitude],
        tooltip=OUR_FOODBANK.name,
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(fmap)

    for fb in FOODBANKS:
        folium.Marker(
            location=[fb.latitude, fb.longitude],
            tooltip=fb.name,
            icon=folium.Icon(color="blue", icon="cutlery", prefix="fa"),
        ).add_to(fmap)

    map_state = st_folium(fmap, width=700, height=520)

with panel_col:
    clicked_name = None
    if map_state and map_state.get("last_object_clicked_tooltip"):
        clicked_name = map_state["last_object_clicked_tooltip"]

    all_foodbanks = [OUR_FOODBANK] + FOODBANKS
    selected = next((fb for fb in all_foodbanks if fb.name == clicked_name), None)

    if selected is None:
        st.info("Click a foodbank marker on the map to view its inventory.")
    else:
        st.subheader(selected.name)
        st.caption(f"{selected.foodbank_id} · {selected.address}")

        ordered = order_by_expiry(selected.food_items)

        if not ordered:
            st.info("No inventory recorded for this foodbank.")
        else:
            st.caption("Sorted by expiry — top spoils soonest, bottom is farthest out.")
            today = date.today()
            rows = [
                {
                    "Food": item.name,
                    "Qty": f"{item.quantity} {item.unit}",
                    "Expiry": item.expiry_date.strftime("%Y-%m-%d"),
                    "Days Left": (item.expiry_date - today).days,
                }
                for item in ordered
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
