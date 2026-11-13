"""One Python wrapper per stored procedure.

This file is the ONLY place where the app changes data, and it never contains
an INSERT, UPDATE or DELETE: every write is an ``EXEC dbo.sp_...`` with
parameters. The transactions, triggers and constraints all run inside SQL Server.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from . import db

# --------------------------------------------------------------------------
# Fixed EXEC statements (parameters are bound with ? markers)
# --------------------------------------------------------------------------

_SEARCH_AVAILABLE_ROOMS = """
EXEC dbo.sp_SearchAvailableRooms @CheckIn = ?, @CheckOut = ?, @Persons = ?;
"""

_CREATE_BOOKING = """
SET NOCOUNT ON;
DECLARE @id INT;
EXEC dbo.sp_CreateBooking
     @GuestID = ?, @RoomNumber = ?, @StaffID = ?,
     @CheckIn = ?, @CheckOut = ?, @Adults = ?, @Children = ?,
     @Channel = ?, @DepositAmount = ?, @DepositMethod = ?,
     @NewBookingID = @id OUTPUT;
SELECT @id AS NewBookingID;
"""

_CHECK_IN = "EXEC dbo.sp_CheckIn @BookingID = ?;"

_ADD_SERVICE = "EXEC dbo.sp_AddService @BookingID = ?, @ServiceID = ?, @Quantity = ?, @StaffID = ?;"

_CHECK_OUT = "EXEC dbo.sp_CheckOut @BookingID = ?, @Method = ?;"

_MONTHLY_PERFORMANCE = "EXEC dbo.sp_MonthlyPerformance @Year = ?, @Month = ?;"

# Read-only helpers used to notice a VIP upgrade made by trg_Payments_VIPUpgrade.
_GUEST_TIER = "SELECT CONCAT(FirstName, ' ', LastName) AS Guest, VIPTier FROM Guests WHERE GuestID = ?;"
_BOOKING_GUEST = """
SELECT g.GuestID, CONCAT(g.FirstName, ' ', g.LastName) AS Guest, g.VIPTier
FROM   Bookings b
JOIN   Guests g ON g.GuestID = b.GuestID
WHERE  b.BookingID = ?;
"""


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@dataclass
class BookingResult:
    booking_id: int
    invoice: dict
    guest: str
    tier_before: str | None
    tier_after: str | None

    @property
    def upgraded_to(self) -> str | None:
        if self.tier_before and self.tier_after and self.tier_before != self.tier_after:
            return self.tier_after
        return None


@dataclass
class CheckOutResult:
    bill: dict
    guest: str
    tier_before: str | None
    tier_after: str | None

    @property
    def upgraded_to(self) -> str | None:
        if self.tier_before and self.tier_after and self.tier_before != self.tier_after:
            return self.tier_after
        return None


def _tier_of_guest(guest_id: int) -> tuple[str, str | None]:
    frame = db.fetch(_GUEST_TIER, (int(guest_id),))
    if frame.empty:
        return "", None
    return str(frame.iloc[0]["Guest"]), str(frame.iloc[0]["VIPTier"])


# --------------------------------------------------------------------------
# Procedures
# --------------------------------------------------------------------------

def search_available_rooms(check_in: date, check_out: date, persons: int) -> pd.DataFrame:
    """sp_SearchAvailableRooms: free rooms for the dates and party size (read-only)."""
    return db.read(_SEARCH_AVAILABLE_ROOMS, (check_in, check_out, int(persons)))


def create_booking(
    *,
    guest_id: int,
    room_number: str,
    staff_id: int,
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
    channel: str,
    deposit_amount: float,
    deposit_method: str,
) -> BookingResult:
    """sp_CreateBooking: booking + deposit in one transaction. Returns the invoice row."""
    guest, tier_before = _tier_of_guest(guest_id)
    result = db.execute_procedure(
        _CREATE_BOOKING,
        (
            int(guest_id), str(room_number), int(staff_id),
            check_in, check_out, int(adults), int(children),
            str(channel), Decimal(str(round(float(deposit_amount), 2))), str(deposit_method),
        ),
    )
    invoice = result.row(0)
    new_id = result.row(1).get("NewBookingID") or invoice.get("BookingID")
    _, tier_after = _tier_of_guest(guest_id)
    return BookingResult(int(new_id), invoice, guest, tier_before, tier_after)


def check_in(booking_id: int) -> dict:
    """sp_CheckIn: the trigger trg_Bookings_RoomStatus then marks the room Occupied."""
    return db.execute_procedure(_CHECK_IN, (int(booking_id),)).row(0)


def add_service(booking_id: int, service_id: int, quantity: int, staff_id: int | None) -> dict:
    """sp_AddService: charge a service to the room. Returns the updated invoice."""
    staff = int(staff_id) if staff_id is not None else None
    return db.execute_procedure(_ADD_SERVICE, (int(booking_id), int(service_id), int(quantity), staff)).row(0)


def check_out(booking_id: int, method: str) -> CheckOutResult:
    """sp_CheckOut: settle the balance and close the stay in one transaction."""
    before = db.fetch(_BOOKING_GUEST, (int(booking_id),))
    guest = str(before.iloc[0]["Guest"]) if not before.empty else ""
    tier_before = str(before.iloc[0]["VIPTier"]) if not before.empty else None
    bill = db.execute_procedure(_CHECK_OUT, (int(booking_id), str(method))).row(0)
    tier_after = bill.get("GuestTierNow")
    return CheckOutResult(bill, guest or str(bill.get("Guest", "")), tier_before, tier_after)


def monthly_performance(year: int, month: int) -> pd.DataFrame:
    """sp_MonthlyPerformance: one-row management report for a month (read-only)."""
    return db.read(_MONTHLY_PERFORMANCE, (int(year), int(month)))
