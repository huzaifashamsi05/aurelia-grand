"""Live Room Map: every room as a tile, coloured by Rooms.Status.

The status is never set by this app. It changes when sp_CheckIn / sp_CheckOut
update a booking and the trigger trg_Bookings_RoomStatus reacts.
"""
from __future__ import annotations

import streamlit as st

from core import config, queries, ui

today = config.hotel_today()
rooms = queries.room_map()
counts = rooms["Status"].value_counts().to_dict()

ui.page_header(
    "Housekeeping & Occupancy",
    "Live Room Map",
    "Floors 2 to 10. Click a room to see who is in it and who arrives next.",
    side=f"<b>{len(rooms)} rooms</b><br>{ui.short_date(today)}",
)
ui.render(ui.status_legend(counts))

map_column, detail_column = st.columns([1.5, 1], gap="large")
selected = st.session_state.get("map_room")

with map_column:
    for floor in sorted(rooms["FloorNo"].unique(), reverse=True):
        floor_rooms = rooms[rooms["FloorNo"] == floor].sort_values("RoomNumber")
        slots = st.columns([0.75, 1, 1, 1, 1, 1], gap="small")
        slots[0].html(f'<div class="ag-floor">Floor {int(floor)}</div>')
        for slot, room in zip(slots[1:], floor_rooms.itertuples()):
            number = str(room.RoomNumber)
            key = f"tile_{room.Status}_{number}" + ("_selected" if number == selected else "")
            tip = f"{room.TypeName} · {room.ViewType} view · {room.Status}"
            if slot.button(number, key=key, help=tip, width="stretch"):
                st.session_state["map_room"] = number
                st.rerun()

with detail_column:
    if not selected or selected not in set(rooms["RoomNumber"].astype(str)):
        ui.render(
            '<div class="ag-card"><div class="ag-overline">Room details</div>'
            '<div class="ag-empty">Select a room on the map.</div></div>'
        )
    else:
        room = rooms[rooms["RoomNumber"].astype(str) == selected].iloc[0]
        guest = queries.room_current_guest(selected)
        upcoming = queries.room_next_booking(selected, today)

        smoking = "Smoking" if bool(room.IsSmoking) else "Non-smoking"
        ui.render(
            '<div class="ag-card">'
            f'<div class="ag-header-row"><div><div class="ag-overline">{ui.esc(room.TypeName)}</div>'
            f'<div class="ag-title">Room {ui.esc(selected)}</div></div>'
            f'<div>{ui.status_pill(room.Status)}</div></div>'
            f'<div class="ag-section-note" style="margin-top:0.5rem">Floor {int(room.FloorNo)} · '
            f'{ui.esc(room.ViewType)} view · {ui.esc(room.BedType)} bed · {int(room.SizeSqFt):,} sq ft · '
            f'sleeps {int(room.MaxOccupancy)} · {smoking}</div>'
            f'<div class="ag-section-note">Base rate {ui.pkr(room.BaseRate)} per night</div>'
            "</div>"
        )

        ui.section("Current guest")
        if guest:
            ui.render(
                '<div class="ag-card">'
                f'<div class="ag-row" style="border:0;padding:0"><div><div class="main">{ui.esc(guest.get("Guest"))}'
                f' &nbsp;{ui.tier_badge(guest.get("VIPTier"))}</div>'
                f'<div class="meta">Booking #{ui.whole(guest.get("BookingID"))} · {ui.esc(guest.get("Nationality"))}'
                f' · {ui.whole(guest.get("Persons"))} guest(s)</div>'
                f'<div class="meta">{ui.short_date(guest.get("CheckInDate"))} to '
                f'{ui.short_date(guest.get("CheckOutDate"))} · {ui.whole(guest.get("Nights"))} night(s)</div></div></div>'
                f'<div class="ag-invoice" style="box-shadow:none;border-color:var(--ag-line);margin-top:0.7rem;padding:0.6rem 0.9rem">'
                f'<div class="line"><span>Bill so far</span><span>{ui.pkr(guest.get("BillTotal"))}</span></div>'
                f'<div class="line"><span>Paid</span><span>{ui.pkr(guest.get("Paid"))}</span></div>'
                f'<div class="line balance"><span>Balance</span><span>{ui.pkr(guest.get("Balance"))}</span></div>'
                "</div></div>"
            )
        else:
            ui.empty("No guest is checked in to this room.")

        ui.section("Next booking")
        if upcoming:
            ui.render(
                '<div class="ag-card">'
                f'<div class="main" style="color:var(--ag-ivory)">{ui.esc(upcoming.get("Guest"))} &nbsp;'
                f'{ui.tier_badge(upcoming.get("VIPTier"))}</div>'
                f'<div class="ag-section-note" style="margin:0.25rem 0 0 0">Booking #{ui.whole(upcoming.get("BookingID"))}'
                f' · arrives {ui.short_date(upcoming.get("CheckInDate"))} · {ui.whole(upcoming.get("Nights"))} night(s)'
                f' · {ui.esc(upcoming.get("Channel"))}</div>'
                "</div>"
            )
        else:
            ui.empty("No confirmed booking is waiting for this room.")
