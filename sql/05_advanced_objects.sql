/* =====================================================================
   AURELIA GRAND, KARACHI  |  File 05 : Advanced database objects
   Required: any 2 of VIEW, STORED PROCEDURE, TRIGGER  ->  we built all 3,
   plus bonus objects: user-defined functions, transactions and indexes.

     Functions  : fn_BookingBill, fn_AmountPaid, fn_AvailableRooms
     Views      : vw_InHouseGuests, vw_GuestInvoice, vw_GuestLoyalty
     Procedures : sp_SearchAvailableRooms, sp_CreateBooking, sp_CheckIn,
                  sp_AddService, sp_CheckOut, sp_MonthlyPerformance
     Triggers   : trg_Bookings_NoDoubleBooking, trg_Bookings_RoomStatus,
                  trg_Bookings_SoftDelete, trg_Payments_VIPUpgrade
     Indexes    : 4 non-clustered indexes on the busiest foreign keys
   ===================================================================== */
USE AureliaGrand;
GO

/* =====================================================================
   PART A. INDEXES  (make the most frequent lookups fast)
   ===================================================================== */
CREATE NONCLUSTERED INDEX IX_Bookings_Room_Dates
    ON Bookings (RoomID, CheckInDate, CheckOutDate) INCLUDE (Status);
CREATE NONCLUSTERED INDEX IX_Bookings_Guest
    ON Bookings (GuestID) INCLUDE (CheckInDate, Status, RoomCharge);
CREATE NONCLUSTERED INDEX IX_ServiceUsage_Booking
    ON ServiceUsage (BookingID) INCLUDE (LineTotal);
CREATE NONCLUSTERED INDEX IX_Payments_Booking
    ON Payments (BookingID) INCLUDE (Amount, PaymentType);
GO

/* =====================================================================
   PART B. USER-DEFINED FUNCTIONS
   ===================================================================== */

/* Total bill of one booking = room charge + all services used */
CREATE OR ALTER FUNCTION dbo.fn_BookingBill (@BookingID INT)
RETURNS DECIMAL(12,2)
AS
BEGIN
    RETURN (SELECT b.RoomCharge + ISNULL((SELECT SUM(u.LineTotal) FROM ServiceUsage u WHERE u.BookingID = b.BookingID), 0)
            FROM   Bookings b
            WHERE  b.BookingID = @BookingID);
END;
GO

/* Net amount received for one booking (refunds are subtracted) */
CREATE OR ALTER FUNCTION dbo.fn_AmountPaid (@BookingID INT)
RETURNS DECIMAL(12,2)
AS
BEGIN
    RETURN ISNULL((SELECT SUM(CASE WHEN PaymentType = 'Refund' THEN -Amount ELSE Amount END)
                   FROM   Payments
                   WHERE  BookingID = @BookingID), 0);
END;
GO

/* Table-valued function: rooms that are free for the whole stay */
CREATE OR ALTER FUNCTION dbo.fn_AvailableRooms (@CheckIn DATE, @CheckOut DATE)
RETURNS TABLE
AS
RETURN
    SELECT r.RoomID, r.RoomNumber, r.FloorNo, r.ViewType,
           rt.RoomTypeID, rt.TypeName, rt.BaseRate, rt.MaxOccupancy
    FROM   Rooms r
    JOIN   RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
    WHERE  r.Status <> 'Maintenance'
      AND  NOT EXISTS (SELECT 1
                       FROM   Bookings b
                       WHERE  b.RoomID = r.RoomID
                         AND  b.Status IN ('Confirmed', 'CheckedIn', 'CheckedOut')
                         AND  b.CheckInDate  < @CheckOut      -- two stays overlap when each one
                         AND  @CheckIn       < b.CheckOutDate -- starts before the other one ends
                      );
GO

/* =====================================================================
   PART C. VIEWS
   ===================================================================== */

/* 1. Who is in the hotel right now (live front-desk board) */
CREATE OR ALTER VIEW dbo.vw_InHouseGuests
AS
SELECT  r.RoomNumber, rt.TypeName, r.FloorNo, r.ViewType,
        b.BookingID,
        CONCAT(g.FirstName, ' ', g.LastName) AS Guest,
        g.VIPTier, g.Nationality,
        b.CheckInDate, b.CheckOutDate, b.Nights,
        b.Adults + b.Children               AS Persons
