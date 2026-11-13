"""Guests: search, profile with loyalty tier, stay history and the top-10 leaderboard."""
from __future__ import annotations

import streamlit as st

from core import charts, config, queries, ui

VIEWS = ["Find a guest", "Top 10 leaderboard"]

ui.page_header(
    "Guest Relations",
    "Guests",
    "Search by name, CNIC or passport, email or phone. Loyalty figures come from the view vw_GuestLoyalty.",
)

st.session_state.setdefault("g_view", VIEWS[0])
view = st.segmented_control("View", VIEWS, key="g_view", required=True, label_visibility="collapsed") or VIEWS[0]


def tier_progress(tier: str, spend: float) -> str:
    """A meter towards the next tier (thresholds are enforced by trg_Payments_VIPUpgrade)."""
    if tier == "Platinum" or spend >= config.PLATINUM_THRESHOLD:
        return ('<div class="ag-meter"><span style="width:100%"></span></div>'
                '<div class="ag-meter-note">Platinum: the highest tier.</div>')
    target, name = ((config.GOLD_THRESHOLD, "Gold") if spend < config.GOLD_THRESHOLD
                    else (config.PLATINUM_THRESHOLD, "Platinum"))
    share = max(0.0, min(1.0, spend / target))
    return (f'<div class="ag-meter"><span style="width:{share * 100:.1f}%"></span></div>'
            f'<div class="ag-meter-note">{ui.pkr(spend)} of {ui.pkr(target)} towards {name} · '
            f'{ui.pkr(target - spend)} to go</div>')


def profile(guest_id: int) -> None:
    guest = queries.guest_profile(guest_id)
    if not guest:
        ui.empty("This guest could not be found.")
        return
    name = f'{guest.get("FirstName")} {guest.get("LastName")}'
    tier = str(guest.get("VIPTier"))
    spend = float(guest.get("LifetimeSpend") or 0)
    gender = {"M": "Male", "F": "Female"}.get(str(guest.get("Gender")), "-")

    facts = [
        ("City", guest.get("City")), ("Nationality", guest.get("Nationality")),
        ("Email", guest.get("Email")), ("Phone", guest.get("Phone")),
        ("CNIC / passport", guest.get("IDDocument")), ("Date of birth", ui.short_date(guest.get("DateOfBirth"))),
        ("Gender", gender), ("Guest since", ui.short_date(guest.get("CreatedAt"))),
    ]
    facts_html = "".join(
        f'<div><div class="k">{ui.esc(label)}</div><div class="v">{ui.esc(value)}</div></div>'
        for label, value in facts
    )
    ui.render(
        '<div class="ag-card ag-profile">'
        f'<div class="ag-header-row"><div><div class="ag-overline">Guest #{ui.whole(guest.get("GuestID"))}</div>'
        f'<div class="name">{ui.esc(name)}</div></div><div>{ui.tier_badge(tier)}</div></div>'
        f"{tier_progress(tier, spend)}"
        f'<div class="facts">{facts_html}</div>'
        "</div>"
    )
    ui.kpi_row([
        {"label": "Stays", "value": ui.num(guest.get("Stays"))},
        {"label": "Nights", "value": ui.num(guest.get("Nights"))},
        {"label": "Lifetime spend", "value": ui.money_html(spend)},
        {"label": "Last visit", "value": ui.short_date(guest.get("LastVisit"))},
    ], columns=4)

    stays = queries.guest_stays(guest_id)
    ui.section("Stay history and invoices", f"{len(stays)} booking(s) · from the view vw_GuestInvoice")
    if stays.empty:
        ui.empty("No bookings yet.")
    else:
        pretty = {"CheckedIn": "Checked in", "CheckedOut": "Checked out", "NoShow": "No-show"}
        stays = stays.assign(Status=stays["Status"].replace(pretty))
        ui.table(
            stays[["BookingID", "RoomNumber", "TypeName", "CheckInDate", "CheckOutDate", "Nights", "Status",
                   "RoomCharge", "ServiceCharge", "BillTotal", "Paid", "Balance"]],
            labels={"BookingID": "Booking", "RoomNumber": "Room", "TypeName": "Room type",
                    "CheckInDate": "Check-in", "CheckOutDate": "Check-out",
                    "RoomCharge": "Room charge", "ServiceCharge": "Services", "BillTotal": "Bill"},
            height=min(320, 38 * (len(stays) + 1) + 4),
        )


