"""Read-only queries for the screens.

Everything here is a parameterised SELECT on the tables, the three views
(vw_InHouseGuests, vw_GuestInvoice, vw_GuestLoyalty) or the functions.
Nothing in this file changes data.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import db

# --------------------------------------------------------------------------
# Lobby
# --------------------------------------------------------------------------

_KPI_TONIGHT = """
SELECT (SELECT COUNT(*) FROM Rooms)                                AS TotalRooms,
       (SELECT COUNT(*) FROM Rooms WHERE Status = 'Maintenance')   AS OutOfService,
       COUNT(*)                                                    AS RoomsOccupied,
       ISNULL(SUM(b.RatePerNight), 0)                              AS RoomRevenue,
       ISNULL(SUM(b.Adults + b.Children), 0)                       AS Persons
FROM   Bookings b
WHERE  b.Status = 'CheckedIn';
"""

_ROOM_STATUS_COUNTS = "SELECT Status, COUNT(*) AS Rooms FROM Rooms GROUP BY Status;"

_MOVEMENT_COLUMNS = """
        b.BookingID,
        CONCAT(g.FirstName, ' ', g.LastName) AS Guest,
        g.VIPTier, r.RoomNumber, rt.TypeName, r.ViewType, r.FloorNo,
        b.CheckInDate, b.CheckOutDate, b.Nights,
        b.Adults + b.Children AS Persons,
        b.Channel, b.RatePerNight, b.Status
FROM    Bookings b
JOIN    Guests g     ON g.GuestID     = b.GuestID
JOIN    Rooms r      ON r.RoomID      = b.RoomID
JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
"""

_ARRIVALS = f"""
SELECT {_MOVEMENT_COLUMNS}
WHERE   b.CheckInDate = ? AND b.Status NOT IN ('Cancelled', 'NoShow')
ORDER BY CASE b.Status WHEN 'Confirmed' THEN 0 ELSE 1 END, r.FloorNo, r.RoomNumber;
"""

_DEPARTURES = f"""
SELECT {_MOVEMENT_COLUMNS}
WHERE   b.CheckOutDate = ? AND b.Status NOT IN ('Cancelled', 'NoShow')
ORDER BY CASE b.Status WHEN 'CheckedIn' THEN 0 ELSE 1 END, r.FloorNo, r.RoomNumber;
"""


def kpi_tonight() -> dict:
    frame = db.read(_KPI_TONIGHT)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def room_status_counts() -> dict:
    frame = db.read(_ROOM_STATUS_COUNTS)
    return {str(row.Status): int(row.Rooms) for row in frame.itertuples()}


def arrivals(day: date) -> pd.DataFrame:
    return db.read(_ARRIVALS, (day,))


def departures(day: date) -> pd.DataFrame:
    return db.read(_DEPARTURES, (day,))


# --------------------------------------------------------------------------
# Front desk
# --------------------------------------------------------------------------

_GUEST_OPTIONS = """
SELECT GuestID, CONCAT(FirstName, ' ', LastName) AS Guest, City, VIPTier, IDDocument
FROM   Guests
ORDER BY FirstName, LastName;
"""

_STAFF = """
SELECT StaffID, FullName, Role
FROM   Staff
WHERE  IsActive = 1
ORDER BY CASE Role WHEN 'Front Desk' THEN 0 WHEN 'Concierge' THEN 1 ELSE 2 END, FullName;
"""

_SERVICES = "SELECT ServiceID, ServiceName, Category, Price, IsAvailable FROM Services ORDER BY Category, ServiceName;"

_ALL_ROOMS = """
SELECT r.RoomNumber, rt.TypeName, r.FloorNo, r.ViewType, rt.MaxOccupancy, rt.BaseRate AS RatePerNight, r.Status
FROM   Rooms r
JOIN   RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
ORDER BY r.FloorNo, r.RoomNumber;
"""

_IN_HOUSE = """
SELECT h.BookingID, h.RoomNumber, h.TypeName, h.FloorNo, h.ViewType, h.Guest, h.VIPTier, h.Nationality,
       h.CheckInDate, h.CheckOutDate, h.Nights, h.Persons,
       i.RoomCharge, i.ServiceCharge, i.BillTotal, i.Paid, i.Balance
FROM   dbo.vw_InHouseGuests h
JOIN   dbo.vw_GuestInvoice  i ON i.BookingID = h.BookingID
ORDER BY h.FloorNo, h.RoomNumber;
"""

_INVOICE = "SELECT * FROM dbo.vw_GuestInvoice WHERE BookingID = ?;"

_BILL_AND_PAID = "SELECT dbo.fn_BookingBill(?) AS Bill, dbo.fn_AmountPaid(?) AS Paid;"

_SERVICE_LINES = """
SELECT u.UsageDate, s.ServiceName, s.Category, u.Quantity, u.UnitPrice, u.LineTotal,
       st.FullName AS DeliveredBy