FROM    Bookings b
JOIN    Guests g     ON g.GuestID     = b.GuestID
JOIN    Rooms r      ON r.RoomID      = b.RoomID
JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
WHERE   b.Status = 'CheckedIn';
GO

/* 2. Invoice for every booking: room + services - payments = balance */
CREATE OR ALTER VIEW dbo.vw_GuestInvoice
AS
SELECT  b.BookingID,
        CONCAT(g.FirstName, ' ', g.LastName)    AS Guest,
        r.RoomNumber, b.CheckInDate, b.CheckOutDate, b.Nights, b.Status, b.Channel,
        /* a cancelled or no-show booking is billed only what the hotel kept (deposit not refunded) */
        CASE WHEN b.Status IN ('Cancelled', 'NoShow') THEN ISNULL(p.NetPaid, 0) ELSE b.RoomCharge END AS RoomCharge,
        ISNULL(s.ServiceTotal, 0)               AS ServiceCharge,
        CASE WHEN b.Status IN ('Cancelled', 'NoShow') THEN ISNULL(p.NetPaid, 0)
             ELSE b.RoomCharge + ISNULL(s.ServiceTotal, 0) END AS BillTotal,
        ISNULL(p.NetPaid, 0)                    AS Paid,
        CASE WHEN b.Status IN ('Cancelled', 'NoShow') THEN 0
             ELSE b.RoomCharge + ISNULL(s.ServiceTotal, 0) - ISNULL(p.NetPaid, 0) END AS Balance
FROM    Bookings b
JOIN    Guests g ON g.GuestID = b.GuestID
JOIN    Rooms  r ON r.RoomID  = b.RoomID
LEFT JOIN (SELECT BookingID, SUM(LineTotal) AS ServiceTotal
           FROM   ServiceUsage GROUP BY BookingID) s ON s.BookingID = b.BookingID
LEFT JOIN (SELECT BookingID, SUM(CASE WHEN PaymentType = 'Refund' THEN -Amount ELSE Amount END) AS NetPaid
           FROM   Payments GROUP BY BookingID) p ON p.BookingID = b.BookingID;
GO

/* 3. Loyalty profile of every guest (used by the VIP trigger and the app) */
CREATE OR ALTER VIEW dbo.vw_GuestLoyalty
AS
SELECT  g.GuestID,
        CONCAT(g.FirstName, ' ', g.LastName) AS Guest,
        g.City, g.Nationality, g.VIPTier,
        COUNT(b.BookingID)                   AS Stays,
        SUM(ISNULL(b.Nights, 0))             AS Nights,
        SUM(ISNULL(b.RoomCharge, 0)) + SUM(ISNULL(s.ServiceTotal, 0)) AS LifetimeSpend,
        MAX(b.CheckOutDate)                  AS LastVisit
FROM    Guests g
LEFT JOIN Bookings b ON b.GuestID = g.GuestID AND b.Status IN ('CheckedOut', 'CheckedIn')
LEFT JOIN (SELECT BookingID, SUM(LineTotal) AS ServiceTotal
           FROM   ServiceUsage GROUP BY BookingID) s ON s.BookingID = b.BookingID
GROUP BY g.GuestID, g.FirstName, g.LastName, g.City, g.Nationality, g.VIPTier;
GO

/* =====================================================================
   PART D. TRIGGERS
   ===================================================================== */

/* 1. Business rule the table constraints cannot express:
      the same room can never be booked twice for overlapping nights */
CREATE OR ALTER TRIGGER dbo.trg_Bookings_NoDoubleBooking
ON Bookings
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1
               FROM   inserted i
               JOIN   Bookings b
                      ON  b.RoomID     = i.RoomID
                      AND b.BookingID <> i.BookingID
                      AND b.Status IN ('Confirmed', 'CheckedIn', 'CheckedOut')
                      AND b.CheckInDate < i.CheckOutDate
                      AND i.CheckInDate < b.CheckOutDate
               WHERE  i.Status IN ('Confirmed', 'CheckedIn', 'CheckedOut'))
        THROW 50001, 'Double booking blocked: this room is already booked for some of these nights.', 1;
        -- THROW inside a trigger aborts the statement and rolls the whole transaction back
