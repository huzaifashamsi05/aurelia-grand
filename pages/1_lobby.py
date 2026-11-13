"""Lobby: the hotel at a glance (six KPIs and the six-month trend)."""
from __future__ import annotations

import streamlit as st

from core import charts, config, queries, sql_catalog, ui

today = config.hotel_today()

ui.page_header(
    f"{config.HOTEL_CITY} · Arabian Sea",
    config.HOTEL_NAME,
    "Command Center · the whole house at a glance",
    side=f"<b>{ui.long_date(today)}</b><br>Hotel date",
    hero=True,
)

# ---- tonight's numbers -----------------------------------------------------
kpi = queries.kpi_tonight()
total_rooms = int(kpi.get("TotalRooms", 0) or 0)
occupied = int(kpi.get("RoomsOccupied", 0) or 0)
room_revenue = float(kpi.get("RoomRevenue", 0) or 0)
persons = int(kpi.get("Persons", 0) or 0)

occupancy = 100 * occupied / total_rooms if total_rooms else 0
adr = room_revenue / occupied if occupied else 0
revpar = room_revenue / total_rooms if total_rooms else 0

arrivals = queries.arrivals(today)
departures = queries.departures(today)
arrived = int((arrivals["Status"] == "CheckedIn").sum()) if not arrivals.empty else 0
pending_arrivals = int((arrivals["Status"] == "Confirmed").sum()) if not arrivals.empty else 0
departed = int((departures["Status"] == "CheckedOut").sum()) if not departures.empty else 0
pending_departures = int((departures["Status"] == "CheckedIn").sum()) if not departures.empty else 0

ui.kpi_row([
    {"label": "Occupancy", "value": ui.pct(occupancy), "sub": f"{occupied} of {total_rooms} rooms"},
    {"label": "ADR", "value": ui.money_html(adr), "sub": "Avg daily rate tonight"},
    {"label": "RevPAR", "value": ui.money_html(revpar), "sub": "Per available room"},
    {"label": "In-house guests", "value": ui.num(persons), "sub": f"In {occupied} rooms"},
    {"label": "Arrivals today", "value": ui.num(len(arrivals)),
     "sub": f"{arrived} in · {pending_arrivals} to come"},
    {"label": "Departures today", "value": ui.num(len(departures)),
     "sub": f"{departed} out · {pending_departures} to go"},
])

# ---- six-month trend (report R01) -------------------------------------------
trend = sql_catalog.run_report("R01", today).tail(6)

ui.section("Six-month trend", "Monthly occupancy, ADR and RevPAR · report R01, current month to date")
left, right = st.columns(2, gap="medium")
with left:
    with st.container(border=True):
        st.caption("Occupancy %")
        charts.show(charts.line_chart(trend, "Month", {"Occupancy": "Occupancy %"},
                                      suffix="%", decimals=1, area=True, height=220), key="lobby_occ")
with right:
    with st.container(border=True):
        st.caption("ADR and RevPAR · PKR per night")
        charts.show(charts.line_chart(trend, "Month", {"ADR": "ADR_PKR", "RevPAR": "RevPAR_PKR"},
                                      prefix="", height=220), key="lobby_rate")

with st.expander("View the six-month figures as a table"):
    st.dataframe(trend, hide_index=True, width="stretch")

# ---- the house right now ------------------------------------------------------
status = queries.room_status_counts()
ui.section("The house right now", "Room status is kept in step by the trigger trg_Bookings_RoomStatus")
ui.render(f'<div class="ag-card">{ui.status_legend(status)}</div>')

movement_left, movement_right = st.columns(2, gap="medium")
columns = ["RoomNumber", "Guest", "VIPTier", "TypeName", "Nights", "Status"]
labels = {"RoomNumber": "Room", "VIPTier": "Tier", "TypeName": "Room type"}
pretty_status = {"CheckedIn": "Checked in", "CheckedOut": "Checked out"}
arrivals = arrivals.assign(Status=arrivals["Status"].replace(pretty_status))
departures = departures.assign(Status=departures["Status"].replace(pretty_status))
with movement_left:
    st.caption(f"Arrivals · {ui.short_date(today)}")
    if arrivals.empty:
        ui.empty("No arrivals today.")
    else:
        st.dataframe(arrivals[columns].rename(columns=labels), hide_index=True, width="stretch", height=250)
with movement_right:
    st.caption(f"Departures · {ui.short_date(today)}")
    if departures.empty:
        ui.empty("No departures today.")
    else:
        st.dataframe(departures[columns].rename(columns=labels), hide_index=True, width="stretch", height=250)
