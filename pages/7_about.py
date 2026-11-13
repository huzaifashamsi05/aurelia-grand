"""About: the team, the course, the ER diagram, the schema and how the app uses the database."""
from __future__ import annotations

import streamlit as st

from core import config, queries, ui

TEAM = [
    ("25F-DS-106", "Muhammad Abdul Rehman Khan"),
    ("25F-DS-135", "Muhammad Huzaifa Shamsi"),
    ("25F-DS-140", "Basit Mirza"),
    ("25F-DS-152", "Muhammad Hashir"),
    ("25F-DS-155", "Saif Ul Wahab"),
]

TABLES = {
    "RoomTypes": "The categories of room the hotel sells, with base rate and capacity.",
    "Rooms": "Every physical room: number, floor, view and live status.",
    "Guests": "People who stay at the hotel, with their VIP tier.",
    "Staff": "Employees who take bookings and deliver services.",
    "Bookings": "One row per reservation. Nights and RoomCharge are computed columns.",
    "Services": "Extras a guest can buy: dining, spa, laundry, transport and more.",
    "ServiceUsage": "Which booking used which service (resolves the many-to-many).",
    "Payments": "Deposits, settlements and refunds against a booking.",
}

# Where each database object is used in this app.
USAGE = [
    ("sp_SearchAvailableRooms", "Stored procedure", "Front Desk · Availability and the room list of New booking"),
    ("sp_CreateBooking", "Stored procedure", "Front Desk · New booking (booking + deposit in one transaction)"),
    ("sp_CheckIn", "Stored procedure", "Front Desk · Arrivals, the Check in button"),
    ("sp_AddService", "Stored procedure", "Front Desk · In-house, Add to room bill"),
    ("sp_CheckOut", "Stored procedure", "Front Desk · In-house, Check out (settlement + status in one transaction)"),
    ("sp_MonthlyPerformance", "Stored procedure", "Revenue & Analytics · the month picker"),
    ("vw_InHouseGuests", "View", "Front Desk · In-house list"),
    ("vw_GuestInvoice", "View", "Every invoice and running bill; guest stay history; room details"),
    ("vw_GuestLoyalty", "View", "Guests · profile figures and the top-10 leaderboard"),
    ("fn_AvailableRooms", "Function", "Inside sp_SearchAvailableRooms and sp_CreateBooking"),
    ("fn_BookingBill", "Function", "Inside sp_CheckOut; shown in SQL Lab (A2)"),
    ("fn_AmountPaid", "Function", "Inside sp_CheckOut; shown in SQL Lab (A2)"),
    ("trg_Bookings_NoDoubleBooking", "Trigger", "Blocks overlapping bookings (error 50001) · SQL Lab trigger demos"),
    ("trg_Bookings_RoomStatus", "Trigger", "Recolours the Live Room Map after check-in and check-out"),
    ("trg_Bookings_SoftDelete", "Trigger", "A DELETE becomes a cancellation · SQL Lab (A6)"),
    ("trg_Payments_VIPUpgrade", "Trigger", "The 'Upgraded to Gold / Platinum' toast after a payment"),
]

ui.page_header(
    "DBMS Group Project · Group 08",
    "About",
    "Hotel Booking and Guest Service System · Aurelia Grand, Karachi (a fictional five-star hotel).",
)

# ---- course and team ---------------------------------------------------------
course_column, team_column = st.columns([1, 1.15], gap="large")
with course_column:
    info = queries.server_info()
    ui.render(
        '<div class="ag-card">'
        '<div class="ag-overline">Course</div>'
        '<div class="ag-section" style="margin-top:0.2rem">Database Management Systems</div>'
        '<div class="ag-section-note">25F batch · Department of Data Science<br>'
        'Dawood University of Engineering &amp; Technology (DUET), Karachi</div>'
        '<table class="ag-table">'
        '<tr><td>Topic</td><td>Hotel Booking and Guest Service System</td></tr>'
        '<tr><td>Submission</td><td>Wednesday, 25 November 2026</td></tr>'
        f'<tr><td>Database</td><td>{ui.esc(info.get("DatabaseName"))} · SQL Server {ui.esc(info.get("Version"))}</td></tr>'
        f'<tr><td>Edition</td><td>{ui.esc(info.get("Edition"))}</td></tr>'
        f'<tr><td>Hotel date</td><td>{ui.short_date(config.hotel_today())} '
        f'(server date {ui.short_date(info.get("ServerDate"))})</td></tr>'
        "</table></div>"
    )