END;
GO

/* 2. Keep the room status in step with the booking status */
CREATE OR ALTER TRIGGER dbo.trg_Bookings_RoomStatus
ON Bookings
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT UPDATE(Status) RETURN;

    UPDATE r
    SET    r.Status = CASE i.Status WHEN 'CheckedIn'  THEN 'Occupied'
                                    WHEN 'CheckedOut' THEN 'Cleaning' END
    FROM   Rooms r
    JOIN   inserted i ON i.RoomID    = r.RoomID
    JOIN   deleted  d ON d.BookingID = i.BookingID
    WHERE  i.Status <> d.Status
      AND  i.Status IN ('CheckedIn', 'CheckedOut');
END;
GO

/* 3. Bookings are never physically deleted: a DELETE becomes a cancellation,
      so the hotel keeps a full history for audit and reporting */
CREATE OR ALTER TRIGGER dbo.trg_Bookings_SoftDelete
ON Bookings
INSTEAD OF DELETE
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM deleted WHERE Status IN ('CheckedIn', 'CheckedOut'))
        THROW 50002, 'A stay that has already started cannot be deleted.', 1;

    UPDATE b
    SET    b.Status = 'Cancelled'
    FROM   Bookings b
    JOIN   deleted d ON d.BookingID = b.BookingID;

    PRINT CONCAT(@@ROWCOUNT, ' booking(s) marked as Cancelled instead of being deleted.');
END;
GO

/* 4. Automatic loyalty upgrade: when a payment arrives, re-check the guest's
      lifetime spend and promote (never demote) the VIP tier
      Silver -> Gold at PKR 750,000   Gold -> Platinum at PKR 2,000,000 */
CREATE OR ALTER TRIGGER dbo.trg_Payments_VIPUpgrade
ON Payments
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE g
    SET    g.VIPTier = x.NewTier
    FROM   Guests g
    JOIN  (SELECT l.GuestID,
                  CASE WHEN l.LifetimeSpend >= 2000000 THEN 'Platinum'
                       WHEN l.LifetimeSpend >=  750000 THEN 'Gold'
                       ELSE 'Silver' END AS NewTier
           FROM   dbo.vw_GuestLoyalty l
           WHERE  l.GuestID IN (SELECT b.GuestID FROM Bookings b JOIN inserted i ON i.BookingID = b.BookingID)
          ) x ON x.GuestID = g.GuestID
    WHERE  (x.NewTier = 'Platinum' AND g.VIPTier <> 'Platinum')
        OR (x.NewTier = 'Gold'     AND g.VIPTier =  'Silver');
END;
GO

/* =====================================================================
   PART E. STORED PROCEDURES
   ===================================================================== */

/* 1. Search: free rooms for given dates and party size, cheapest first */
CREATE OR ALTER PROCEDURE dbo.sp_SearchAvailableRooms
    @CheckIn  DATE,
    @CheckOut DATE,
    @Persons  TINYINT = 1
AS
BEGIN
    SET NOCOUNT ON;
    IF @CheckOut <= @CheckIn
        THROW 50010, 'Check-out must be after check-in.', 1;

    SELECT  RoomNumber, TypeName, FloorNo, ViewType, MaxOccupancy,
            BaseRate                                   AS RatePerNight,
            BaseRate * DATEDIFF(DAY, @CheckIn, @CheckOut) AS StayTotal
    FROM    dbo.fn_AvailableRooms(@CheckIn, @CheckOut)
    WHERE   MaxOccupancy >= @Persons
    ORDER BY BaseRate, FloorNo DESC, RoomNumber;
END;
GO

/* 2. Create a booking and take the deposit in ONE transaction:
      either both rows are saved or neither is */
