/* =====================================================================
   AURELIA GRAND, KARACHI  |  File 06 : Advanced features - live demo
   A complete guest journey that exercises every view, function,
   procedure, trigger, transaction and index from file 05.
   Run it top to bottom (F5). It is safe to run more than once.
   ===================================================================== */
USE AureliaGrand;
GO

/* ---------- 1. VIEWS ---------- */
SELECT TOP (10) * FROM dbo.vw_InHouseGuests ORDER BY RoomNumber;                -- who is in the hotel now
SELECT TOP (10) * FROM dbo.vw_GuestInvoice  WHERE Status = 'CheckedOut' AND Balance > 0 ORDER BY Balance DESC;   -- unpaid bills
SELECT TOP (10) * FROM dbo.vw_GuestLoyalty  ORDER BY LifetimeSpend DESC;       -- best guests
GO

/* ---------- 2. FUNCTIONS ---------- */
SELECT TOP (5) BookingID,
       dbo.fn_BookingBill(BookingID) AS Bill,
       dbo.fn_AmountPaid(BookingID)  AS Paid
FROM   Bookings
WHERE  Status = 'CheckedOut'
ORDER BY BookingID DESC;

SELECT TypeName, COUNT(*) AS FreeRooms                      -- table-valued function
FROM   dbo.fn_AvailableRooms('2026-12-30', '2027-01-02')
GROUP BY TypeName;
GO

/* ---------- 3. STORED PROCEDURE: search free rooms for a family of 3 over New Year ---------- */
EXEC dbo.sp_SearchAvailableRooms @CheckIn = '2026-12-30', @CheckOut = '2027-01-02', @Persons = 3;
GO

/* =====================================================================
   4. GUEST JOURNEY: book -> check in -> spa -> check out
   We pick a Silver guest who is close to Gold, so the VIP trigger
   upgrades them live at check-out.
   ===================================================================== */
DECLARE @Guest INT, @Room VARCHAR(5), @NewID INT, @Today DATE = CAST(GETDATE() AS DATE);
DECLARE @Out DATE = DATEADD(DAY, 2, @Today);

SELECT TOP (1) @Guest = GuestID
FROM   dbo.vw_GuestLoyalty
WHERE  VIPTier = 'Silver' AND LifetimeSpend BETWEEN 550000 AND 700000
ORDER BY LifetimeSpend DESC;

SELECT TOP (1) @Room = RoomNumber
FROM   dbo.fn_AvailableRooms(@Today, @Out)
WHERE  TypeName IN ('Junior Suite', 'Executive Room', 'Presidential Suite')
ORDER BY BaseRate DESC;

SELECT 'Before' AS Stage, GuestID, Guest, VIPTier, LifetimeSpend FROM dbo.vw_GuestLoyalty WHERE GuestID = @Guest;
SELECT 'Room before' AS Stage, RoomNumber, Status FROM Rooms WHERE RoomNumber = @Room;

/* 4a. Booking + deposit in one transaction (sp_CreateBooking) */
EXEC dbo.sp_CreateBooking
     @GuestID = @Guest, @RoomNumber = @Room, @StaffID = 3,
     @CheckIn = @Today, @CheckOut = @Out, @Adults = 2,
     @Channel = 'Website', @DepositAmount = 50000, @DepositMethod = 'JazzCash',
     @NewBookingID = @NewID OUTPUT;

/* 4b. TRIGGER trg_Bookings_NoDoubleBooking: try to sell the same room again */
BEGIN TRY
    INSERT INTO Bookings (GuestID, RoomID, StaffID, CheckInDate, CheckOutDate, Channel, RatePerNight)
    SELECT 1, RoomID, 4, @Today, DATEADD(DAY, 1, @Today), 'Walk-in', 50000
    FROM   Rooms WHERE RoomNumber = @Room;
END TRY
BEGIN CATCH
    SELECT 'Trigger blocked a double booking' AS Demo, ERROR_NUMBER() AS ErrorNo, ERROR_MESSAGE() AS Message;
