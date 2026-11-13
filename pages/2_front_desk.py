"""Front Desk: search, book, check in, charge services and check out.

Every button on this screen runs one stored procedure through core/procs.py:
  Availability -> sp_SearchAvailableRooms      New booking -> sp_CreateBooking
  Arrivals     -> sp_CheckIn                   In-house    -> sp_AddService, sp_CheckOut
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from core import config, db, procs, queries, ui

VIEWS = ["Availability", "New booking", "Arrivals", "In-house"]
today = config.hotel_today()

ui.page_header(
    "Operations",
    "Front Desk",
    "Every action here runs a stored procedure. The database enforces the rules.",
    side=f"<b>{ui.short_date(today)}</b><br>Hotel date",
)

# The booking being prepared survives a switch between views.
draft = st.session_state.setdefault("fd_draft", {
    "check_in": today, "check_out": today + timedelta(days=2),
    "adults": 2, "children": 0, "room": None,
})

if "fd_goto" in st.session_state:
    st.session_state["fd_view"] = st.session_state.pop("fd_goto")
st.session_state.setdefault("fd_view", VIEWS[0])
view = st.segmented_control("View", VIEWS, key="fd_view", required=True, label_visibility="collapsed")
view = view or VIEWS[0]


def stay_inputs(prefix: str) -> tuple[date, date, int, int]:
    """Dates and party size, shared by Availability and New booking."""
    c1, c2, c3, c4 = st.columns([1.3, 1.3, 0.8, 0.8])
    check_in = c1.date_input("Check-in", value=draft["check_in"], format="DD/MM/YYYY", key=f"{prefix}_in")
    check_out = c2.date_input("Check-out", value=draft["check_out"], format="DD/MM/YYYY", key=f"{prefix}_out")
    adults = c3.number_input("Adults", min_value=1, max_value=6, value=int(draft["adults"]), key=f"{prefix}_adults")
    children = c4.number_input("Children", min_value=0, max_value=4, value=int(draft["children"]), key=f"{prefix}_kids")
    draft.update(check_in=check_in, check_out=check_out, adults=int(adults), children=int(children))
    return check_in, check_out, int(adults), int(children)


def search(check_in: date, check_out: date, persons: int):
    """sp_SearchAvailableRooms. Shows the procedure's own message if it refuses."""
    try:
        return procs.search_available_rooms(check_in, check_out, persons)
    except db.DatabaseError as error:
        meta = " · ".join(p for p in (error.source, f"error {error.number}" if error.number else None) if p)
        ui.notice("error", "The database said no", error.message, meta or None)
        return None


# ===========================================================================
# (a) Availability
# ===========================================================================
if view == "Availability":
    ui.section("Search availability", "Runs sp_SearchAvailableRooms, which reads fn_AvailableRooms")
    check_in, check_out, adults, children = stay_inputs("av")
    rooms = search(check_in, check_out, adults + children)

    if rooms is not None:
        nights = (check_out - check_in).days
        if rooms.empty:
            ui.empty("No room is free for these dates and this party size.")
        else:
            st.caption(f"{len(rooms)} room(s) free · {nights} night(s) · cheapest first")
            per_row = 4
            for start in range(0, len(rooms), per_row):
                columns = st.columns(per_row, gap="small")
                for column, room in zip(columns, rooms.iloc[start:start + per_row].itertuples()):
                    with column:
                        ui.render(
                            '<div class="ag-room-card">'
                            f'<div class="no">{ui.esc(room.RoomNumber)}</div>'
                            f'<div class="type">{ui.esc(room.TypeName)}</div>'
                            f'<div class="facts">{ui.esc(room.ViewType)} view · Floor {int(room.FloorNo)}'
                            f' · sleeps {int(room.MaxOccupancy)}</div>'
                            f'<div class="price">{ui.pkr(room.RatePerNight)} <small>per night</small></div>'
                            f'<div class="total">{ui.pkr(room.StayTotal)} for the stay</div>'
                            "</div>"
                        )
                        if st.button("Book this room", key=f"pick_{room.RoomNumber}", width="stretch"):
                            draft["room"] = str(room.RoomNumber)
                            st.session_state["fd_goto"] = "New booking"
                            st.rerun()

