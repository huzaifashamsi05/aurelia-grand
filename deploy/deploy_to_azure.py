"""Load the AureliaGrand database into Azure SQL Database (one time).

Run deploy_to_azure.bat (it uses the app's Python). You will be asked for the Azure
server name, the admin login and the password you chose in the Azure portal.
Nothing is saved to disk.
"""
import getpass, re, sys, time
from pathlib import Path
import pyodbc

# Streamlit Community Cloud outbound IPs (docs.streamlit.io/deploy/streamlit-community-cloud/status)
STREAMLIT_IPS = ["35.230.127.150", "35.203.151.101", "34.19.100.134", "34.83.176.217", "35.230.58.211",
                 "35.203.187.165", "35.185.209.55", "34.127.88.74", "34.127.0.121", "35.230.78.192",
                 "35.247.110.67", "35.197.92.111", "34.168.247.159", "35.230.56.30", "34.127.33.101",
                 "35.227.190.87", "35.199.156.97", "34.82.135.155"]

SCRIPT = Path(__file__).resolve().parent.parent / "sql" / "00_BUILD_AZURE.sql"

def driver():
    for d in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if d in pyodbc.drivers():
            return d
    sys.exit("ODBC Driver 18 for SQL Server is not installed.")

def main():
    print("\n=== Aurelia Grand -> Azure SQL Database ===\n")
    server = input("Azure server name [aureliagrand-g08.database.windows.net]: ").strip() or "aureliagrand-g08.database.windows.net"
    if "." not in server:
        server += ".database.windows.net"
    user = input("Admin login [aureliaadmin]: ").strip() or "aureliaadmin"
    pwd = getpass.getpass("Password (hidden while typing): ")
    cs = (f"DRIVER={{{driver()}}};SERVER=tcp:{server},1433;DATABASE=AureliaGrand;UID={{{user}}};PWD={{{pwd}}};"
          "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    for attempt in range(6):
        try:
            conn = pyodbc.connect(cs, autocommit=True)
            break
        except pyodbc.Error as e:
            msg = str(e)
            if "40613" in msg or "timeout" in msg.lower():
                print("Database is waking up, retrying in 15 s ...")
                time.sleep(15)
                continue
            sys.exit(f"\nCould not connect:\n{msg}\n")
    else:
        sys.exit("Could not connect after several tries.")
    batches = [b.strip() for b in re.split(r"^\s*GO\s*$", SCRIPT.read_text(encoding="utf-8"), flags=re.M | re.I) if b.strip()]
    cur = conn.cursor()
    t0 = time.time()
    for i, b in enumerate(batches, 1):
        try:
            cur.execute(b)
            while cur.nextset():
                pass
        except pyodbc.Error as e:
            sys.exit(f"\nBatch {i} failed:\n{e}\n\n{b[:400]}")
        print(f"\r  {i}/{len(batches)} batches done", end="", flush=True)
    print(f"\n\nDone in {time.time()-t0:.0f} s.")
    for t in ("RoomTypes", "Rooms", "Guests", "Staff", "Services", "Bookings", "ServiceUsage", "Payments"):
        print(f"  {t:13s} {cur.execute(f'SELECT COUNT(*) FROM dbo.{t}').fetchone()[0]:>6,} rows")
    # Allow only Streamlit Community Cloud's published outbound IPs (database-level firewall rules).
    for k, ip in enumerate(STREAMLIT_IPS, 1):
        # constants from the list above (not user input), so literal SQL is safe here
        cur.execute(f"EXEC sp_set_database_firewall_rule @name = N'StreamlitCloud-{k:02d}', "
                    f"@start_ip_address = '{ip}', @end_ip_address = '{ip}';")
    print(f"  firewall: {len(STREAMLIT_IPS)} Streamlit Cloud IP rules added")
    n = cur.execute("SELECT COUNT(*) FROM sys.objects WHERE type IN ('V','P','TR','FN','IF')").fetchone()[0]
    print(f"  views + procedures + triggers + functions: {n}")
    conn.close()

if __name__ == "__main__":
    main()
