from datetime import date

import streamlit as st

from src.app_state import (
    confirm_match,
    get_all_requests,
    get_allocations,
    get_donations,
    get_foodbanks,
    get_graph,
    get_path_index,
)
from src.data_structures.transaction_log import TransactionLog
from src.matching.engine import find_candidates

st.set_page_config(page_title="Matches", page_icon="🤝", layout="wide")

st.title("Transfer Matches")
st.caption(
    "The engine scores every (request, source) pairing on one scale — urgency, "
    "expiry pressure, and delivery distance — then allocates scarce stock "
    "best-first, so a contested item goes to whichever bank the weights favour. "
    "Confirm a match to rescue the food (removed from the source) and serve the "
    "request."
)

foodbanks = get_foodbanks()
name_by_id = {fb.foodbank_id: fb.name for fb in foodbanks}
today = date.today()

# --- Rescued-so-far stats -------------------------------------------------
log = TransactionLog.from_records(get_donations())

col_a, col_b = st.columns(2)
col_a.metric("Food rescued", f"{log.total_rescued()} units")
col_b.metric("Confirmed donations", len(log))

rescued_by_source = log.rescued_units_by_source()
if rescued_by_source:
    st.caption("Rescued by source foodbank")
    st.dataframe(
        [
            {"Foodbank": name_by_id.get(fb_id, fb_id), "Units rescued": units}
            for fb_id, units in sorted(
                rescued_by_source.items(), key=lambda kv: kv[1], reverse=True
            )
        ],
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# --- Contention-aware allocation ------------------------------------------
# One global pass scores every (request, source) pairing and hands scarce stock
# to the best-scoring requests first, so the plan already reflects who wins a
# contested item. find_candidates is used only to show the ranked alternatives.
# Graph and allocation plan are cached in session state (memoized on the network
# version), so they are not rebuilt when nothing has changed.
graph = get_graph()
requests = get_all_requests()
allocations = get_allocations(today)

# Index the resolved allocations by the request they serve.
allocs_by_request: dict[str, list] = {}
for alloc in allocations:
    allocs_by_request.setdefault(alloc.request.request_id, []).append(alloc)

if not requests:
    st.success("No open requests in the network.")
else:
    # Group requests by the requesting foodbank for display.
    grouped: dict[str, list] = {}
    for request in requests:
        grouped.setdefault(request.foodbank_id, []).append(request)

    for fb_id in sorted(grouped):
        fb_name = name_by_id.get(fb_id, fb_id)
        reqs = grouped[fb_id]
        with st.expander(f"{fb_name} — {len(reqs)} open request(s)", expanded=True):
            for request in reqs:
                st.markdown(
                    f"**{request.request_id}** · needs **{request.quantity} "
                    f"{request.category}** · _{request.urgency.label}_"
                )

                allocs = allocs_by_request.get(request.request_id, [])
                # Ranked "ideal" sources for this request, ignoring contention.
                candidates = find_candidates(
                    request, foodbanks, graph, today, top_n=2, paths=get_path_index()
                )

                if allocs:
                    header = st.columns([3, 3, 2, 2, 2, 2, 2])
                    for col, label in zip(
                        header,
                        ["Source", "Product", "Qty", "Days left", "Distance", "Score", ""],
                    ):
                        col.caption(label)

                    for rank, alloc in enumerate(allocs):
                        row = st.columns([3, 3, 2, 2, 2, 2, 2])
                        row[0].write(name_by_id.get(alloc.source_id, alloc.source_id))
                        row[1].write(alloc.food_item.name)
                        qty_label = f"{alloc.fill_quantity}/{request.quantity}"
                        if alloc.is_partial:
                            qty_label += " ⚠️"
                        row[2].write(qty_label)
                        row[3].write(str(alloc.days_to_expiry))
                        row[4].write(f"{alloc.distance_km:.1f} km")
                        row[5].write(f"{alloc.score:.1f}")
                        button_type = "primary" if rank == 0 else "secondary"
                        if row[6].button(
                            "Confirm",
                            key=f"confirm_{request.request_id}_{alloc.source_id}",
                            type=button_type,
                            use_container_width=True,
                        ):
                            record = confirm_match(alloc)
                            st.success(
                                f"Rescued {record.quantity} {request.category} from "
                                f"{name_by_id.get(alloc.source_id, alloc.source_id)}."
                            )
                            st.rerun()
                elif candidates:
                    # Some bank could serve it, but its stock was allocated to a
                    # higher-scoring (more deserving) request first: contention.
                    best = candidates[0]
                    st.warning(
                        f"No stock allocated — {name_by_id.get(best.source_id, best.source_id)}"
                        " was the best match but its stock went to a higher-priority "
                        "request. It reopens here once that stock is replenished."
                    )
                else:
                    st.info("No available source for this request.")

                # Ranked comparison so the weighting is transparent for the demo.
                if candidates:
                    ranked = " · ".join(
                        f"{name_by_id.get(c.source_id, c.source_id)} "
                        f"(score {c.score:.1f}, {c.distance_km:.1f} km, "
                        f"{c.days_to_expiry}d left)"
                        for c in candidates
                    )
                    st.caption(f"Ranked by score (lower is better): {ranked}")
                st.divider()
