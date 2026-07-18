from datetime import date

import streamlit as st

from src.app_state import add_request, get_requests
from src.constants import CATEGORIES
from src.data import OUR_FOODBANK
from src.data_structures.request_queue import RequestQueue
from src.models import FoodRequest, Urgency
from src.utils import generate_request_id

st.set_page_config(page_title="Food Requests", page_icon="📝", layout="wide")

st.title("Food Requests")
st.caption(f"Requests raised by {OUR_FOODBANK.name} ({OUR_FOODBANK.foodbank_id})")

st.subheader("Raise a Request")

with st.form("add_request_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        category = st.selectbox("Category", CATEGORIES)
        quantity = st.number_input("Quantity Needed", min_value=1, value=1, step=1)

    with col2:
        urgency = st.selectbox(
            "Urgency",
            list(Urgency),
            format_func=lambda u: u.label,
        )

    submitted = st.form_submit_button("Submit Request")

if submitted:
    request = FoodRequest(
        request_id=generate_request_id(),
        foodbank_id=OUR_FOODBANK.foodbank_id,
        category=category,
        quantity=int(quantity),
        urgency=urgency,
    )
    add_request(request)
    st.success(f"Request {request.request_id} submitted for {request.quantity} x {request.category}.")

st.divider()
st.subheader("Open Requests")

requests = get_requests()

if not requests:
    st.info("No requests yet. Raise one above.")
else:
    st.caption(
        "Ordered by priority — a blend of urgency and how long a request has "
        "waited, so long-neglected requests rise over time."
    )
    today = date.today()
    queue = RequestQueue.from_requests(requests, today)
    rows = [
        {
            "Priority": rank,
            "Request ID": r.request_id,
            "Category": r.category,
            "Quantity": r.quantity,
            "Urgency": r.urgency.label,
            "Days Waiting": (today - r.submitted_at).days,
            "Submitted": r.submitted_at.strftime("%Y-%m-%d"),
        }
        for rank, r in enumerate(queue.pending(today), start=1)
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
