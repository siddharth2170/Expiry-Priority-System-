import streamlit as st
from datetime import date

st.set_page_config(
    page_title="Food Rescue System",
    page_icon="🍎",
    layout="centered"
)

st.title("Food Rescue and Expiry-Priority System")
st.subheader("Register a Food Donation")

with st.form("donation_form"):

    st.markdown("### Donor Information")

    donor_id = st.text_input("Donor ID")
    donor_name = st.text_input("Donor Name")
    organization = st.text_input("Restaurant / Supermarket")
    contact = st.text_input("Contact Number")

    st.markdown("### Food Information")

    food_id = st.text_input("Food ID")

    food_name = st.text_input("Food Name")

    category = st.selectbox(
        "Category",
        [
            "Bakery",
            "Dairy",
            "Vegetables",
            "Fruits",
            "Prepared Meals",
            "Grains",
            "Beverages",
            "Other"
        ]
    )

    quantity = st.number_input(
        "Quantity",
        min_value=1,
        value=1,
        step=1
    )

    unit = st.selectbox(
        "Unit",
        [
            "Packets",
            "Boxes",
            "Kilograms",
            "Liters",
            "Meals",
            "Pieces"
        ]
    )

    expiry_date = st.date_input(
        "Expiry Date",
        min_value=date.today()
    )

    storage = st.selectbox(
        "Storage Requirement",
        [
            "Room Temperature",
            "Refrigerated",
            "Frozen"
        ]
    )

    notes = st.text_area("Additional Notes")

    submitted = st.form_submit_button("Submit Donation")

if submitted:

    if not donor_id or not donor_name or not food_id or not food_name:
        st.error("Please fill all required fields.")

    else:

        donation = {
            "Donor ID": donor_id,
            "Donor Name": donor_name,
            "Organization": organization,
            "Contact": contact,
            "Food ID": food_id,
            "Food Name": food_name,
            "Category": category,
            "Quantity": quantity,
            "Unit": unit,
            "Expiry Date": expiry_date.strftime("%Y-%m-%d"),
            "Storage": storage,
            "Notes": notes
        }

        st.success("Donation Registered Successfully!")

        st.markdown("### Donation Summary")

        st.json(donation)