END CATCH;

/* 4c. Check in -> TRIGGER trg_Bookings_RoomStatus sets the room to Occupied */
EXEC dbo.sp_CheckIn @BookingID = @NewID;

/* 4d. Room charges during the stay */
EXEC dbo.sp_AddService @BookingID = @NewID, @ServiceID = 10, @Quantity = 1, @StaffID = 16;   -- Couples Spa Retreat
EXEC dbo.sp_AddService @BookingID = @NewID, @ServiceID = 2,  @Quantity = 2, @StaffID = 12;   -- Chef's Tasting Dinner x2
BEGIN TRY
    EXEC dbo.sp_AddService @BookingID = @NewID, @ServiceID = 16;                              -- yacht is unavailable
END TRY
BEGIN CATCH
    SELECT 'Procedure rule' AS Demo, ERROR_MESSAGE() AS Message;
END CATCH;

/* 4e. Check out: settlement + status change in one transaction.
       TRIGGER sets room to Cleaning, TRIGGER trg_Payments_VIPUpgrade promotes the guest */
EXEC dbo.sp_CheckOut @BookingID = @NewID, @Method = 'Card';

SELECT 'After' AS Stage, GuestID, Guest, VIPTier, LifetimeSpend FROM dbo.vw_GuestLoyalty WHERE GuestID = @Guest;
SELECT * FROM Payments WHERE BookingID = @NewID;
GO

/* =====================================================================
   5. TRANSACTION: all-or-nothing
   A bad deposit method makes the Payments CHECK fail, so the booking
   inserted just before it in the same transaction is rolled back too.
   ===================================================================== */
DECLARE @Before INT = (SELECT COUNT(*) FROM Bookings);
BEGIN TRY
    EXEC dbo.sp_CreateBooking @GuestID = 25, @RoomNumber = '1002', @StaffID = 5,
         @CheckIn = '2027-02-10', @CheckOut = '2027-02-12', @Adults = 2,
         @DepositAmount = 100000, @DepositMethod = 'Bitcoin';
END TRY
BEGIN CATCH
    SELECT 'Transaction rolled back' AS Demo, ERROR_MESSAGE() AS Reason;
END CATCH;
SELECT @Before AS BookingsBefore, (SELECT COUNT(*) FROM Bookings) AS BookingsAfter;   -- the same number
GO

/* =====================================================================
   6. TRIGGER trg_Bookings_SoftDelete: DELETE becomes a cancellation
   ===================================================================== */
DECLARE @Future INT;
EXEC dbo.sp_CreateBooking @GuestID = 40, @RoomNumber = '1001', @StaffID = 6,
     @CheckIn = '2027-03-05', @CheckOut = '2027-03-07', @Adults = 2,
     @Channel = 'Phone', @NewBookingID = @Future OUTPUT;

DELETE FROM Bookings WHERE BookingID = @Future;

SELECT BookingID, Status, 'still in the table, now Cancelled' AS Note
FROM   Bookings WHERE BookingID = @Future;
GO

/* =====================================================================
   7. INDEX: the same query with and without the index.
   Open the Messages tab to compare "logical reads".
   ===================================================================== */
SET STATISTICS IO ON;
SELECT COUNT(*) AS Stays, SUM(RoomCharge) AS Spend
FROM   Bookings WITH (INDEX(0))            -- force a full scan, as if no index existed
WHERE  GuestID = 120;

SELECT COUNT(*) AS Stays, SUM(RoomCharge) AS Spend
FROM   Bookings                            -- SQL Server now uses IX_Bookings_Guest
WHERE  GuestID = 120;
SET STATISTICS IO OFF;
GO

/* ---------- 8. STORED PROCEDURE: monthly management report ---------- */
EXEC dbo.sp_MonthlyPerformance @Year = 2026, @Month = 8;    -- Independence Day month
EXEC dbo.sp_MonthlyPerformance @Year = 2026, @Month = 10;   -- October
GO