with team_column:
    rows = "".join(f"<tr><td><code>{ui.esc(roll)}</code></td><td>{ui.esc(name)}</td></tr>" for roll, name in TEAM)
    ui.render(
        '<div class="ag-card"><div class="ag-overline">Team</div>'
        '<div class="ag-section" style="margin-top:0.2rem">Group 08</div>'
        f'<table class="ag-table"><thead><tr><th>Roll no.</th><th>Name</th></tr></thead><tbody>{rows}</tbody></table>'
        "</div>"
    )

# ---- how the app talks to the database ----------------------------------------
ui.section("How this app uses the database")
ui.render(
    '<div class="ag-kpis three">'
    '<div class="ag-kpi"><div class="label">Writes</div><div class="sub" style="white-space:normal;color:#C9C2B2;'
    'font-size:0.82rem;margin-top:0.4rem">Only through the stored procedures. The Python code contains no INSERT, '
    'UPDATE or DELETE for bookings, services or payments.</div></div>'
    '<div class="ag-kpi"><div class="label">Reads</div><div class="sub" style="white-space:normal;color:#C9C2B2;'
    'font-size:0.82rem;margin-top:0.4rem">Views, functions and the report SQL from file 04. Every statement is '
    'parameterised.</div></div>'
    '<div class="ag-kpi"><div class="label">Rules</div><div class="sub" style="white-space:normal;color:#C9C2B2;'
    'font-size:0.82rem;margin-top:0.4rem">Constraints, triggers and THROW errors (50001 to 50050) are raised by '
    'SQL Server and shown here as messages.</div></div>'
    "</div>"
)

# ---- ER diagram -----------------------------------------------------------------
ui.section("Entity-relationship diagram", "8 tables in third normal form · source: erd/aurelia_grand.dbml")
diagram = config.ERD_DIR / "AureliaGrand_ERD_luxury.png"
report_diagram = config.ERD_DIR / "AureliaGrand_ERD_report.png"
if diagram.exists():
    st.image(str(diagram), width="stretch")
elif report_diagram.exists():
    st.image(str(report_diagram), width="stretch")
else:
    ui.empty("The ER diagram image was not found in the erd/ folder.")
if diagram.exists() and report_diagram.exists():
    with st.expander("Light version of the diagram (as printed in the report)"):
        st.image(str(report_diagram), width="stretch")

# ---- schema ----------------------------------------------------------------------
ui.section("Schema summary", "Live row counts from the database")
counts = {str(row.TableName): int(row.RowCount) for row in queries.table_counts().itertuples()}
schema_rows = "".join(
    f"<tr><td><code>{ui.esc(name)}</code></td><td class='num'>{counts.get(name, 0):,}</td>"
    f"<td>{ui.esc(purpose)}</td></tr>"
    for name, purpose in TABLES.items()
)
ui.render(
    '<div class="ag-card"><table class="ag-table"><thead><tr><th>Table</th><th class="num">Rows</th>'
    f"<th>Purpose</th></tr></thead><tbody>{schema_rows}</tbody></table></div>"
)

# ---- database objects -------------------------------------------------------------
objects = queries.database_objects()
present = set(objects["ObjectName"].astype(str))
indexes = sorted(objects.loc[objects["ObjectType"] == "Index", "ObjectName"].astype(str))
ui.section("Database objects and where the app uses them",
           f"{len(USAGE)} programmable objects and {len(indexes)} indexes found in the database")
usage_rows = "".join(
    f"<tr><td><code>{ui.esc(name)}</code></td><td>{ui.esc(kind)}</td><td>{ui.esc(where)}</td>"
    f"<td>{ui.status_pill('Available', 'Present') if name in present else ui.status_pill('Maintenance', 'Missing')}</td></tr>"
    for name, kind, where in USAGE
)
ui.render(
    '<div class="ag-card"><table class="ag-table"><thead><tr><th>Object</th><th>Type</th><th>Used in</th>'
    f"<th>In database</th></tr></thead><tbody>{usage_rows}</tbody></table></div>"
)
if indexes:
    st.caption("Indexes: " + ", ".join(indexes))
