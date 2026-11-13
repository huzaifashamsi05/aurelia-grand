/* =====================================================================
   AURELIA GRAND, KARACHI  |  Hotel Booking and Guest Service System
   DBMS Group Project - Group 08 - 25F Data Science, DUET Karachi
   File 01 : Database and tables (DDL)
   Target  : Microsoft SQL Server 2019 / 2022 / 2025 (Express is fine)
   ===================================================================== */

USE master;
GO

/* Drop and recreate so the script can be run again and again */
IF DB_ID(N'AureliaGrand') IS NOT NULL
BEGIN
    ALTER DATABASE AureliaGrand SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE AureliaGrand;
END
GO

CREATE DATABASE AureliaGrand;
GO

USE AureliaGrand;
GO

/* ---------------------------------------------------------------------
   1. RoomTypes : the categories of room the hotel sells
   --------------------------------------------------------------------- */
CREATE TABLE RoomTypes (
    RoomTypeID     INT IDENTITY(1,1)  NOT NULL,
    TypeName       VARCHAR(40)        NOT NULL,
    BaseRate       DECIMAL(10,2)      NOT NULL,          -- PKR per night
    MaxOccupancy   TINYINT            NOT NULL,
    BedType        VARCHAR(20)        NOT NULL,
    SizeSqFt       SMALLINT           NOT NULL,
    Description    VARCHAR(200)       NULL,
    CONSTRAINT PK_RoomTypes           PRIMARY KEY (RoomTypeID),
    CONSTRAINT UQ_RoomTypes_Name      UNIQUE (TypeName),
    CONSTRAINT CK_RoomTypes_Rate      CHECK (BaseRate > 0),
    CONSTRAINT CK_RoomTypes_Occupancy CHECK (MaxOccupancy BETWEEN 1 AND 6),
    CONSTRAINT CK_RoomTypes_Bed       CHECK (BedType IN ('King', 'Twin', 'Queen')),
    CONSTRAINT CK_RoomTypes_Size      CHECK (SizeSqFt BETWEEN 200 AND 3000)
);
GO

/* ---------------------------------------------------------------------
   2. Rooms : every physical room in the building
   --------------------------------------------------------------------- */
CREATE TABLE Rooms (
    RoomID         INT IDENTITY(1,1)  NOT NULL,
    RoomNumber     VARCHAR(5)         NOT NULL,
    RoomTypeID     INT                NOT NULL,
    FloorNo        TINYINT            NOT NULL,
    ViewType       VARCHAR(10)        NOT NULL,
    Status         VARCHAR(12)        NOT NULL CONSTRAINT DF_Rooms_Status  DEFAULT ('Available'),
    IsSmoking      BIT                NOT NULL CONSTRAINT DF_Rooms_Smoking DEFAULT (0),
    CONSTRAINT PK_Rooms               PRIMARY KEY (RoomID),
    CONSTRAINT UQ_Rooms_Number        UNIQUE (RoomNumber),
    CONSTRAINT FK_Rooms_RoomTypes     FOREIGN KEY (RoomTypeID) REFERENCES RoomTypes (RoomTypeID),
    CONSTRAINT CK_Rooms_Floor         CHECK (FloorNo BETWEEN 1 AND 15),
    CONSTRAINT CK_Rooms_View          CHECK (ViewType IN ('Sea', 'City', 'Garden')),
    CONSTRAINT CK_Rooms_Status        CHECK (Status IN ('Available', 'Occupied', 'Cleaning', 'Maintenance'))
);
GO

/* ---------------------------------------------------------------------
   3. Guests : people who stay at the hotel
   --------------------------------------------------------------------- */
