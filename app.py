"""Aurelia Grand Command Center - entry point.

Run with:   streamlit run app.py

This file sets the page up, draws the custom sidebar and runs the selected
screen inside one guard, so the user never sees a Python traceback.
"""
from __future__ import annotations

import logging

import streamlit as st

from core import config, db, ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

st.set_page_config(
    page_title=f"{config.HOTEL_NAME} · {config.APP_TITLE}",
    page_icon=str(config.ASSETS_DIR / "monogram.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    st.Page("pages/1_lobby.py", title="Lobby", icon=":material/apartment:", url_path="lobby", default=True),
    st.Page("pages/2_front_desk.py", title="Front Desk", icon=":material/concierge:", url_path="front-desk"),
    st.Page("pages/3_room_map.py", title="Live Room Map", icon=":material/grid_view:", url_path="room-map"),
    st.Page("pages/4_guests.py", title="Guests", icon=":material/group:", url_path="guests"),
    st.Page("pages/5_analytics.py", title="Revenue & Analytics", icon=":material/monitoring:", url_path="analytics"),
    st.Page("pages/6_sql_lab.py", title="SQL Lab", icon=":material/database:", url_path="sql-lab"),
    st.Page("pages/7_about.py", title="About", icon=":material/info:", url_path="about"),
]

current_page = st.navigation(PAGES, position="hidden")
ui.inject_css()

try:
    ui.sidebar(PAGES)
    current_page.run()
except db.DatabaseError as error:
    ui.error_panel(error)
except Exception as error:  # last line of defence: friendly panel, details go to the log
    ui.error_panel(error)