FROM   ServiceUsage u
JOIN   Services s   ON s.ServiceID = u.ServiceID
LEFT JOIN Staff st  ON st.StaffID  = u.StaffID
WHERE  u.BookingID = ?
ORDER BY u.UsageID;
"""

_PAYMENTS = """
SELECT PaymentDate, PaymentType, Method, Amount, TransactionRef
FROM   Payments
WHERE  BookingID = ?
ORDER BY PaymentID;
"""


def guest_options() -> pd.DataFrame:
    return db.read(_GUEST_OPTIONS)


def staff() -> pd.DataFrame:
    return db.read(_STAFF)


def services() -> pd.DataFrame:
    return db.read(_SERVICES)


def all_rooms() -> pd.DataFrame:
    return db.read(_ALL_ROOMS)


def in_house() -> pd.DataFrame:
    return db.read(_IN_HOUSE)


def invoice(booking_id: int) -> dict:
    frame = db.read(_INVOICE, (int(booking_id),))
    return frame.iloc[0].to_dict() if not frame.empty else {}


def bill_and_paid(booking_id: int) -> dict:
    """fn_BookingBill and fn_AmountPaid for one booking."""
    frame = db.read(_BILL_AND_PAID, (int(booking_id), int(booking_id)))
    return frame.iloc[0].to_dict() if not frame.empty else {}


def service_lines(booking_id: int) -> pd.DataFrame:
    return db.read(_SERVICE_LINES, (int(booking_id),))


def payments(booking_id: int) -> pd.DataFrame:
    return db.read(_PAYMENTS, (int(booking_id),))


# --------------------------------------------------------------------------
# Room map
# --------------------------------------------------------------------------

_ROOM_MAP = """
SELECT r.RoomID, r.RoomNumber, r.FloorNo, r.ViewType, r.Status, r.IsSmoking,
       rt.TypeName, rt.BaseRate, rt.MaxOccupancy, rt.BedType, rt.SizeSqFt
FROM   Rooms r
JOIN   RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
ORDER BY r.FloorNo DESC, r.RoomNumber;
"""

_ROOM_CURRENT_GUEST = """
SELECT TOP (1) b.BookingID, CONCAT(g.FirstName, ' ', g.LastName) AS Guest, g.VIPTier, g.Nationality,
       b.CheckInDate, b.CheckOutDate, b.Nights, b.Adults + b.Children AS Persons,
       i.BillTotal, i.Paid, i.Balance
FROM   Bookings b
JOIN   Guests g ON g.GuestID = b.GuestID
JOIN   Rooms  r ON r.RoomID  = b.RoomID
JOIN   dbo.vw_GuestInvoice i ON i.BookingID = b.BookingID
WHERE  r.RoomNumber = ? AND b.Status = 'CheckedIn'
ORDER BY b.CheckInDate DESC;
"""

_ROOM_NEXT_BOOKING = """
SELECT TOP (1) b.BookingID, CONCAT(g.FirstName, ' ', g.LastName) AS Guest, g.VIPTier,
       b.CheckInDate, b.CheckOutDate, b.Nights, b.Channel
FROM   Bookings b
JOIN   Guests g ON g.GuestID = b.GuestID
JOIN   Rooms  r ON r.RoomID  = b.RoomID
WHERE  r.RoomNumber = ? AND b.Status = 'Confirmed' AND b.CheckInDate >= ?
ORDER BY b.CheckInDate;
"""


def room_map() -> pd.DataFrame:
    return db.read(_ROOM_MAP)


def room_current_guest(room_number: str) -> dict:
    frame = db.read(_ROOM_CURRENT_GUEST, (str(room_number),))
    return frame.iloc[0].to_dict() if not frame.empty else {}


def room_next_booking(room_number: str, day: date) -> dict:
    frame = db.read(_ROOM_NEXT_BOOKING, (str(room_number), day))
    return frame.iloc[0].to_dict() if not frame.empty else {}


# --------------------------------------------------------------------------
# Guests
# --------------------------------------------------------------------------

_GUEST_SEARCH = """
SELECT TOP (60) g.GuestID, CONCAT(g.FirstName, ' ', g.LastName) AS Guest, g.VIPTier,
       g.City, g.Nationality, g.Email, g.Phone, g.IDDocument
FROM   Guests g
WHERE  CONCAT(g.FirstName, ' ', g.LastName) LIKE ?
   OR  g.IDDocument LIKE ?
   OR  g.Email      LIKE ?
   OR  g.Phone      LIKE ?
ORDER BY g.FirstName, g.LastName;
"""

_GUEST_PROFILE = """
SELECT g.GuestID, g.FirstName, g.LastName, g.Gender, g.Email, g.Phone, g.IDDocument,
       g.Nationality, g.City, g.DateOfBirth, g.VIPTier, g.CreatedAt,
       l.Stays, l.Nights, l.LifetimeSpend, l.LastVisit
