/* =====================================================================
   AURELIA GRAND, KARACHI  |  File 04 : 15 management reports
   Together they use: INNER / LEFT JOIN, GROUP BY, HAVING, COUNT, SUM,
   AVG, MIN, MAX, subqueries, CTEs, window functions, sorting and
   date filtering.
   "Today" is fixed to the data snapshot date so results never change.
   On a live system replace it with CAST(GETDATE() AS DATE).
   ===================================================================== */
USE AureliaGrand;
GO

/* ---------------------------------------------------------------------
   R01. Monthly Occupancy %, ADR and RevPAR (the 3 KPIs every hotel tracks)
        Occupancy = rooms sold / rooms available
        ADR       = room revenue / rooms sold       (average daily rate)
        RevPAR    = room revenue / rooms available  (revenue per available room)
   --------------------------------------------------------------------- */
DECLARE @Today DATE = '2026-11-25';
DECLARE @Rooms INT  = (SELECT COUNT(*) FROM Rooms);

WITH Calendar AS (
    SELECT CAST('2026-01-01' AS DATE) AS NightDate
    UNION ALL
    SELECT DATEADD(DAY, 1, NightDate) FROM Calendar WHERE NightDate < @Today
),
RoomNights AS (
    SELECT c.NightDate, b.RatePerNight
    FROM   Calendar c
    JOIN   Bookings b
           ON c.NightDate >= b.CheckInDate AND c.NightDate < b.CheckOutDate
    WHERE  b.Status IN ('CheckedOut', 'CheckedIn')
)
SELECT  FORMAT(MIN(c.NightDate), 'MMM yyyy')                                         AS [Month],
        COUNT(rn.NightDate)                                                          AS RoomsSold,
        COUNT(DISTINCT c.NightDate) * @Rooms                                         AS RoomsAvailable,
        CAST(100.0 * COUNT(rn.NightDate) / (COUNT(DISTINCT c.NightDate) * @Rooms) AS DECIMAL(5,1)) AS [Occupancy %],
        CAST(AVG(rn.RatePerNight) AS DECIMAL(10,0))                                  AS ADR_PKR,
        CAST(SUM(rn.RatePerNight) / (COUNT(DISTINCT c.NightDate) * @Rooms) AS DECIMAL(10,0)) AS RevPAR_PKR
FROM    Calendar c
LEFT JOIN RoomNights rn ON rn.NightDate = c.NightDate
GROUP BY YEAR(c.NightDate), MONTH(c.NightDate)
ORDER BY YEAR(c.NightDate), MONTH(c.NightDate)
OPTION (MAXRECURSION 400);
GO

/* ---------------------------------------------------------------------
   R02. Revenue by room type (which product earns the most?)
   --------------------------------------------------------------------- */
SELECT  rt.TypeName,
        COUNT(b.BookingID)                          AS Stays,
        SUM(b.Nights)                               AS RoomNights,
        SUM(b.RoomCharge)                           AS RoomRevenue_PKR,
        CAST(AVG(b.RatePerNight) AS DECIMAL(10,0))  AS AvgRate_PKR,
        MIN(b.RatePerNight)                         AS LowestRate,
        MAX(b.RatePerNight)                         AS HighestRate,
        CAST(100.0 * SUM(b.RoomCharge) / SUM(SUM(b.RoomCharge)) OVER () AS DECIMAL(5,1)) AS [Share %]
FROM    RoomTypes rt
JOIN    Rooms     r ON r.RoomTypeID = rt.RoomTypeID
JOIN    Bookings  b ON b.RoomID     = r.RoomID
WHERE   b.Status IN ('CheckedOut', 'CheckedIn')
GROUP BY rt.TypeName
ORDER BY RoomRevenue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R03. Top 10 guests by lifetime value (room + services), ranked
   --------------------------------------------------------------------- */
WITH GuestValue AS (
    SELECT  g.GuestID,
            CONCAT(g.FirstName, ' ', g.LastName)  AS Guest,
            g.City, g.VIPTier,
            COUNT(b.BookingID)              AS Stays,
            SUM(b.RoomCharge)               AS RoomSpend,
            SUM(ISNULL(s.ServiceSpend, 0))  AS ServiceSpend
    FROM    Guests g
    JOIN    Bookings b ON b.GuestID = g.GuestID AND b.Status IN ('CheckedOut', 'CheckedIn')
    LEFT JOIN (SELECT BookingID, SUM(LineTotal) AS ServiceSpend
               FROM   ServiceUsage GROUP BY BookingID) s ON s.BookingID = b.BookingID
    GROUP BY g.GuestID, g.FirstName, g.LastName, g.City, g.VIPTier
)
SELECT TOP (10)
        RANK() OVER (ORDER BY RoomSpend + ServiceSpend DESC) AS [Rank],
        Guest, City, VIPTier, Stays,
        RoomSpend, ServiceSpend,
        RoomSpend + ServiceSpend AS LifetimeValue_PKR