# ===========================================================================
# (b) New booking
# ===========================================================================
elif view == "New booking":
    ui.section("New booking", "Runs sp_CreateBooking: booking and deposit are saved in one transaction")
    form_column, result_column = st.columns([1.35, 1], gap="large")

    with form_column:
        check_in, check_out, adults, children = stay_inputs("nb")

        guests = queries.guest_options()
        guest_labels = {
            int(g.GuestID): f"{g.Guest} · {g.City} · {g.VIPTier} · {g.IDDocument}" for g in guests.itertuples()
        }
        guest_id = st.selectbox(
            "Guest", list(guest_labels), index=None, format_func=guest_labels.get,
            placeholder="Type a name, city or CNIC to search", key="nb_guest",
        )

        any_room = st.toggle("Show every room, to test the double-booking guard", key="nb_any_room")
        if any_room:
            pool = queries.all_rooms()
            free = procs.search_available_rooms(check_in, check_out, 1) if check_out > check_in else None
            free_numbers = set(free["RoomNumber"].astype(str)) if free is not None else set()
        else:
            pool = search(check_in, check_out, adults + children)
            free_numbers = set(pool["RoomNumber"].astype(str)) if pool is not None else set()

        room_labels: dict[str, str] = {}
        if pool is not None:
            for r in pool.itertuples():
                number = str(r.RoomNumber)
                label = (f"{number} · {r.TypeName} · {r.ViewType} view · Floor {int(r.FloorNo)}"
                         f" · {ui.pkr(r.RatePerNight)}")
                if number not in free_numbers:
                    label += " · NOT FREE"
                room_labels[number] = label
        room_options = list(room_labels)
        preselected = room_options.index(draft["room"]) if draft.get("room") in room_options else None
        room_number = st.selectbox(
            "Room", room_options, index=preselected, format_func=room_labels.get,
            placeholder="Choose a room" if room_options else "No room is free for these dates",
            key=f"nb_room_{any_room}",
        )
        draft["room"] = room_number

        c1, c2 = st.columns(2)
        channel = c1.selectbox("Channel", config.CHANNELS, key="nb_channel")
        staff = queries.staff()
        desk = staff[staff["Role"].isin(["Front Desk", "Concierge"])]
        staff_labels = {int(s.StaffID): f"{s.FullName} · {s.Role}" for s in desk.itertuples()}
        staff_id = c2.selectbox("Booked by", list(staff_labels), format_func=staff_labels.get, key="nb_staff")

        c3, c4 = st.columns(2)
        deposit = c3.number_input("Deposit (PKR)", min_value=0, max_value=5_000_000, value=0, step=5_000,
                                  key="nb_deposit")
        method = c4.selectbox("Deposit method", config.PAYMENT_METHODS, key="nb_method")

        ready = guest_id is not None and room_number is not None
        if st.button("Confirm booking", type="primary", disabled=not ready, key="nb_submit"):
            try:
                booking = procs.create_booking(
                    guest_id=guest_id, room_number=room_number, staff_id=staff_id,
                    check_in=check_in, check_out=check_out, adults=adults, children=children,
                    channel=channel, deposit_amount=deposit, deposit_method=method,
                )
            except db.DatabaseError as error:
                ui.flash_error(error)
            else:
                st.session_state["fd_last_booking"] = booking.invoice
                ui.flash(
                    "success", f"Booking #{booking.booking_id} confirmed",
                    f"{booking.guest} · room {room_number} · {ui.short_date(check_in)} to {ui.short_date(check_out)}",
                    "Procedure sp_CreateBooking · one transaction",
                )
                if booking.upgraded_to:
                    ui.flash_vip(booking.guest, booking.upgraded_to)
                draft["room"] = None
            st.rerun()
        if not ready:
            st.caption("Choose a guest and a room to continue.")

    with result_column:
        last = st.session_state.get("fd_last_booking")
        if last:
            ui.invoice_card(last, "Booking confirmed",
                            "Returned by sp_CreateBooking from the view vw_GuestInvoice.")
            if st.button("Clear", key="nb_clear"):
                st.session_state.pop("fd_last_booking", None)
                st.rerun()
        elif room_number and pool is not None and check_out > check_in:
            chosen = pool[pool["RoomNumber"].astype(str) == room_number].iloc[0]
            nights = (check_out - check_in).days
            ui.render(
                '<div class="ag-card">'
                '<div class="ag-overline">Estimate</div>'
                f'<div class="ag-section" style="margin-top:0.2rem">Room {ui.esc(room_number)} · '
                f'{ui.esc(chosen.TypeName)}</div>'
                f'<div class="ag-section-note">{nights} night(s) at the base rate of {ui.pkr(chosen.RatePerNight)}</div>'
                f'<div class="ag-figure">{ui.money_html(chosen.RatePerNight * nights, short=False)}</div>'
                '<div class="ag-meter-note">The final nightly rate is set inside sp_CreateBooking: '
                'December +25%, Corporate -15%, Website -5%, Walk-in +5%.</div>'
                "</div>"
            )
        else:
            ui.empty("The invoice appears here as soon as the booking is confirmed.")

