"""Revenue & Analytics: the 15 management reports (R01-R15) as charts and tables.

The SQL is read from sql/04_reporting_queries.sql through core/sql_catalog.py,
so each chart shows exactly what the submitted report returns.
The month picker calls the stored procedure sp_MonthlyPerformance.
"""
from __future__ import annotations

import calendar

import pandas as pd
import streamlit as st

from core import charts, config, procs, sql_catalog, ui

GROUPS = ["Occupancy & rates", "Room types", "Channels", "Seasonality", "Services", "Payments", "Staff", "Guests"]
today = config.hotel_today()

ui.page_header(
    "Management Reports",
    "Revenue & Analytics",
    "Fifteen reports (R01 to R15) from 04_reporting_queries.sql, plus sp_MonthlyPerformance for any month.",
    side=f"<b>{ui.short_date(today)}</b><br>Figures to date",
)

st.session_state.setdefault("an_group", GROUPS[0])
group = st.segmented_control("Group", GROUPS, key="an_group", required=True, label_visibility="collapsed") or GROUPS[0]


def load(report_id: str) -> pd.DataFrame:
    return sql_catalog.run_report(report_id, today)


def heading(report_id: str) -> None:
    query = sql_catalog.get(report_id)
    ui.section(f"{report_id} · {query.title}", query.description or None)


def details(report_id: str, frame: pd.DataFrame, *, open_table: bool = False, height: int | str = "auto") -> None:
    """The figures as a table, and the SQL behind them."""
    if open_table:
        ui.table(frame, height=height, key=f"tbl_{report_id}")
    else:
        with st.expander("Figures as a table"):
            ui.table(frame, key=f"tbl_{report_id}")
    with st.expander(f"SQL of {report_id}"):
        st.code(sql_catalog.get(report_id).sql, language="sql")


def chart_card(caption: str, figure, key: str) -> None:
    with st.container(border=True):
        st.caption(caption)
        charts.show(figure, key=key)


# ===========================================================================
if group == "Occupancy & rates":
    # ---- month picker -> sp_MonthlyPerformance --------------------------------
    ui.section("Monthly performance", "Runs the stored procedure sp_MonthlyPerformance for the month you pick")
    pick_month, pick_year, _spacer = st.columns([1.2, 0.8, 3])
    month = pick_month.selectbox("Month", list(range(1, 13)), index=today.month - 1,
                                 format_func=lambda m: calendar.month_name[m], key="an_month")
    year = pick_year.selectbox("Year", [2026, 2027], index=0 if today.year <= 2026 else 1, key="an_year")
    performance = procs.monthly_performance(year, month)
    if performance.empty or pd.isna(performance.iloc[0].get("RoomsSold")):
        ui.empty("No stays were recorded in this month.")
    else:
        row = performance.iloc[0]
        ui.kpi_row([
            {"label": "Occupancy", "value": ui.pct(row["Occupancy %"]),
             "sub": f'{ui.num(row["RoomsSold"])} of {ui.num(row["RoomsAvailable"])} room-nights'},
            {"label": "ADR", "value": ui.money_html(row["ADR_PKR"]), "sub": "Average daily rate"},
            {"label": "RevPAR", "value": ui.money_html(row["RevPAR_PKR"]), "sub": "Per available room"},
            {"label": "Room revenue", "value": ui.money_html(row["RoomRevenue_PKR"]), "sub": str(row["ReportMonth"])},
            {"label": "Service revenue", "value": ui.money_html(row["ServiceRevenue_PKR"]), "sub": "Extras sold"},
            {"label": "Cancellations", "value": ui.num(row["Cancellations"]), "sub": "By check-in month"},
        ])

    # ---- R01 -------------------------------------------------------------------
    heading("R01")
    r01 = load("R01")
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Occupancy % by month",
                   charts.line_chart(r01, "Month", {"Occupancy": "Occupancy %"}, suffix="%", decimals=1,
                                     area=True, height=240), "an_r01_occ")
    with right:
        chart_card("ADR and RevPAR by month · PKR per night",
                   charts.line_chart(r01, "Month", {"ADR": "ADR_PKR", "RevPAR": "RevPAR_PKR"}, height=240),
                   "an_r01_rate")
    details("R01", r01)

    # ---- R12 -------------------------------------------------------------------
    heading("R12")
    r12 = load("R12")
    if r12.empty:
        ui.empty("No arrivals or departures on this date.")
    details("R12", r12, open_table=not r12.empty, height=260)

