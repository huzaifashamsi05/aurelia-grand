"""Database access for the whole app (SQLAlchemy engine + pyodbc cursors).

Rules this module enforces:
  * every statement is parameterised (``?`` markers), SQL is never built from user text;
  * reads are cached and never commit;
  * writes happen only through stored procedures (see ``core/procs.py``) and commit;
  * SQL Server errors are turned into a clean ``DatabaseError`` so the UI can show
    ``ERROR_MESSAGE()`` text instead of a Python traceback.
"""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

import pandas as pd
import pyodbc
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

from . import config

log = logging.getLogger("aurelia.db")

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

# Which database object raises each custom error number (THROW 50001-50050).
ERROR_SOURCES = {
    50001: "Trigger trg_Bookings_NoDoubleBooking",
    50002: "Trigger trg_Bookings_SoftDelete",
    50010: "Procedure sp_SearchAvailableRooms",
    50020: "Procedure sp_CreateBooking",
    50021: "Procedure sp_CreateBooking",
    50022: "Procedure sp_CreateBooking",
    50030: "Procedure sp_CheckIn",
    50031: "Procedure sp_CheckIn",
    50032: "Procedure sp_CheckIn",
    50040: "Procedure sp_AddService",
    50041: "Procedure sp_AddService",
    50050: "Procedure sp_CheckOut",
}

# Plain-language text for constraint violations (the raw text is kept as detail).
CONSTRAINT_MESSAGES = {
    "CK_Bookings_Dates": "Check-out must be after check-in.",
    "CK_Bookings_Lead": "The check-in date cannot be earlier than the booking date.",
    "CK_Bookings_Adults": "A booking needs between 1 and 6 adults.",
    "CK_Bookings_Children": "A booking can have at most 4 children.",
    "CK_Bookings_Channel": "This booking channel is not recognised.",
    "CK_Bookings_Rate": "The nightly rate must be greater than zero.",
    "CK_Payments_Method": "This payment method is not accepted. Use Cash, Card, Bank Transfer, JazzCash or Easypaisa.",
    "CK_Payments_Amount": "A payment amount must be greater than zero.",
    "CK_Usage_Qty": "Quantity must be between 1 and 20.",
    "FK_Bookings_Guests": "This guest does not exist (or still has bookings and cannot be removed).",
    "FK_Bookings_Rooms": "This room does not exist.",
    "FK_Bookings_Staff": "This staff member does not exist.",
    "FK_Usage_Staff": "This staff member does not exist.",
    "FK_Usage_Services": "This service does not exist.",
    "UQ_Guests_Email": "Another guest already uses this email address.",
    "UQ_Guests_IDDocument": "Another guest already uses this CNIC / passport number.",
    "UQ_Payments_Ref": "A payment with this transaction reference already exists.",
}

_SQLSERVER_MESSAGE = re.compile(
    r"\[SQL Server\](?P<msg>.*?)\s*\((?P<num>\d+)\)\s*\(SQL[A-Za-z]+\)", re.S
)
_CONSTRAINT_NAME = re.compile(r"""constraint\s+["'](?P<name>[A-Za-z0-9_]+)["']""", re.I)
_DRIVER_PREFIX = re.compile(r"^(\[[^\]]*\])+")
_CONNECTION_STATES = {"08001", "08S01", "08004", "HYT00", "HYT01", "28000", "IM002", "IM003"}


class DatabaseError(Exception):
    """A database problem with a message that is safe to show to the user."""

    def __init__(
        self,
        message: str,
        *,
        number: int | None = None,
        detail: str | None = None,
        constraint: str | None = None,
        kind: str = "error",
    ):
        super().__init__(message)
        self.message = message
        self.number = number
        self.detail = detail
        self.constraint = constraint
        self.kind = kind  # "rule" | "constraint" | "connection" | "error"

    @property
    def source(self) -> str | None:
        """Which database object said no, e.g. 'Procedure sp_CheckIn'."""
        if self.number in ERROR_SOURCES:
            return ERROR_SOURCES[self.number]
        if self.constraint:
            return f"Constraint {self.constraint}"
        return None

    @property
    def is_double_booking(self) -> bool:
        return self.number in (50001, 50022)