# ===========================================================================
# Find a guest
# ===========================================================================
if view == "Find a guest":
    term = st.text_input("Search", placeholder="Name, CNIC / passport, email or phone", key="g_term")

    if len(term.strip()) < 2:
        tiers = queries.tier_counts()
        ui.kpi_row([
            {"label": "Silver guests", "value": ui.num(tiers.get("Silver", 0)), "sub": "Starting tier"},
            {"label": "Gold guests", "value": ui.num(tiers.get("Gold", 0)),
             "sub": f"From {ui.pkr(config.GOLD_THRESHOLD, short=True)} lifetime spend"},
            {"label": "Platinum guests", "value": ui.num(tiers.get("Platinum", 0)),
             "sub": f"From {ui.pkr(config.PLATINUM_THRESHOLD, short=True)} lifetime spend"},
        ], columns=3)
        st.caption("Type at least two characters to search. Tiers are upgraded automatically by the trigger "
                   "trg_Payments_VIPUpgrade whenever a payment arrives.")
    else:
        results = queries.guest_search(term)
        if results.empty:
            ui.empty("No guest matches this search.")
        else:
            list_column, profile_column = st.columns([1, 1.5], gap="large")
            with list_column:
                st.caption(f"{len(results)} match(es) · select a row to open the profile")
                event = st.dataframe(
                    results[["Guest", "VIPTier", "City", "IDDocument"]].rename(
                        columns={"VIPTier": "Tier", "IDDocument": "CNIC / passport"}),
                    hide_index=True, width="stretch", height=460,
                    on_select="rerun", selection_mode="single-row", key=f"g_grid_{term.strip().lower()}",
                )
                picked = event.selection.rows[0] if event.selection.rows else 0
            with profile_column:
                profile(int(results.iloc[picked]["GuestID"]))

# ===========================================================================
# Leaderboard
# ===========================================================================
else:
    top = queries.leaderboard()
    ui.section("Top 10 guests by lifetime spend", "SELECT TOP (10) ... FROM vw_GuestLoyalty ORDER BY LifetimeSpend DESC")
    table_column, chart_column = st.columns([1.25, 1], gap="large")
    with table_column:
        rows = "".join(
            "<tr>"
            f'<td><span class="ag-rank">{position}</span></td>'
            f"<td>{ui.esc(g.Guest)}<br><span style='color:var(--ag-muted);font-size:0.74rem'>{ui.esc(g.City)}"
            f" · {ui.esc(g.Nationality)}</span></td>"
            f"<td>{ui.tier_badge(g.VIPTier)}</td>"
            f'<td class="num">{int(g.Stays)}</td><td class="num">{int(g.Nights)}</td>'
            f'<td class="num">{ui.pkr(g.LifetimeSpend)}</td>'
            "</tr>"
            for position, g in enumerate(top.itertuples(), start=1)
        )
        ui.render(
            '<div class="ag-card"><table class="ag-table"><thead><tr><th></th><th>Guest</th><th>Tier</th>'
            '<th class="num">Stays</th><th class="num">Nights</th><th class="num">Lifetime spend</th>'
            f"</tr></thead><tbody>{rows}</tbody></table></div>"
        )
    with chart_column:
        with st.container(border=True):
            st.caption("Lifetime spend · PKR")
            charts.show(charts.bar_chart(top, "Guest", "LifetimeSpend", compact=True, height=430), key="g_top")