CREATE OR ALTER PROCEDURE dbo.sp_CreateBooking
    @GuestID       INT,
    @RoomNumber    VARCHAR(5),
    @StaffID       INT,
    @CheckIn       DATE,
    @CheckOut      DATE,
    @Adults        TINYINT       = 1,
    @Children      TINYINT       = 0,
    @Channel       VARCHAR(15)   = 'Website',
    @DepositAmount DECIMAL(12,2) = 0,
    @DepositMethod VARCHAR(15)   = 'Card',
    @NewBookingID  INT           = NULL OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @RoomID INT, @Base DECIMAL(10,2), @Cap TINYINT, @Rate DECIMAL(10,2);

    SELECT @RoomID = r.RoomID, @Base = rt.BaseRate, @Cap = rt.MaxOccupancy
    FROM   Rooms r JOIN RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
    WHERE  r.RoomNumber = @RoomNumber;

    IF @RoomID IS NULL                               THROW 50020, 'Room number does not exist.', 1;
    IF @Adults + @Children > @Cap + 1                THROW 50021, 'Too many persons for this room type.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.fn_AvailableRooms(@CheckIn, @CheckOut) WHERE RoomID = @RoomID)
                                                     THROW 50022, 'Room is not available for these dates.', 1;

    /* dynamic pricing: December +25%, corporate -15%, website -5%, walk-in +5% */
    SET @Rate = @Base
              * CASE WHEN MONTH(@CheckIn) = 12 THEN 1.25 ELSE 1.00 END
              * CASE @Channel WHEN 'Corporate' THEN 0.85 WHEN 'Website' THEN 0.95
                              WHEN 'Walk-in'   THEN 1.05 ELSE 1.00 END;
    SET @Rate = ROUND(@Rate / 500, 0) * 500;

    BEGIN TRY
        BEGIN TRANSACTION;

            INSERT INTO Bookings (GuestID, RoomID, StaffID, BookingDate, CheckInDate, CheckOutDate,
                                  Adults, Children, Channel, RatePerNight, Status)
            VALUES (@GuestID, @RoomID, @StaffID, CAST(GETDATE() AS DATE), @CheckIn, @CheckOut,
                    @Adults, @Children, @Channel, @Rate, 'Confirmed');

            SET @NewBookingID = SCOPE_IDENTITY();

            IF @DepositAmount > 0
                INSERT INTO Payments (BookingID, PaymentDate, Amount, Method, PaymentType, TransactionRef)
                VALUES (@NewBookingID, CAST(GETDATE() AS DATE), @DepositAmount, @DepositMethod, 'Deposit',
                        CONCAT('AG', FORMAT(GETDATE(), 'yyMMdd'), '-N', @NewBookingID));

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    SELECT * FROM dbo.vw_GuestInvoice WHERE BookingID = @NewBookingID;
END;
GO

/* 3. Check-in (the trigger then marks the room Occupied) */
CREATE OR ALTER PROCEDURE dbo.sp_CheckIn
    @BookingID INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @Status VARCHAR(12), @In DATE;
    SELECT @Status = Status, @In = CheckInDate FROM Bookings WHERE BookingID = @BookingID;

    IF @Status IS NULL                               THROW 50030, 'Booking not found.', 1;
    IF @Status <> 'Confirmed'                        THROW 50031, 'Only a confirmed booking can be checked in.', 1;
    IF @In > DATEADD(DAY, 1, CAST(GETDATE() AS DATE)) THROW 50032, 'Too early: check-in date is more than 1 day away.', 1;

    UPDATE Bookings SET Status = 'CheckedIn' WHERE BookingID = @BookingID;

    SELECT b.BookingID, r.RoomNumber, r.Status AS RoomStatusNow, b.Status AS BookingStatus
    FROM   Bookings b JOIN Rooms r ON r.RoomID = b.RoomID
    WHERE  b.BookingID = @BookingID;
END;
GO

/* 4. Charge a service to a guest's room (price is copied at the time of use) */
CREATE OR ALTER PROCEDURE dbo.sp_AddService
    @BookingID INT,
    @ServiceID INT,
    @Quantity  TINYINT = 1,
    @StaffID   INT     = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM Bookings WHERE BookingID = @BookingID AND Status = 'CheckedIn')
        THROW 50040, 'Services can only be charged to a guest who is checked in.', 1;
    IF NOT EXISTS (SELECT 1 FROM Services WHERE ServiceID = @ServiceID AND IsAvailable = 1)
        THROW 50041, 'This service is not available at the moment.', 1;

    INSERT INTO ServiceUsage (BookingID, ServiceID, StaffID, UsageDate, Quantity, UnitPrice)
    SELECT @BookingID, ServiceID, @StaffID, CAST(GETDATE() AS DATE), @Quantity, Price
    FROM   Services
    WHERE  ServiceID = @ServiceID;

    SELECT BookingID, Guest, RoomCharge, ServiceCharge, BillTotal, Paid, Balance
    FROM   dbo.vw_GuestInvoice WHERE BookingID = @BookingID;