FROM   Guests g
JOIN   dbo.vw_GuestLoyalty l ON l.GuestID = g.GuestID
WHERE  g.GuestID = ?;
"""

_GUEST_STAYS = """
SELECT i.BookingID, i.RoomNumber, rt.TypeName, i.CheckInDate, i.CheckOutDate, i.Nights,
       i.Status, i.Channel, i.RoomCharge, i.ServiceCharge, i.BillTotal, i.Paid, i.Balance
FROM   dbo.vw_GuestInvoice i
JOIN   Bookings b   ON b.BookingID    = i.BookingID
JOIN   Rooms r      ON r.RoomID       = b.RoomID
JOIN   RoomTypes rt ON rt.RoomTypeID  = r.RoomTypeID
WHERE  b.GuestID = ?
ORDER BY i.CheckInDate DESC;
"""

_LEADERBOARD = """
SELECT TOP (10) GuestID, Guest, City, Nationality, VIPTier, Stays, Nights, LifetimeSpend, LastVisit
FROM   dbo.vw_GuestLoyalty
ORDER BY LifetimeSpend DESC;
"""

_TIER_COUNTS = "SELECT VIPTier, COUNT(*) AS Guests FROM Guests GROUP BY VIPTier;"


def _like(term: str) -> str:
    """Escape LIKE wildcards typed by the user, then wrap in %...%."""
    escaped = term.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    return f"%{escaped}%"


def guest_search(term: str) -> pd.DataFrame:
    pattern = _like(term.strip())
    return db.read(_GUEST_SEARCH, (pattern, pattern, pattern, pattern))


def guest_profile(guest_id: int) -> dict:
    frame = db.read(_GUEST_PROFILE, (int(guest_id),))
    return frame.iloc[0].to_dict() if not frame.empty else {}


def guest_stays(guest_id: int) -> pd.DataFrame:
    return db.read(_GUEST_STAYS, (int(guest_id),))


def leaderboard() -> pd.DataFrame:
    return db.read(_LEADERBOARD)


def tier_counts() -> dict:
    frame = db.read(_TIER_COUNTS)
    return {str(row.VIPTier): int(row.Guests) for row in frame.itertuples()}


# --------------------------------------------------------------------------
# About
# --------------------------------------------------------------------------

_TABLE_COUNTS = """
SELECT 'RoomTypes' AS TableName, COUNT(*) AS [RowCount] FROM RoomTypes
UNION ALL SELECT 'Rooms',        COUNT(*) FROM Rooms
UNION ALL SELECT 'Guests',       COUNT(*) FROM Guests
UNION ALL SELECT 'Staff',        COUNT(*) FROM Staff
UNION ALL SELECT 'Bookings',     COUNT(*) FROM Bookings
UNION ALL SELECT 'Services',     COUNT(*) FROM Services
UNION ALL SELECT 'ServiceUsage', COUNT(*) FROM ServiceUsage
UNION ALL SELECT 'Payments',     COUNT(*) FROM Payments;
"""

_DATABASE_OBJECTS = """
SELECT o.name AS ObjectName,
       CASE o.type WHEN 'P'  THEN 'Stored procedure'
                   WHEN 'V'  THEN 'View'
                   WHEN 'TR' THEN 'Trigger'
                   WHEN 'FN' THEN 'Scalar function'
                   WHEN 'IF' THEN 'Table-valued function'
                   WHEN 'TF' THEN 'Table-valued function' END AS ObjectType
FROM   sys.objects o
WHERE  o.is_ms_shipped = 0 AND o.type IN ('P', 'V', 'TR', 'FN', 'IF', 'TF')
UNION ALL
SELECT i.name, 'Index'
FROM   sys.indexes i
JOIN   sys.objects t ON t.object_id = i.object_id
WHERE  t.is_ms_shipped = 0 AND i.is_primary_key = 0 AND i.is_unique_constraint = 0
  AND  i.type_desc = 'NONCLUSTERED'
ORDER BY ObjectType, ObjectName;
"""

_SERVER_INFO = """
SELECT CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(40)) AS Version,
       CAST(SERVERPROPERTY('Edition') AS VARCHAR(80))        AS Edition,
       DB_NAME()                                             AS DatabaseName,
       CAST(GETDATE() AS DATE)                               AS ServerDate;
"""


def table_counts() -> pd.DataFrame:
    return db.read(_TABLE_COUNTS)


def database_objects() -> pd.DataFrame:
    return db.read(_DATABASE_OBJECTS)


def server_info() -> dict:
    frame = db.read(_SERVER_INFO)
    return frame.iloc[0].to_dict() if not frame.empty else {}
