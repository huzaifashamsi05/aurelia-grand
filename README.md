# Aurelia Grand · Command Center

**Hotel Booking and Guest Service System** — DBMS Group Project, Group 08, Department of Data Science, DUET Karachi (Batch 25/F, Section C).

| Roll No. | Name |
|---|---|
| 25F-DS-106 | Muhammad Abdul Rehman Khan |
| 25F-DS-135 | Muhammad Huzaifa Shamsi |
| 25F-DS-140 | Basit Mirza |
| 25F-DS-152 | Muhammad Hashir |
| 25F-DS-155 | Saif Ul Wahab |

A luxury hotel operations app built on a **Microsoft SQL Server** database (8 tables, 15 reports, 3 views, 3 functions, 6 stored procedures, 4 triggers). Every change in the app runs through the database's stored procedures, so transactions, triggers and constraints protect the data.

## Screens
Lobby (KPIs: Occupancy, ADR, RevPAR) · Front Desk (search, book, check-in, services, check-out) · Live Room Map · Guests · Revenue & Analytics (15 reports) · SQL Lab (every project query, runnable) · About.

## Database files (`sql/`)
| File | Purpose |
|---|---|
| `01_schema.sql` | CREATE DATABASE and 8 tables with all constraints |
| `03_data_operations.sql` | CRUD and constraint demos |
| `04_reporting_queries.sql` | 15 management reports |
| `05_advanced_objects.sql` | Indexes, functions, views, triggers, stored procedures |
| `06_advanced_demo.sql` | A complete guest journey using every advanced object |

ER diagram: [dbdiagram.io](https://dbdiagram.io/d/Aurelia-Grand-Hotel-Booking-System-DBMS-Group-08-6af692f64e0bad65989e1259) and `erd/`.

## Run locally (Windows, SQL Server Express)
1. Build the database in SSMS with `00_BUILD_ALL.sql`.
2. `pip install -r requirements.txt`
3. `streamlit run app.py` (Windows Authentication to `localhost\SQLEXPRESS` by default).

## Cloud
The live version runs on Streamlit Community Cloud with an Azure SQL Database (free tier). Connection details are kept in Streamlit secrets, never in this repository. The free database pauses when idle, so the first page load after a break can take up to a minute.