FROM    GuestValue
ORDER BY LifetimeValue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R04. Service revenue by category - only categories above PKR 1 million (HAVING)
   --------------------------------------------------------------------- */
SELECT  sv.Category,
        COUNT(*)                                   AS TimesUsed,
        SUM(u.Quantity)                            AS UnitsSold,
        SUM(u.LineTotal)                           AS Revenue_PKR,
        CAST(AVG(u.LineTotal) AS DECIMAL(10,0))    AS AvgTicket_PKR,
        MIN(u.UsageDate)                           AS FirstSale,
        MAX(u.UsageDate)                           AS LastSale
FROM    ServiceUsage u
JOIN    Services sv ON sv.ServiceID = u.ServiceID
GROUP BY sv.Category
HAVING  SUM(u.LineTotal) > 1000000
ORDER BY Revenue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R05. Booking channel performance: volume, cancellations, lead time
   --------------------------------------------------------------------- */
SELECT  Channel,
        COUNT(*)                                                                     AS Bookings,
        SUM(CASE WHEN Status IN ('Cancelled', 'NoShow') THEN 1 ELSE 0 END)            AS Lost,
        CAST(100.0 * SUM(CASE WHEN Status IN ('Cancelled', 'NoShow') THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,1)) AS [Lost %],
        AVG(DATEDIFF(DAY, BookingDate, CheckInDate))                                 AS AvgLeadDays,
        CAST(AVG(RatePerNight) AS DECIMAL(10,0))                                     AS AvgRate_PKR
FROM    Bookings
GROUP BY Channel
ORDER BY Bookings DESC;
GO

/* ---------------------------------------------------------------------
   R06. Loyal guests: stayed 12 or more times in 2026 (GROUP BY + HAVING)
   --------------------------------------------------------------------- */
SELECT  CONCAT(g.FirstName, ' ', g.LastName) AS Guest,
        g.City, g.VIPTier,
        COUNT(*)                        AS Stays,
        SUM(b.Nights)                   AS TotalNights,
        MIN(b.CheckInDate)              AS FirstStay,
        MAX(b.CheckInDate)              AS LatestStay
FROM    Guests g
JOIN    Bookings b ON b.GuestID = g.GuestID
WHERE   b.Status IN ('CheckedOut', 'CheckedIn')
  AND   YEAR(b.CheckInDate) = 2026
GROUP BY g.FirstName, g.LastName, g.City, g.VIPTier
HAVING  COUNT(*) >= 12
ORDER BY Stays DESC, TotalNights DESC;
GO

/* ---------------------------------------------------------------------
   R07. Outstanding balances: guests who checked out but have not paid in full
        (correlated subqueries for services and payments)
   --------------------------------------------------------------------- */
SELECT  b.BookingID,
        CONCAT(g.FirstName, ' ', g.LastName) AS Guest,
        b.Channel,
        b.CheckOutDate,
        b.RoomCharge + ISNULL((SELECT SUM(u.LineTotal) FROM ServiceUsage u WHERE u.BookingID = b.BookingID), 0) AS BillTotal,
        ISNULL((SELECT SUM(CASE WHEN p.PaymentType = 'Refund' THEN -p.Amount ELSE p.Amount END)
                FROM Payments p WHERE p.BookingID = b.BookingID), 0)                                         AS Paid,
        b.RoomCharge
          + ISNULL((SELECT SUM(u.LineTotal) FROM ServiceUsage u WHERE u.BookingID = b.BookingID), 0)
          - ISNULL((SELECT SUM(CASE WHEN p.PaymentType = 'Refund' THEN -p.Amount ELSE p.Amount END)
                    FROM Payments p WHERE p.BookingID = b.BookingID), 0)                                     AS BalanceDue
FROM    Bookings b
JOIN    Guests g ON g.GuestID = b.GuestID
WHERE   b.Status = 'CheckedOut'
  AND   b.RoomCharge
          + ISNULL((SELECT SUM(u.LineTotal) FROM ServiceUsage u WHERE u.BookingID = b.BookingID), 0)
        > ISNULL((SELECT SUM(CASE WHEN p.PaymentType = 'Refund' THEN -p.Amount ELSE p.Amount END)
                  FROM Payments p WHERE p.BookingID = b.BookingID), 0)
ORDER BY BalanceDue DESC;
GO

/* ---------------------------------------------------------------------
   R08. Under-performing rooms: room revenue below the average of their own room type
        (subquery in HAVING)
   --------------------------------------------------------------------- */