CREATE TABLE Guests (
    GuestID        INT IDENTITY(1,1)  NOT NULL,
    FirstName      VARCHAR(40)        NOT NULL,
    LastName       VARCHAR(40)        NOT NULL,
    Gender         CHAR(1)            NOT NULL,
    Email          VARCHAR(100)       NOT NULL,
    Phone          VARCHAR(20)        NOT NULL,
    IDDocument     VARCHAR(20)        NOT NULL,          -- CNIC for Pakistanis, passport for foreigners
    Nationality    VARCHAR(30)        NOT NULL CONSTRAINT DF_Guests_Nationality DEFAULT ('Pakistan'),
    City           VARCHAR(40)        NOT NULL,
    DateOfBirth    DATE               NOT NULL,
    VIPTier        VARCHAR(10)        NOT NULL CONSTRAINT DF_Guests_Tier      DEFAULT ('Silver'),
    CreatedAt      DATETIME2(0)       NOT NULL CONSTRAINT DF_Guests_Created   DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Guests              PRIMARY KEY (GuestID),
    CONSTRAINT UQ_Guests_Email        UNIQUE (Email),
    CONSTRAINT UQ_Guests_IDDocument   UNIQUE (IDDocument),
    CONSTRAINT CK_Guests_Gender       CHECK (Gender IN ('M', 'F')),
    CONSTRAINT CK_Guests_Email        CHECK (Email LIKE '%_@_%._%'),
    CONSTRAINT CK_Guests_Tier         CHECK (VIPTier IN ('Silver', 'Gold', 'Platinum')),
    CONSTRAINT CK_Guests_Age          CHECK (DateOfBirth <= DATEADD(YEAR, -18, CAST(CreatedAt AS DATE)))
);
GO

/* ---------------------------------------------------------------------
   4. Staff : employees who handle bookings and deliver services
   --------------------------------------------------------------------- */
CREATE TABLE Staff (
    StaffID        INT IDENTITY(1,1)  NOT NULL,
    FullName       VARCHAR(60)        NOT NULL,
    Role           VARCHAR(20)        NOT NULL,
    Email          VARCHAR(100)       NOT NULL,
    Phone          VARCHAR(20)        NOT NULL,
    HireDate       DATE               NOT NULL,
    MonthlySalary  DECIMAL(10,2)      NOT NULL,
    IsActive       BIT                NOT NULL CONSTRAINT DF_Staff_Active DEFAULT (1),
    CONSTRAINT PK_Staff               PRIMARY KEY (StaffID),
    CONSTRAINT UQ_Staff_Email         UNIQUE (Email),
    CONSTRAINT CK_Staff_Role          CHECK (Role IN ('Manager', 'Front Desk', 'Concierge', 'Chef', 'Spa Therapist', 'Housekeeping', 'Driver')),
    CONSTRAINT CK_Staff_Salary        CHECK (MonthlySalary BETWEEN 40000 AND 1000000)
);
GO

/* ---------------------------------------------------------------------
   5. Bookings : one row per room reservation
   --------------------------------------------------------------------- */
CREATE TABLE Bookings (
    BookingID      INT IDENTITY(1001,1) NOT NULL,
    GuestID        INT                NOT NULL,
    RoomID         INT                NOT NULL,
    StaffID        INT                NOT NULL,          -- front-desk agent who made the booking
    BookingDate    DATE               NOT NULL CONSTRAINT DF_Bookings_Date    DEFAULT (CAST(GETDATE() AS DATE)),
    CheckInDate    DATE               NOT NULL,
    CheckOutDate   DATE               NOT NULL,
    Adults         TINYINT            NOT NULL CONSTRAINT DF_Bookings_Adults  DEFAULT (1),
    Children       TINYINT            NOT NULL CONSTRAINT DF_Bookings_Kids    DEFAULT (0),
    Channel        VARCHAR(15)        NOT NULL,
    RatePerNight   DECIMAL(10,2)      NOT NULL,
    Status         VARCHAR(12)        NOT NULL CONSTRAINT DF_Bookings_Status  DEFAULT ('Confirmed'),
    Nights         AS DATEDIFF(DAY, CheckInDate, CheckOutDate) PERSISTED,
    RoomCharge     AS CAST(DATEDIFF(DAY, CheckInDate, CheckOutDate) * RatePerNight AS DECIMAL(12,2)) PERSISTED,
    CONSTRAINT PK_Bookings            PRIMARY KEY (BookingID),
    CONSTRAINT FK_Bookings_Guests     FOREIGN KEY (GuestID) REFERENCES Guests (GuestID),
    CONSTRAINT FK_Bookings_Rooms      FOREIGN KEY (RoomID)  REFERENCES Rooms (RoomID),
    CONSTRAINT FK_Bookings_Staff      FOREIGN KEY (StaffID) REFERENCES Staff (StaffID),
    CONSTRAINT CK_Bookings_Dates      CHECK (CheckOutDate > CheckInDate),
    CONSTRAINT CK_Bookings_Lead       CHECK (BookingDate <= CheckInDate),
    CONSTRAINT CK_Bookings_Adults     CHECK (Adults BETWEEN 1 AND 6),
    CONSTRAINT CK_Bookings_Children   CHECK (Children BETWEEN 0 AND 4),
    CONSTRAINT CK_Bookings_Channel    CHECK (Channel IN ('Website', 'Walk-in', 'Phone', 'Booking.com', 'Corporate')),
    CONSTRAINT CK_Bookings_Rate       CHECK (RatePerNight > 0),
    CONSTRAINT CK_Bookings_Status     CHECK (Status IN ('Confirmed', 'CheckedIn', 'CheckedOut', 'Cancelled', 'NoShow'))
);
GO

