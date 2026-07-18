from datetime import date

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.app_state import (
    get_all_requests,
    get_allocations,
    get_donations,
    get_foodbanks,
    get_graph,
    get_inventories,
    get_path_index,
)
from src.constants import DELIVERY_THRESHOLD_KM
from src.data import OUR_FOODBANK
from src.data_structures.expiry_log import ExpiryLog
from src.matching.engine import find_candidates

st.set_page_config(
    page_title="Food Rescue Network",
    page_icon="🍎",
    layout="wide",
)

st.title("Food Rescue Network")
st.caption(
    "Grey lines are delivery routes (labelled with distance). The green line is "
    "the engine's top recommended transfer for our hub right now. Click a "
    "foodbank to see its inventory and highlight the shortest path from our hub "
    "(blue)."
)

all_foodbanks = get_foodbanks()
other_foodbanks = [
    fb for fb in all_foodbanks if fb.foodbank_id != OUR_FOODBANK.foodbank_id
]
by_name = {fb.name: fb for fb in all_foodbanks}
name_by_id = {fb.foodbank_id: fb.name for fb in all_foodbanks}
coords = {fb.foodbank_id: [fb.latitude, fb.longitude] for fb in all_foodbanks}

graph = get_graph()

# The clicked bank persists in session state so the map can be redrawn with the
# route highlighted on the next run.
selected = by_name.get(st.session_state.get("selected_foodbank"))

# The engine's current top recommendation for OUR hub, drawn in green. We run the
# full network allocation (so contention is respected -- our hub only "wins" an
# item if it out-scores every other bank competing for it) then keep the best
# transfer that lands at our hub. Memoized on the network version, so idle reruns
# (like clicking a marker) reuse the plan instead of recomputing it.
_allocations = get_allocations(date.today())
_hub_allocs = [a for a in _allocations if a.dest_id == OUR_FOODBANK.foodbank_id]
recommended = min(_hub_allocs, key=lambda a: a.score) if _hub_allocs else None

def render_match_with_hub(clicked) -> None:
    """Show whether our hub can serve one of the clicked bank's requests.

    A "match with our hub" means the clicked bank requested a category that our
    hub stocks, so we (the hub) could be the source. Banks whose requests we
    cannot serve simply show no row.
    """
    hub = next(
        fb for fb in all_foodbanks if fb.foodbank_id == OUR_FOODBANK.foodbank_id
    )
    today = date.today()
    rows = []
    for req in get_all_requests():
        if req.foodbank_id != clicked.foodbank_id:
            continue
        # Restrict the source pool to just our hub: a candidate appears only if
        # our hub actually stocks the requested category and can reach them.
        candidates = find_candidates(
            req, [hub], graph, today, top_n=1, paths=get_path_index()
        )
        if not candidates:
            continue
        c = candidates[0]
        rows.append(
            {
                "Their Request": f"{req.quantity} {req.category}",
                "We Send": c.food_item.name,
                "Qty": f"{c.fill_quantity}/{req.quantity}"
                + (" ⚠️" if c.is_partial else ""),
                "Days Left": c.days_to_expiry,
                "Distance": f"{c.distance_km:.1f} km",
            }
        )

    st.markdown(f"**Match with {OUR_FOODBANK.name}**")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Confirm this transfer on the Transfer Matches page.")
    else:
        st.caption(f"No match with {OUR_FOODBANK.name} for this bank's requests.")


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

    # Auto-highlight the engine's top recommended transfer (source -> requester).
    if recommended is not None and recommended.route:
        folium.PolyLine(
            [coords[node] for node in recommended.route],
            color="#2ca02c",
            weight=5,
            opacity=0.9,
            tooltip=(
                f"Recommended: rescue {recommended.fill_quantity} "
                f"{recommended.request.category} "
                f"{name_by_id[recommended.source_id]} -> "
                f"{name_by_id[recommended.dest_id]}"
            ),
        ).add_to(fmap)

    # Markers last so they sit on top of the lines.
    folium.Marker(
        location=coords[OUR_FOODBANK.foodbank_id],
        tooltip=OUR_FOODBANK.name,
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(fmap)
    for fb in other_foodbanks:
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

    if recommended is not None:
        st.caption(
            f"Recommended transfer (green): rescue **{recommended.fill_quantity} "
            f"{recommended.request.category}** from "
            f"**{name_by_id[recommended.source_id]}** to "
            f"**{name_by_id[recommended.dest_id]}** "
            f"({recommended.distance_km:.1f} km). Confirm it on the Transfer "
            f"Matches page."
        )

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

        ordered = get_inventories()[selected.foodbank_id].items()

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

        # For any other bank, show whether our hub can serve one of its requests
        # (a match between it and us). Our own hub shows just its inventory.
        if selected.foodbank_id != OUR_FOODBANK.foodbank_id:
            render_match_with_hub(selected)

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

st.divider()
st.subheader("Recent rescues")

donations = get_donations()
if not donations:
    st.info(
        "No donations confirmed yet. Confirm matches on the Transfer Matches page "
        "to rescue near-expiry food."
    )
else:
    st.caption(f"{len(donations)} confirmed donations across the network")
    rescue_rows = [
        {
            "From": name_by_id.get(rec.from_foodbank_id, rec.from_foodbank_id),
            "To": name_by_id.get(rec.to_foodbank_id, rec.to_foodbank_id),
            "Units": rec.quantity,
            "Date": rec.transfer_date.strftime("%Y-%m-%d"),
            "Status": rec.status,
        }
        for rec in reversed(donations)
    ]
    st.dataframe(rescue_rows, use_container_width=True, hide_index=True)