# ===========================================================================
# (c) Arrivals
# ===========================================================================
elif view == "Arrivals":
    ui.section(f"Arrivals · {ui.short_date(today)}", "Check in runs sp_CheckIn; a trigger then marks the room Occupied")
    arrivals = queries.arrivals(today)

    server_date = ui.as_date(queries.server_info().get("ServerDate"))
    if server_date and server_date != today:
        st.caption(
            f"sp_CheckIn compares the arrival date with the server's own date ({ui.short_date(server_date)}). "
            "It refuses a check-in that is more than one day ahead."
        )

    if arrivals.empty:
        ui.empty("No arrivals for this date. Create a booking that starts today under New booking.")
    for booking in arrivals.itertuples():
        with st.container(border=True):
            info, action = st.columns([5, 1], vertical_alignment="center")
            with info:
                ui.render(
                    '<div class="ag-row" style="border:0;padding:0;justify-content:flex-start">'
                    f'<div class="room">{ui.esc(booking.RoomNumber)}</div>'
                    f'<div><div class="main">{ui.esc(booking.Guest)} &nbsp;{ui.tier_badge(booking.VIPTier)}</div>'
                    f'<div class="meta">Booking #{int(booking.BookingID)} · {ui.esc(booking.TypeName)} · '
                    f'{int(booking.Nights)} night(s) · {int(booking.Persons)} guest(s) · {ui.esc(booking.Channel)}'
                    f' &nbsp; {ui.status_pill(booking.Status)}</div></div>'
                    "</div>"
                )
            with action:
                if booking.Status == "Confirmed":
                    if st.button("Check in", type="primary", key=f"checkin_{int(booking.BookingID)}", width="stretch"):
                        try:
                            outcome = procs.check_in(int(booking.BookingID))
                        except db.DatabaseError as error:
                            ui.flash_error(error)
                        else:
                            ui.flash(
                                "success", f"{booking.Guest} is checked in",
                                f"Room {outcome.get('RoomNumber')} is now {outcome.get('RoomStatusNow')}.",
                                "Procedure sp_CheckIn · trigger trg_Bookings_RoomStatus",
                            )
                        st.rerun()

