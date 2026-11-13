/* =====================================================================
   AURELIA GRAND, KARACHI  |  File 03 : Data operations (CRUD)
   Shows: SELECT, WHERE, AND, OR, NOT, BETWEEN, IN, LIKE, DISTINCT,
          ORDER BY, INSERT, UPDATE, DELETE  (+ constraints in action)
   Run each block on its own (select it and press F5) during the demo.
   ===================================================================== */
USE AureliaGrand;
GO

/* ---------- SELECT : the full room catalogue ---------- */
SELECT RoomTypeID, TypeName, BaseRate, MaxOccupancy, BedType, SizeSqFt
FROM   RoomTypes;

/* ---------- WHERE + AND : sea-view rooms on floor 6 or above that are free right now ---------- */
SELECT RoomNumber, FloorNo, ViewType, Status
FROM   Rooms
WHERE  ViewType = 'Sea'
  AND  FloorNo >= 6
  AND  Status = 'Available';

/* ---------- OR : guests from Lahore or Islamabad who are Platinum members ---------- */
SELECT GuestID, FirstName, LastName, City, VIPTier
FROM   Guests
WHERE  VIPTier = 'Platinum'
  AND (City = 'Lahore' OR City = 'Islamabad');

/* ---------- NOT : every booking that is NOT cancelled and NOT a no-show ---------- */
SELECT COUNT(*) AS LiveBookings
FROM   Bookings
WHERE  NOT Status IN ('Cancelled', 'NoShow');

/* ---------- BETWEEN : arrivals over the 25 December long weekend (Quaid-e-Azam Day) ---------- */
SELECT BookingID, GuestID, RoomID, CheckInDate, CheckOutDate, RatePerNight
FROM   Bookings
WHERE  CheckInDate BETWEEN '2026-12-24' AND '2026-12-26'
ORDER  BY CheckInDate;

/* ---------- BETWEEN on numbers : services priced from PKR 5,000 to 15,000 ---------- */
SELECT ServiceName, Category, Price
FROM   Services
WHERE  Price BETWEEN 5000 AND 15000
ORDER  BY Price DESC;

/* ---------- IN : foreign guests from the Gulf ---------- */
SELECT FirstName, LastName, Nationality, City
FROM   Guests
WHERE  Nationality IN ('United Arab Emirates', 'Saudi Arabia');

/* ---------- LIKE : guests whose surname starts with 'Kh' and who use Gmail ---------- */
SELECT FirstName, LastName, Email
FROM   Guests
WHERE  LastName LIKE 'Kh%'
  AND  Email    LIKE '%@gmail.com';

/* ---------- LIKE with a single-character wildcard : rooms 901 to 909 (the suite floor) ---------- */
SELECT RoomNumber, RoomTypeID, ViewType
FROM   Rooms
WHERE  RoomNumber LIKE '90_';

/* ---------- DISTINCT : which cities do our Pakistani guests come from? ---------- */
SELECT DISTINCT City
FROM   Guests
WHERE  Nationality = 'Pakistan'
ORDER  BY City;

/* ---------- ORDER BY (two keys) : the most expensive services first, then by name ---------- */
SELECT Category, ServiceName, Price
FROM   Services
ORDER  BY Category ASC, Price DESC;

/* =====================================================================
   INSERT / UPDATE / DELETE on a demo guest, so real data is not damaged
   ===================================================================== */

/* ---------- INSERT : a new guest (DEFAULT fills Nationality, VIPTier, CreatedAt) ---------- */
INSERT INTO Guests (FirstName, LastName, Gender, Email, Phone, IDDocument, City, DateOfBirth)
VALUES ('Saif', 'Wahab', 'M', 'saif.wahab.demo@gmail.com', '+92-300-5550155', '42101-5550155-1', 'Karachi', '2005-04-12');

SELECT GuestID, FirstName, LastName, Nationality, VIPTier, CreatedAt
FROM   Guests
WHERE  Email = 'saif.wahab.demo@gmail.com';

/* ---------- UPDATE : the guest moves city and is upgraded to Gold ---------- */
UPDATE Guests
SET    City    = 'Lahore',
       VIPTier = 'Gold'
WHERE  Email   = 'saif.wahab.demo@gmail.com';

SELECT FirstName, LastName, City, VIPTier
FROM   Guests
WHERE  Email = 'saif.wahab.demo@gmail.com';

/* ---------- UPDATE many rows : 5% price revision on all spa services ---------- */
BEGIN TRANSACTION;
    UPDATE Services
    SET    Price = ROUND(Price * 1.05, -2)
    WHERE  Category = 'Spa';
    SELECT ServiceName, Price FROM Services WHERE Category = 'Spa';
ROLLBACK TRANSACTION;          -- undo, this was only a demonstration
SELECT ServiceName, Price FROM Services WHERE Category = 'Spa';

/* ---------- DELETE : remove the demo guest ---------- */
DELETE FROM Guests
WHERE  Email = 'saif.wahab.demo@gmail.com';

SELECT COUNT(*) AS StillThere
FROM   Guests
WHERE  Email = 'saif.wahab.demo@gmail.com';
GO

/* =====================================================================
   Constraints doing their job (each statement below is EXPECTED to fail)
   ===================================================================== */

/* CHECK : check-out must be after check-in */
BEGIN TRY
    INSERT INTO Bookings (GuestID, RoomID, StaffID, CheckInDate, CheckOutDate, Channel, RatePerNight)
    VALUES (1, 1, 3, '2026-12-10', '2026-12-08', 'Website', 32000);
END TRY
BEGIN CATCH
    SELECT 'CHECK CK_Bookings_Dates' AS ConstraintTested, ERROR_MESSAGE() AS Result;
END CATCH;

/* UNIQUE : two guests cannot share one CNIC / passport */
BEGIN TRY
    INSERT INTO Guests (FirstName, LastName, Gender, Email, Phone, IDDocument, City, DateOfBirth)
    SELECT 'Copy', 'Cat', 'M', 'copy.cat@gmail.com', '+92-300-0000000', IDDocument, 'Karachi', '1990-01-01'
    FROM   Guests WHERE GuestID = 50;
END TRY
BEGIN CATCH
    SELECT 'UNIQUE UQ_Guests_IDDocument' AS ConstraintTested, ERROR_MESSAGE() AS Result;
END CATCH;

/* FOREIGN KEY : a guest who has bookings cannot be deleted */
BEGIN TRY
    DELETE FROM Guests WHERE GuestID = 1;
END TRY
BEGIN CATCH
    SELECT 'FOREIGN KEY FK_Bookings_Guests' AS ConstraintTested, ERROR_MESSAGE() AS Result;
END CATCH;

/* NOT NULL : every guest must have an email */
BEGIN TRY
    INSERT INTO Guests (FirstName, LastName, Gender, Email, Phone, IDDocument, City, DateOfBirth)
    VALUES ('No', 'Email', 'F', NULL, '+92-300-1111111', '42101-0000001-2', 'Karachi', '1995-01-01');
END TRY
BEGIN CATCH
    SELECT 'NOT NULL Guests.Email' AS ConstraintTested, ERROR_MESSAGE() AS Result;
END CATCH;
GO
