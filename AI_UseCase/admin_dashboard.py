import streamlit as st
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import pandas as pd
from db.database import get_all_bookings


def show_admin_dashboard():
    st.title("Admin Dashboard")
    st.caption("All bookings stored in the system.")

    bookings = get_all_bookings()

    if not bookings:
        st.info("No bookings found yet.")
        return

    df = pd.DataFrame(bookings)

    # --- Filters ---
    col1, col2 = st.columns(2)
    with col1:
        search_name = st.text_input("Search by name", "")
    with col2:
        type_filter = st.selectbox(
            "Filter by booking type",
            ["All"] + sorted(df["booking_type"].unique().tolist())
        )

    if search_name:
        df = df[df["name"].str.contains(search_name, case=False, na=False)]
    if type_filter != "All":
        df = df[df["booking_type"] == type_filter]

    st.metric("Total Bookings", len(df))
    st.dataframe(df, use_container_width=True)
