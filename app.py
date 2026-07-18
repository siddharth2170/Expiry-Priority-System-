import folium
import streamlit as st
from streamlit_folium import st_folium

from src.data import FOODBANKS, OUR_FOODBANK

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

    selected = next((fb for fb in FOODBANKS if fb.name == clicked_name), None)

    if selected is None:
        st.info("Click a foodbank marker on the map to view details.")
    else:
        st.subheader(selected.name)
        with st.container(border=True):
            st.empty()