# ===========================================================================
# (d) In-house
# ===========================================================================
else:
    final_bill = st.session_state.get("fd_last_checkout")
    if final_bill:
        bill_column, note_column = st.columns([1.2, 1], gap="large")
        with bill_column:
            ui.invoice_card(
                final_bill, "Final bill",
                f"Room status now: {final_bill.get('RoomStatusNow')} · Guest tier now: {final_bill.get('GuestTierNow')}",
            )
        with note_column:
            ui.render(
                '<div class="ag-card"><div class="ag-overline">Checked out</div>'
                '<div class="ag-section-note" style="margin-top:0.5rem">sp_CheckOut settled the balance and closed '
                'the stay in one transaction. The room was set to Cleaning by the trigger '
                'trg_Bookings_RoomStatus, and trg_Payments_VIPUpgrade re-checked the guest\'s tier.</div></div>'
            )
            if st.button("Done", key="ih_done"):
                st.session_state.pop("fd_last_checkout", None)
                st.rerun()
        ui.hairline()

    in_house = queries.in_house()
    ui.section("In-house guests", f"{len(in_house)} room(s) occupied · from the view vw_InHouseGuests")

    if in_house.empty:
        ui.empty("Nobody is in the hotel right now.")
    else:
        list_column, detail_column = st.columns([1.25, 1], gap="large")

        with list_column:
            table = in_house[["RoomNumber", "Guest", "VIPTier", "TypeName", "CheckOutDate", "BillTotal", "Balance"]]
            st.dataframe(
                table.rename(columns={"RoomNumber": "Room", "VIPTier": "Tier", "TypeName": "Room type",
                                      "CheckOutDate": "Departs", "BillTotal": "Bill"}),
                hide_index=True, width="stretch", height=430,
                column_config={
                    "Bill": st.column_config.NumberColumn(format="PKR %,.0f"),
                    "Balance": st.column_config.NumberColumn(format="PKR %,.0f"),
                    "Departs": st.column_config.DateColumn(format="DD MMM YYYY"),
                },
            )

        with detail_column:
            labels = {int(g.BookingID): f"Room {g.RoomNumber} · {g.Guest}" for g in in_house.itertuples()}
            booking_id = st.selectbox("Guest", list(labels), format_func=labels.get, key="ih_booking")
            guest = in_house[in_house["BookingID"] == booking_id].iloc[0]
            ui.render(f'<div style="margin:0.2rem 0 0.5rem 0">{ui.tier_badge(guest.VIPTier)} '
                      f'<span class="ag-section-note">&nbsp;{ui.esc(guest.TypeName)} · {ui.esc(guest.ViewType)} view'
                      f' · {int(guest.Persons)} guest(s)</span></div>')
            ui.invoice_card(queries.invoice(booking_id), "Running bill", "From the view vw_GuestInvoice.")

            lines = queries.service_lines(booking_id)
            with st.expander(f"Services charged ({len(lines)})"):
                if lines.empty:
                    st.caption("No services yet.")
                else:
                    st.dataframe(lines[["UsageDate", "ServiceName", "Quantity", "LineTotal"]].rename(
                        columns={"UsageDate": "Date", "ServiceName": "Service", "Quantity": "Qty",
                                 "LineTotal": "Total"}),
                        hide_index=True, width="stretch")

            ui.section("Add a service", "Runs sp_AddService")
            services = queries.services()
            service_labels = {
                int(s.ServiceID): f"{s.ServiceName} · {s.Category} · {ui.pkr(s.Price)}"
                                  + ("" if s.IsAvailable else " · unavailable")
                for s in services.itertuples()
            }
            staff = queries.staff()
            staff_labels = {int(s.StaffID): f"{s.FullName} · {s.Role}" for s in staff.itertuples()}
            service_id = st.selectbox("Service", list(service_labels), format_func=service_labels.get, key="ih_service")
            q1, q2 = st.columns([1, 2.2])
            quantity = q1.number_input("Quantity", min_value=1, max_value=20, value=1, key="ih_quantity")
            staff_id = q2.selectbox("Delivered by", [None] + list(staff_labels), key="ih_staff",
                                    format_func=lambda s: "Not recorded" if s is None else staff_labels[s])
            if st.button("Add to room bill", key="ih_add"):
                try:
                    updated = procs.add_service(booking_id, service_id, int(quantity), staff_id)
                except db.DatabaseError as error:
                    ui.flash_error(error)
                else:
                    name = service_labels[service_id].split(" · ")[0]
                    ui.flash("success", f"{int(quantity)} × {name} charged to room {guest.RoomNumber}",
                             f"Bill total is now {ui.pkr(updated.get('BillTotal'))}.", "Procedure sp_AddService")
                    st.session_state.pop("ih_quantity", None)  # back to 1 for the next charge
                st.rerun()

            ui.section("Check out", "Runs sp_CheckOut: settlement and status change in one transaction")
            o1, o2 = st.columns([1.6, 1], vertical_alignment="bottom")
            pay_method = o1.selectbox("Settle the balance by", config.PAYMENT_METHODS, key="ih_method")
            if o2.button("Check out", type="primary", key="ih_checkout", width="stretch"):
                try:
                    outcome = procs.check_out(booking_id, pay_method)
                except db.DatabaseError as error:
                    ui.flash_error(error)
                else:
                    st.session_state["fd_last_checkout"] = {**queries.invoice(booking_id), **outcome.bill}
                    ui.flash(
                        "success", f"{outcome.guest} has checked out",
                        f"Room {outcome.bill.get('RoomNumber')} is now {outcome.bill.get('RoomStatusNow')}. "
                        f"Bill {ui.pkr(outcome.bill.get('BillTotal'))}, paid in full.",
                        "Procedure sp_CheckOut · triggers trg_Bookings_RoomStatus and trg_Payments_VIPUpgrade",
                    )
                    if outcome.upgraded_to:
                        ui.flash_vip(outcome.guest, outcome.upgraded_to)
                    for widget_key in ("ih_quantity", "ih_service", "ih_staff"):
                        st.session_state.pop(widget_key, None)
                st.rerun()
