from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.data import FOODBANKS, OUR_FOODBANK
from src.data_structures.expiry_log import ExpiryLog
from src.data_structures.inventory import Inventory

st.set_page_config(
    page_title="Food Rescue Network",
    page_icon="🍎",
    layout="wide",
)

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

        ordered = Inventory.from_foodbank(selected).items()

        if not ordered:
            st.info("No inventory recorded for this foodbank.")
        else:
            st.caption("Sorted by expiry — top spoils soonest, bottom is farthest out.")
            today = date.today()
            rows = [
                {
                    "Food": item.name,
                    "Qty": f"{batch.quantity} {item.unit}",
                    "Expiry": batch.expiry_date.strftime("%Y-%m-%d"),
                    "Days Left": (batch.expiry_date - today).days,
                }
                for item, batch in ordered
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Expired items across the network")

all_foodbanks = [OUR_FOODBANK] + FOODBANKS
expiry_log = ExpiryLog.from_foodbanks(all_foodbanks)

if len(expiry_log) == 0:
    st.success("No expired items recorded across the network.")
else:
    st.caption(
        f"{len(expiry_log)} expired batches · "
        f"{expiry_log.total_expired_quantity()} units total"
    )
    today = date.today()
    name_by_id = {fb.foodbank_id: fb.name for fb in all_foodbanks}
    grouped = expiry_log.grouped_by_foodbank()

    for fb_id in sorted(grouped):
        entries = grouped[fb_id]
        fb_name = name_by_id.get(fb_id, fb_id)
        with st.expander(f"{fb_name} — {len(entries)} expired", expanded=True):
            rows = [
                {
                    "Food": item.name,
                    "Qty": f"{batch.quantity} {item.unit}",
                    "Expired On": batch.expiry_date.strftime("%Y-%m-%d"),
                    "Days Ago": (today - batch.expiry_date).days,
                }
                for item, batch in entries
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