def translate_error(exc: BaseException) -> DatabaseError:
    """Turn a pyodbc / SQLAlchemy exception into a clean DatabaseError."""
    if isinstance(exc, DatabaseError):
        return exc

    original = getattr(exc, "orig", None) or exc
    args = getattr(original, "args", ()) or ()
    sqlstate = str(args[0]) if args else ""
    raw = str(args[1]) if len(args) > 1 else str(original)

    match = _SQLSERVER_MESSAGE.search(raw)
    if match:
        message, number = match["msg"].strip(), int(match["num"])
    else:
        message, number = _DRIVER_PREFIX.sub("", raw).strip(), None

    is_connection = sqlstate in _CONNECTION_STATES or (
        isinstance(original, (pyodbc.OperationalError, pyodbc.InterfaceError)) and not match
    )
    if is_connection or number in (4060, 18456, 53, 2, 17):
        settings = config.db_settings()
        return DatabaseError(
            f"Cannot reach the hotel database ({settings['server']} / {settings['database']}).",
            number=number,
            detail=message,
            kind="connection",
        )

    if number is not None and 50000 <= number <= 50999:
        return DatabaseError(message, number=number, kind="rule")

    constraint_match = _CONSTRAINT_NAME.search(message)
    if constraint_match:
        name = constraint_match["name"]
        friendly = CONSTRAINT_MESSAGES.get(name, f"The database rejected this change (rule {name}).")
        return DatabaseError(friendly, number=number, detail=message, constraint=name, kind="constraint")

    return DatabaseError(message or "The database reported an error.", number=number, kind="error")


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

_DRIVER_PREFERENCE = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
    "FreeTDS",
)

# Streamlit Community Cloud (Debian) has no Microsoft driver; packages.txt installs FreeTDS.
_FREETDS_PATHS = (
    "/usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so",
    "/usr/lib/aarch64-linux-gnu/odbc/libtdsodbc.so",
    "/usr/lib/odbc/libtdsodbc.so",
)


def pick_driver(preferred: str | None = "auto") -> str:
    import os
    installed = pyodbc.drivers()
    if preferred and preferred != "auto" and preferred in installed:
        return preferred
    for name in _DRIVER_PREFERENCE:
        if name in installed:
            return name
    for path in _FREETDS_PATHS:
        if os.path.exists(path):
            return path
    raise DatabaseError(
        "No SQL Server ODBC driver is installed on this computer.",
        detail="Install 'ODBC Driver 18 for SQL Server' from Microsoft, then restart the app.",
        kind="connection",
    )


def _odbc_value(value: str) -> str:
    """Brace-quote a value so characters such as ';' are safe in a connection string."""
    return "{" + str(value).replace("}", "}}") + "}"


def connection_string() -> str:
    s = config.db_settings()
    driver = pick_driver(s["driver"])
    if "tds" in driver.lower():
        # FreeTDS (Linux cloud): host and port are separate, TLS is required by Azure SQL.
        host = str(s["server"]).replace("tcp:", "").split(",")[0]
        port = str(s["server"]).split(",")[1] if "," in str(s["server"]) else "1433"
        parts = [
            f"DRIVER={{{driver}}}" if not driver.startswith("/") else f"DRIVER={driver}",
            f"SERVER={host}",
            f"PORT={port}",
            f"DATABASE={s['database']}",
            "TDS_Version=7.4",
            "Encryption=require",
            "ClientCharset=UTF-8",
            f"UID={_odbc_value(s['username'] or '')}",
            f"PWD={_odbc_value(s['password'] or '')}",
        ]
        return ";".join(parts) + ";"
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={s['server']}",
        f"DATABASE={s['database']}",
        "APP=Aurelia Grand Command Center",
    ]
    if s["username"]:
        parts += [f"UID={_odbc_value(s['username'])}", f"PWD={_odbc_value(s['password'] or '')}"]
    else:
        parts.append("Trusted_Connection=yes")
    if "ODBC Driver" in driver:
        parts.append("Encrypt=yes")
        parts.append(f"TrustServerCertificate={'yes' if s['trust_server_certificate'] else 'no'}")
    return ";".join(parts) + ";"


def _is_cloud() -> bool:
    return bool(config.db_settings()["username"])


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string()})
    # timeout = seconds to wait for a login. Locally an offline server fails fast;
    # in the cloud an auto-paused Azure SQL free database needs up to a minute to wake up.
    timeout = 45 if _is_cloud() else 5
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800, connect_args={"timeout": timeout})


# Azure SQL errors that mean "the database is waking up / busy, try again".
_TRANSIENT_NUMBERS = (40613, 40501, 40197, 49918, 49919, 49920, 4060, 233, 10053, 10054, 10060)


def _raw_connection_with_retry():
    import time
    last = None
    for attempt in range(6):
        try:
            return get_engine().raw_connection()
        except Exception as exc:  # paused database: retry for about a minute
            last = exc
            text = str(getattr(exc, "orig", exc))
            if not _is_cloud() or not any(str(n) in text for n in _TRANSIENT_NUMBERS) and "timeout" not in text.lower():
                break
            time.sleep(min(5 + attempt * 5, 15))
    raise last


@contextmanager
def _connection(autocommit: bool = False):
    """A raw pyodbc connection from the pool. Always rolled back unless committed."""
    try:
        proxy = _raw_connection_with_retry()
    except DatabaseError:
        raise
    except Exception as exc:  # cannot connect
        raise translate_error(exc) from None
    raw = proxy.driver_connection
    try:
        raw.autocommit = autocommit
        yield raw
    finally:
        try:
            if not autocommit:
                raw.rollback()
            raw.autocommit = False
        except Exception:  # connection already broken
            pass
        proxy.close()