SELECT  r.RoomNumber, rt.TypeName, r.ViewType, r.FloorNo,
        COUNT(b.BookingID)  AS Stays,
        SUM(b.RoomCharge)   AS Revenue_PKR
FROM    Rooms r
JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
JOIN    Bookings  b  ON b.RoomID = r.RoomID AND b.Status IN ('CheckedOut', 'CheckedIn')
GROUP BY r.RoomID, r.RoomNumber, rt.TypeName, r.ViewType, r.FloorNo, r.RoomTypeID
HAVING  SUM(b.RoomCharge) < (
            SELECT AVG(RoomRevenue)
            FROM  (SELECT b2.RoomID, SUM(b2.RoomCharge) AS RoomRevenue
                   FROM   Bookings b2
                   JOIN   Rooms r2 ON r2.RoomID = b2.RoomID
                   WHERE  b2.Status IN ('CheckedOut', 'CheckedIn')
                     AND  r2.RoomTypeID = r.RoomTypeID
                   GROUP BY b2.RoomID) AS PerRoom)
ORDER BY rt.TypeName, Revenue_PKR;
GO

/* ---------------------------------------------------------------------
   R09. Where do our guests come from? Stay length and spend by nationality
   --------------------------------------------------------------------- */
SELECT  g.Nationality,
        COUNT(DISTINCT g.GuestID)                       AS Guests,
        COUNT(b.BookingID)                              AS Stays,
        CAST(AVG(CAST(b.Nights AS DECIMAL(5,2))) AS DECIMAL(4,1)) AS AvgNights,
        CAST(AVG(b.RatePerNight) AS DECIMAL(10,0))      AS AvgRate_PKR,
        SUM(b.RoomCharge)                               AS RoomRevenue_PKR
FROM    Guests g
JOIN    Bookings b ON b.GuestID = g.GuestID
WHERE   b.Status IN ('CheckedOut', 'CheckedIn')
GROUP BY g.Nationality
ORDER BY RoomRevenue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R10. Staff leaderboard: bookings taken by each front-office employee
        and the service revenue each employee delivered (LEFT JOIN keeps everyone)
   --------------------------------------------------------------------- */
SELECT  s.FullName, s.Role, s.IsActive,
        ISNULL(bk.BookingsTaken, 0)   AS BookingsTaken,
        ISNULL(bk.RoomRevenue, 0)     AS RoomRevenueBooked_PKR,
        ISNULL(sv.ServicesDone, 0)    AS ServicesDelivered,
        ISNULL(sv.ServiceRevenue, 0)  AS ServiceRevenue_PKR
FROM    Staff s
LEFT JOIN (SELECT StaffID, COUNT(*) AS BookingsTaken, SUM(RoomCharge) AS RoomRevenue
           FROM   Bookings WHERE Status <> 'Cancelled' GROUP BY StaffID) bk ON bk.StaffID = s.StaffID
LEFT JOIN (SELECT StaffID, COUNT(*) AS ServicesDone, SUM(LineTotal) AS ServiceRevenue
           FROM   ServiceUsage GROUP BY StaffID) sv ON sv.StaffID = s.StaffID
WHERE   s.Role <> 'Manager'
ORDER BY BookingsTaken DESC, ServiceRevenue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R11. Seasonality: Ramadan, Eid, Independence Day and December vs normal days
        (date filtering with BETWEEN inside CASE)
   --------------------------------------------------------------------- */
SELECT  Season,
        COUNT(*)                                   AS Stays,
        CAST(AVG(RatePerNight) AS DECIMAL(10,0))   AS AvgRate_PKR,
        CAST(AVG(CAST(Nights AS DECIMAL(5,2))) AS DECIMAL(4,1)) AS AvgNights,
        SUM(RoomCharge)                            AS RoomRevenue_PKR
FROM (
    SELECT  b.*,
            CASE
                WHEN b.CheckInDate BETWEEN '2026-02-18' AND '2026-03-19' THEN '1. Ramadan'
                WHEN b.CheckInDate BETWEEN '2026-03-20' AND '2026-03-24'
                  OR b.CheckInDate BETWEEN '2026-05-26' AND '2026-05-31' THEN '2. Eid holidays'
                WHEN b.CheckInDate BETWEEN '2026-08-12' AND '2026-08-15' THEN '3. Independence Day'
                WHEN MONTH(b.CheckInDate) = 12                          THEN '4. December peak'
                ELSE '5. Normal days'
            END AS Season
    FROM    Bookings b
    WHERE   b.Status <> 'Cancelled'
) AS x
GROUP BY Season
ORDER BY Season;
GO

