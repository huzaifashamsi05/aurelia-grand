/* =====================================================================
   AURELIA GRAND, KARACHI  |  SQL Lab extras (written for the web app)
   Two demonstrations of the trigger trg_Bookings_NoDoubleBooking.

   The app itself never inserts into Bookings: it always calls
   sp_CreateBooking, which refuses a taken room with error 50022 before
   the trigger is reached. To SEE the trigger (error 50001) a row has to be
   inserted directly, as file 06 step 4b does. The SQL Lab runs both
   scripts inside a transaction that is rolled back, so nothing is saved.
   ===================================================================== */
USE AureliaGrand;
GO

/* ---------- 1. TRIGGER trg_Bookings_NoDoubleBooking: caught with TRY / CATCH ---------- */
DECLARE @RoomID INT, @RoomNumber VARCHAR(5), @In DATE, @Out DATE;

SELECT TOP (1) @RoomID = b.RoomID, @RoomNumber = r.RoomNumber, @In = b.CheckInDate, @Out = b.CheckOutDate
FROM   Bookings b
JOIN   Rooms r ON r.RoomID = b.RoomID
WHERE  b.Status = 'CheckedIn'
ORDER BY r.RoomNumber;

SELECT @RoomNumber AS RoomAlreadyTaken, @In AS TakenFrom, @Out AS TakenUntil;

BEGIN TRY
    INSERT INTO Bookings (GuestID, RoomID, StaffID, BookingDate, CheckInDate, CheckOutDate, Channel, RatePerNight)
    VALUES (1, @RoomID, 4, @In, @In, @Out, 'Walk-in', 50000);          -- same room, same nights
END TRY
BEGIN CATCH
    SELECT 'Trigger blocked a double booking' AS Demo, ERROR_NUMBER() AS ErrorNo, ERROR_MESSAGE() AS Message;
END CATCH;
GO

/* ---------- 2. TRIGGER trg_Bookings_NoDoubleBooking: the same INSERT without TRY / CATCH ---------- */
DECLARE @RoomID INT, @RoomNumber VARCHAR(5), @In DATE, @Out DATE;

SELECT TOP (1) @RoomID = b.RoomID, @RoomNumber = r.RoomNumber, @In = b.CheckInDate, @Out = b.CheckOutDate
FROM   Bookings b
JOIN   Rooms r ON r.RoomID = b.RoomID
WHERE  b.Status = 'CheckedIn'
ORDER BY r.RoomNumber;

SELECT @RoomNumber AS RoomAlreadyTaken, @In AS TakenFrom, @Out AS TakenUntil;

INSERT INTO Bookings (GuestID, RoomID, StaffID, BookingDate, CheckInDate, CheckOutDate, Channel, RatePerNight)
VALUES (1, @RoomID, 4, @In, @In, @Out, 'Walk-in', 50000);              -- the trigger THROWs error 50001
GO