# --------------------------------------------------------------------------
# Result handling
# --------------------------------------------------------------------------

def _clean_message(text: str) -> str:
    return _DRIVER_PREFIX.sub("", str(text)).strip()


def _to_frame(columns: Sequence[str], rows: Sequence) -> pd.DataFrame:
    names, seen = [], {}
    for position, column in enumerate(columns, start=1):
        name = column or f"Column{position}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        names.append(name)

    frame = pd.DataFrame.from_records([tuple(row) for row in rows], columns=names)
    for name in frame.columns:
        if frame[name].dtype == object:
            sample = next((v for v in frame[name] if v is not None), None)
            if isinstance(sample, Decimal):  # DECIMAL / MONEY columns -> float for charts
                frame[name] = frame[name].map(lambda v: float(v) if v is not None else None)
    return frame


def _collect_messages(cursor, messages: list[str]) -> None:
    for _, text in getattr(cursor, "messages", None) or []:
        cleaned = _clean_message(text)
        if cleaned:
            messages.append(cleaned)


def _drain(cursor, frames: list[pd.DataFrame], messages: list[str]) -> None:
    """Read every result set. Errors raised later in a batch surface here."""
    while True:
        _collect_messages(cursor, messages)
        if cursor.description is not None:
            columns = [c[0] for c in cursor.description]
            frames.append(_to_frame(columns, cursor.fetchall()))
        elif cursor.rowcount is not None and cursor.rowcount >= 0:
            plural = "" if cursor.rowcount == 1 else "s"
            messages.append(f"({cursor.rowcount} row{plural} affected)")
        if not cursor.nextset():
            break
    _collect_messages(cursor, messages)


@dataclass
class Result:
    """Everything a batch returned: result sets, PRINT/info messages, and an error if any."""

    frames: list[pd.DataFrame] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    error: DatabaseError | None = None

    @property
    def first(self) -> pd.DataFrame:
        return self.frames[0] if self.frames else pd.DataFrame()

    def row(self, index: int = 0) -> dict:
        """First row of result set ``index`` as a dict (empty dict if there is none)."""
        if index >= len(self.frames) or self.frames[index].empty:
            return {}
        return self.frames[index].iloc[0].to_dict()


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def fetch(sql: str, params: Sequence = ()) -> pd.DataFrame:
    """Run a read-only statement and return its (first) result set. Not cached."""
    result = Result()
    with _connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, tuple(params))
            _drain(cursor, result.frames, result.messages)
        except pyodbc.Error as exc:
            raise translate_error(exc) from None
        finally:
            cursor.close()
    return result.first


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def read(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Cached read. The cache is cleared after every write."""
    return fetch(sql, params)


def clear_cache() -> None:
    st.cache_data.clear()


def execute_procedure(sql: str, params: Sequence = ()) -> Result:
    """Run an ``EXEC dbo.sp_...`` batch, commit it, and clear the read cache.

    This is the only function in the app that commits changes, and it is only
    called from ``core/procs.py`` with a fixed EXEC statement.
    """
    result = Result()
    with _connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, tuple(params))
            _drain(cursor, result.frames, result.messages)
            conn.commit()
        except pyodbc.Error as exc:
            conn.rollback()
            raise translate_error(exc) from None
        finally:
            cursor.close()
            clear_cache()
    return result


def run_script(sql: str, *, setup: Sequence[str] = (), persist: bool = False) -> Result:
    """Run a SQL Lab script exactly as written in the .sql files.

    persist=False (default): everything runs inside one transaction that is
    rolled back at the end, so nothing is saved.
    persist=True: the script runs in autocommit mode, like pressing F5 in SSMS.

    ``setup`` statements run first on the same connection (their results are
    discarded). An error does not raise: it is returned together with whatever
    result sets were produced before it.
    """
    result = Result()
    try:
        with _connection(autocommit=persist) as conn:
            cursor = conn.cursor()
            try:
                for statement in setup:
                    cursor.execute(statement)
                    _drain(cursor, [], [])
                cursor.execute(sql)
                _drain(cursor, result.frames, result.messages)
            except pyodbc.Error as exc:
                result.error = translate_error(exc)
            finally:
                cursor.close()
    except DatabaseError as exc:
        result.error = exc
    if not persist and result.error is not None and result.error.number == 3998:
        # A trigger's THROW dooms the surrounding transaction. In rollback mode that is
        # exactly what we want, so report it as a message instead of an error.
        result.messages.append("SQL Server rolled the transaction back (it became uncommittable after the THROW).")
        result.error = None
    if persist:
        clear_cache()
    return result


def ping() -> bool:
    """True when the database answers. Used for the sidebar status dot."""
    try:
        fetch("SELECT 1 AS ok")
        return True
    except DatabaseError:
        return False
