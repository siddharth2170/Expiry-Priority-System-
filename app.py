from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.data import FOODBANKS, OUR_FOODBANK
from src.data_structures.delivery_graph import DeliveryGraph
from src.data_structures.expiry_log import ExpiryLog
from src.data_structures.inventory import Inventory

# Only connect banks within this many km directly; farther banks must route
# through closer ones, so the shortest path becomes multi-hop and visible.
DELIVERY_THRESHOLD_KM = 4.5

st.set_page_config(
    page_title="Food Rescue Network",
    page_icon="🍎",
    layout="wide",
)

st.title("Food Rescue Network")
st.caption(
    "Grey lines are delivery routes (labelled with distance). Click a foodbank "
    "to see its inventory and highlight the shortest path from our hub."
)

all_foodbanks = [OUR_FOODBANK] + FOODBANKS
by_name = {fb.name: fb for fb in all_foodbanks}
name_by_id = {fb.foodbank_id: fb.name for fb in all_foodbanks}
coords = {fb.foodbank_id: [fb.latitude, fb.longitude] for fb in all_foodbanks}

graph = DeliveryGraph.from_foodbanks(all_foodbanks, threshold_km=DELIVERY_THRESHOLD_KM)

# The clicked bank persists in session state so the map can be redrawn with the
# route highlighted on the next run.
selected = by_name.get(st.session_state.get("selected_foodbank"))

map_col, panel_col = st.columns([3, 2])

with map_col:
    fmap = folium.Map(
        location=[OUR_FOODBANK.latitude, OUR_FOODBANK.longitude],
        zoom_start=12,
        tiles="cartodbpositron",
    )

    # Base network: one grey line per undirected edge, tooltip = distance.
    drawn = set()
    for node in graph.nodes():
        for neighbor, distance in graph.neighbors(node):
            edge = frozenset((node, neighbor))
            if edge in drawn:
                continue
            drawn.add(edge)
            folium.PolyLine(
                [coords[node], coords[neighbor]],
                color="#9aa0a6",
                weight=2,
                opacity=0.5,
                tooltip=f"{distance:.1f} km",
            ).add_to(fmap)

    # Highlight the shortest path from our hub to the selected bank.
    if selected is not None and selected.foodbank_id != OUR_FOODBANK.foodbank_id:
        route_distance, route = graph.shortest_path(
            OUR_FOODBANK.foodbank_id, selected.foodbank_id
        )
        if route:
            folium.PolyLine(
                [coords[node] for node in route],
                color="#1f77b4",
                weight=5,
                opacity=0.9,
                tooltip=f"{route_distance:.1f} km via {len(route) - 1} hop(s)",
            ).add_to(fmap)

    # Markers last so they sit on top of the lines.
    folium.Marker(
        location=coords[OUR_FOODBANK.foodbank_id],
        tooltip=OUR_FOODBANK.name,
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(fmap)
    for fb in FOODBANKS:
        folium.Marker(
            location=coords[fb.foodbank_id],
            tooltip=fb.name,
            icon=folium.Icon(color="blue", icon="cutlery", prefix="fa"),
        ).add_to(fmap)

    map_state = st_folium(fmap, width=700, height=520)

    # Persist a new click and redraw so the highlighted route appears.
    clicked_name = map_state.get("last_object_clicked_tooltip") if map_state else None
    if clicked_name and clicked_name != st.session_state.get("selected_foodbank"):
        st.session_state["selected_foodbank"] = clicked_name
        st.rerun()

with panel_col:
    if selected is None:
        st.info("Click a foodbank marker on the map to view its inventory.")
    else:
        st.subheader(selected.name)
        st.caption(f"{selected.foodbank_id} · {selected.address}")

        if selected.foodbank_id != OUR_FOODBANK.foodbank_id:
            route_distance, route = graph.shortest_path(
                OUR_FOODBANK.foodbank_id, selected.foodbank_id
            )
            if route_distance is not None:
                st.metric(f"Distance from {OUR_FOODBANK.name}", f"{route_distance:.1f} km")
                st.caption("Route: " + " → ".join(name_by_id[node] for node in route))
            else:
                st.caption(f"No delivery route within {DELIVERY_THRESHOLD_KM:.0f} km hops.")

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

expiry_log = ExpiryLog.from_foodbanks(all_foodbanks)

if len(expiry_log) == 0:
    st.success("No expired items recorded across the network.")
else:
    st.caption(
        f"{len(expiry_log)} expired batches · "
        f"{expiry_log.total_expired_quantity()} units total"
    )
    today = date.today()
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