# ===========================================================================
elif group == "Room types":
    heading("R02")
    r02 = load("R02")
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Room revenue by room type · PKR",
                   charts.bar_chart(r02, "TypeName", "RoomRevenue_PKR", compact=True), "an_r02_rev")
    with right:
        chart_card("Average nightly rate by room type · PKR",
                   charts.bar_chart(r02.sort_values("AvgRate_PKR", ascending=False), "TypeName", "AvgRate_PKR"),
                   "an_r02_rate")
    details("R02", r02, open_table=True)

    heading("R08")
    r08 = load("R08")
    st.caption(f"{len(r08)} room(s) earn less than the average of their own room type.")
    details("R08", r08, open_table=True, height=300)

# ===========================================================================
elif group == "Channels":
    heading("R05")
    r05 = load("R05")
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Bookings by channel", charts.bar_chart(r05, "Channel", "Bookings"), "an_r05_volume")
    with right:
        chart_card("Share of bookings lost (cancelled or no-show) · %",
                   charts.bar_chart(r05.sort_values("Lost %", ascending=False), "Channel", "Lost %",
                                    suffix="%", decimals=1), "an_r05_lost")
    details("R05", r05, open_table=True)

    heading("R09")
    r09 = load("R09")
    chart_card("Room revenue by guest nationality · PKR",
               charts.bar_chart(r09, "Nationality", "RoomRevenue_PKR", compact=True), "an_r09")
    details("R09", r09)

# ===========================================================================
elif group == "Seasonality":
    heading("R11")
    r11 = load("R11")
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Average nightly rate by season · PKR",
                   charts.bar_chart(r11, "Season", "AvgRate_PKR", highlight=None), "an_r11_rate")
    with right:
        chart_card("Room revenue by season · PKR",
                   charts.bar_chart(r11, "Season", "RoomRevenue_PKR", compact=True), "an_r11_rev")
    details("R11", r11, open_table=True)

    heading("R14")
    r14 = load("R14")
    chart_card("Total revenue by month (rooms + services) · PKR",
               charts.bar_chart(r14, "Month", "Revenue_PKR", horizontal=False, compact=True, height=280),
               "an_r14")
    details("R14", r14, open_table=True)

# ===========================================================================
elif group == "Services":
    heading("R04")
    r04 = load("R04")
    chart_card("Service revenue by category · PKR",
               charts.bar_chart(r04, "Category", "Revenue_PKR", compact=True), "an_r04")
    details("R04", r04, open_table=True)

    heading("R13")
    r13 = load("R13")
    details("R13", r13, open_table=True)

# ===========================================================================
elif group == "Payments":
    heading("R15")
    r15 = load("R15")
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Share of money received by payment method · %",
                   charts.bar_chart(r15, "Method", "Share %", suffix="%", decimals=1), "an_r15_share")
    with right:
        chart_card("Refunds issued by payment method · PKR",
                   charts.bar_chart(r15.sort_values("Refunded_PKR", ascending=False), "Method", "Refunded_PKR",
                                    compact=True), "an_r15_refund")
    details("R15", r15, open_table=True)

    heading("R07")
    r07 = load("R07")
    if r07.empty:
        ui.empty("Every checked-out guest has paid in full.")
    else:
        ui.kpi_row([
            {"label": "Unpaid bills", "value": ui.num(len(r07)), "sub": "Checked-out bookings"},
            {"label": "Total outstanding", "value": ui.money_html(r07["BalanceDue"].sum()), "sub": "Still to collect"},
            {"label": "Largest balance", "value": ui.money_html(r07["BalanceDue"].max()), "sub": str(r07.iloc[0]["Guest"])},
        ], columns=3)
    details("R07", r07, open_table=not r07.empty, height=300)

# ===========================================================================
elif group == "Staff":
    heading("R10")
    r10 = load("R10")
    bookers = r10[r10["BookingsTaken"] > 0].sort_values("BookingsTaken", ascending=False)
    servers = r10[r10["ServiceRevenue_PKR"] > 0].sort_values("ServiceRevenue_PKR", ascending=False).head(10)
    left, right = st.columns(2, gap="medium")
    with left:
        chart_card("Bookings taken by employee", charts.bar_chart(bookers, "FullName", "BookingsTaken"),
                   "an_r10_bookings")
    with right:
        chart_card("Service revenue delivered by employee · PKR (top 10)",
                   charts.bar_chart(servers, "FullName", "ServiceRevenue_PKR", compact=True), "an_r10_services")
    details("R10", r10, open_table=True, height=320)

# ===========================================================================
else:  # Guests
    heading("R03")
    r03 = load("R03")
    chart_card("Lifetime value of the top 10 guests · PKR",
               charts.bar_chart(r03, "Guest", "LifetimeValue_PKR", compact=True), "an_r03")
    details("R03", r03, open_table=True)

    heading("R06")
    r06 = load("R06")
    if r06.empty:
        ui.empty("No guest has stayed 12 or more times this year.")
    details("R06", r06, open_table=not r06.empty, height=300)