/* ---------------------------------------------------------------------
   R12. Front-desk sheet for today: arrivals and departures (date filtering)
   --------------------------------------------------------------------- */
DECLARE @Today DATE = '2026-11-25';

SELECT  'Arrival'   AS Movement, b.BookingID, CONCAT(g.FirstName, ' ', g.LastName) AS Guest, g.VIPTier,
        r.RoomNumber, rt.TypeName, b.Nights, b.Status
FROM    Bookings b
JOIN    Guests g     ON g.GuestID = b.GuestID
JOIN    Rooms r      ON r.RoomID  = b.RoomID
JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
WHERE   b.CheckInDate = @Today AND b.Status NOT IN ('Cancelled', 'NoShow')
UNION ALL
SELECT  'Departure', b.BookingID, CONCAT(g.FirstName, ' ', g.LastName), g.VIPTier,
        r.RoomNumber, rt.TypeName, b.Nights, b.Status
FROM    Bookings b
JOIN    Guests g     ON g.GuestID = b.GuestID
JOIN    Rooms r      ON r.RoomID  = b.RoomID
JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
WHERE   b.CheckOutDate = @Today AND b.Status NOT IN ('Cancelled', 'NoShow')
ORDER BY Movement, RoomNumber;
GO

/* ---------------------------------------------------------------------
   R13. Best-selling service for each room type (ROW_NUMBER window function)
   --------------------------------------------------------------------- */
WITH Ranked AS (
    SELECT  rt.TypeName, sv.ServiceName,
            SUM(u.LineTotal) AS Revenue_PKR,
            COUNT(*)         AS TimesUsed,
            ROW_NUMBER() OVER (PARTITION BY rt.TypeName ORDER BY SUM(u.LineTotal) DESC) AS rn
    FROM    ServiceUsage u
    JOIN    Services  sv ON sv.ServiceID = u.ServiceID
    JOIN    Bookings  b  ON b.BookingID  = u.BookingID
    JOIN    Rooms     r  ON r.RoomID     = b.RoomID
    JOIN    RoomTypes rt ON rt.RoomTypeID = r.RoomTypeID
    GROUP BY rt.TypeName, sv.ServiceName
)
SELECT  TypeName, ServiceName AS TopService, TimesUsed, Revenue_PKR
FROM    Ranked
WHERE   rn = 1
ORDER BY Revenue_PKR DESC;
GO

/* ---------------------------------------------------------------------
   R14. Month-over-month revenue growth and running total (LAG + SUM OVER)
        Revenue = room charges by check-in month + services by usage month
   --------------------------------------------------------------------- */
WITH Monthly AS (
    SELECT MonthStart, SUM(Amount) AS Revenue
    FROM (
        SELECT DATEFROMPARTS(YEAR(CheckInDate), MONTH(CheckInDate), 1) AS MonthStart, RoomCharge AS Amount
        FROM   Bookings WHERE Status IN ('CheckedOut', 'CheckedIn')
        UNION ALL
        SELECT DATEFROMPARTS(YEAR(UsageDate), MONTH(UsageDate), 1), LineTotal
        FROM   ServiceUsage
    ) AS t
    GROUP BY MonthStart
)
SELECT  FORMAT(MonthStart, 'MMM yyyy')                                AS [Month],
        Revenue                                                       AS Revenue_PKR,
        LAG(Revenue) OVER (ORDER BY MonthStart)                       AS PrevMonth_PKR,
        CAST(100.0 * (Revenue - LAG(Revenue) OVER (ORDER BY MonthStart))
             / LAG(Revenue) OVER (ORDER BY MonthStart) AS DECIMAL(6,1)) AS [Growth %],
        SUM(Revenue) OVER (ORDER BY MonthStart ROWS UNBOUNDED PRECEDING) AS RunningTotal_PKR
FROM    Monthly
ORDER BY MonthStart;
GO

/* ---------------------------------------------------------------------
   R15. How guests pay: share of each payment method, and refunds issued
   --------------------------------------------------------------------- */
SELECT  Method,
        COUNT(*)                                                         AS Transactions,
        SUM(CASE WHEN PaymentType <> 'Refund' THEN Amount ELSE 0 END)    AS Received_PKR,
        SUM(CASE WHEN PaymentType =  'Refund' THEN Amount ELSE 0 END)    AS Refunded_PKR,
        CAST(100.0 * SUM(CASE WHEN PaymentType <> 'Refund' THEN Amount ELSE 0 END)
             / (SELECT SUM(Amount) FROM Payments WHERE PaymentType <> 'Refund') AS DECIMAL(5,1)) AS [Share %],
        MAX(Amount)                                                      AS LargestPayment_PKR
FROM    Payments
GROUP BY Method
ORDER BY Received_PKR DESC;
GO