END;
GO

/* 5. Check-out: settle the balance and close the stay, all-or-nothing */
CREATE OR ALTER PROCEDURE dbo.sp_CheckOut
    @BookingID INT,
    @Method    VARCHAR(15) = 'Card'
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF NOT EXISTS (SELECT 1 FROM Bookings WHERE BookingID = @BookingID AND Status = 'CheckedIn')
        THROW 50050, 'Only a checked-in booking can be checked out.', 1;

    DECLARE @Due DECIMAL(12,2) = dbo.fn_BookingBill(@BookingID) - dbo.fn_AmountPaid(@BookingID);

    BEGIN TRY
        BEGIN TRANSACTION;
            IF @Due > 0
                INSERT INTO Payments (BookingID, PaymentDate, Amount, Method, PaymentType, TransactionRef)
                VALUES (@BookingID, CAST(GETDATE() AS DATE), @Due, @Method, 'Settlement',
                        CONCAT('AG', FORMAT(GETDATE(), 'yyMMdd'), '-S', @BookingID));

            UPDATE Bookings SET Status = 'CheckedOut' WHERE BookingID = @BookingID;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    SELECT i.BookingID, i.Guest, i.RoomNumber, i.BillTotal, i.Paid, i.Balance,
           r.Status AS RoomStatusNow, g.VIPTier AS GuestTierNow
    FROM   dbo.vw_GuestInvoice i
    JOIN   Bookings b ON b.BookingID = i.BookingID
    JOIN   Rooms    r ON r.RoomID    = b.RoomID
    JOIN   Guests   g ON g.GuestID   = b.GuestID
    WHERE  i.BookingID = @BookingID;
END;
GO

/* 6. One-click monthly management report for any month */
CREATE OR ALTER PROCEDURE dbo.sp_MonthlyPerformance
    @Year  INT,
    @Month INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @From DATE = DATEFROMPARTS(@Year, @Month, 1);
    DECLARE @To   DATE = DATEADD(MONTH, 1, @From);
    DECLARE @Days INT  = DATEDIFF(DAY, @From, @To);
    DECLARE @Rooms INT = (SELECT COUNT(*) FROM Rooms);

    ;WITH Nights AS (
        SELECT b.BookingID, b.RatePerNight,
               DATEDIFF(DAY,
                        CASE WHEN b.CheckInDate  > @From THEN b.CheckInDate  ELSE @From END,
                        CASE WHEN b.CheckOutDate < @To   THEN b.CheckOutDate ELSE @To   END) AS NightsInMonth
        FROM   Bookings b
        WHERE  b.Status IN ('CheckedOut', 'CheckedIn')
          AND  b.CheckInDate < @To AND b.CheckOutDate > @From
    )
    SELECT  FORMAT(@From, 'MMMM yyyy')                                     AS ReportMonth,
            SUM(NightsInMonth)                                             AS RoomsSold,
            @Rooms * @Days                                                 AS RoomsAvailable,
            CAST(100.0 * SUM(NightsInMonth) / (@Rooms * @Days) AS DECIMAL(5,1)) AS [Occupancy %],
            CAST(SUM(NightsInMonth * RatePerNight) / NULLIF(SUM(NightsInMonth), 0) AS DECIMAL(10,0)) AS ADR_PKR,
            CAST(SUM(NightsInMonth * RatePerNight) / (@Rooms * @Days) AS DECIMAL(10,0))             AS RevPAR_PKR,
            SUM(NightsInMonth * RatePerNight)                              AS RoomRevenue_PKR,
            (SELECT ISNULL(SUM(LineTotal), 0) FROM ServiceUsage
              WHERE UsageDate >= @From AND UsageDate < @To)                AS ServiceRevenue_PKR,
            (SELECT COUNT(*) FROM Bookings
              WHERE Status = 'Cancelled' AND CheckInDate >= @From AND CheckInDate < @To) AS Cancellations
    FROM    Nights;
END;
GO

PRINT 'AureliaGrand: 4 indexes, 3 functions, 3 views, 4 triggers and 6 stored procedures created.';
GO