/* ---------------------------------------------------------------------
   6. Services : extras a guest can buy during the stay
   --------------------------------------------------------------------- */
CREATE TABLE Services (
    ServiceID      INT IDENTITY(1,1)  NOT NULL,
    ServiceName    VARCHAR(50)        NOT NULL,
    Category       VARCHAR(15)        NOT NULL,
    Price          DECIMAL(10,2)      NOT NULL,
    IsAvailable    BIT                NOT NULL CONSTRAINT DF_Services_Available DEFAULT (1),
    CONSTRAINT PK_Services            PRIMARY KEY (ServiceID),
    CONSTRAINT UQ_Services_Name       UNIQUE (ServiceName),
    CONSTRAINT CK_Services_Category   CHECK (Category IN ('Dining', 'Spa', 'Laundry', 'Transport', 'Room Service', 'Recreation')),
    CONSTRAINT CK_Services_Price      CHECK (Price > 0)
);
GO

/* ---------------------------------------------------------------------
   7. ServiceUsage : which guest (booking) used which service, and when
      (resolves the many-to-many between Bookings and Services)
   --------------------------------------------------------------------- */
CREATE TABLE ServiceUsage (
    UsageID        INT IDENTITY(1,1)  NOT NULL,
    BookingID      INT                NOT NULL,
    ServiceID      INT                NOT NULL,
    StaffID        INT                NULL,              -- who delivered it (optional)
    UsageDate      DATE               NOT NULL CONSTRAINT DF_Usage_Date DEFAULT (CAST(GETDATE() AS DATE)),
    Quantity       TINYINT            NOT NULL CONSTRAINT DF_Usage_Qty  DEFAULT (1),
    UnitPrice      DECIMAL(10,2)      NOT NULL,          -- price at the time of use
    LineTotal      AS CAST(Quantity * UnitPrice AS DECIMAL(12,2)) PERSISTED,
    CONSTRAINT PK_ServiceUsage        PRIMARY KEY (UsageID),
    CONSTRAINT FK_Usage_Bookings      FOREIGN KEY (BookingID) REFERENCES Bookings (BookingID),
    CONSTRAINT FK_Usage_Services      FOREIGN KEY (ServiceID) REFERENCES Services (ServiceID),
    CONSTRAINT FK_Usage_Staff         FOREIGN KEY (StaffID)   REFERENCES Staff (StaffID),
    CONSTRAINT CK_Usage_Qty           CHECK (Quantity BETWEEN 1 AND 20),
    CONSTRAINT CK_Usage_Price         CHECK (UnitPrice > 0)
);
GO

/* ---------------------------------------------------------------------
   8. Payments : money received against a booking (or refunded)
   --------------------------------------------------------------------- */
CREATE TABLE Payments (
    PaymentID      INT IDENTITY(1,1)  NOT NULL,
    BookingID      INT                NOT NULL,
    PaymentDate    DATE               NOT NULL CONSTRAINT DF_Payments_Date DEFAULT (CAST(GETDATE() AS DATE)),
    Amount         DECIMAL(12,2)      NOT NULL,
    Method         VARCHAR(15)        NOT NULL,
    PaymentType    VARCHAR(10)        NOT NULL,
    TransactionRef VARCHAR(20)        NOT NULL,
    CONSTRAINT PK_Payments            PRIMARY KEY (PaymentID),
    CONSTRAINT FK_Payments_Bookings   FOREIGN KEY (BookingID) REFERENCES Bookings (BookingID),
    CONSTRAINT UQ_Payments_Ref        UNIQUE (TransactionRef),
    CONSTRAINT CK_Payments_Amount     CHECK (Amount > 0),
    CONSTRAINT CK_Payments_Method     CHECK (Method IN ('Cash', 'Card', 'Bank Transfer', 'JazzCash', 'Easypaisa')),
    CONSTRAINT CK_Payments_Type       CHECK (PaymentType IN ('Deposit', 'Settlement', 'Refund'))
);
GO

PRINT 'AureliaGrand: 8 tables created.';
GO
