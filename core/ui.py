"""Shared look and feel: CSS, sidebar, headers, KPI cards, badges, notices, formatting."""
from __future__ import annotations

import html
import logging
import math
from datetime import date, datetime

import streamlit as st

from . import config, db

log = logging.getLogger("aurelia.ui")


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def esc(value) -> str:
    """Escape text that comes from the database before putting it in HTML."""
    return html.escape("" if value is None else str(value))


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def pkr(value, short: bool = False) -> str:
    """PKR 1,435,000  or, with short=True,  PKR 45.6M / PKR 52.4K."""
    number = _number(value)
    if number is None:
        return "-"
    if not short:
        return f"PKR {number:,.0f}"
    magnitude = abs(number)
    if magnitude >= 1_000_000_000:
        return f"PKR {number / 1_000_000_000:.2f}B"
    if magnitude >= 1_000_000:
        return f"PKR {number / 1_000_000:.1f}M"
    if magnitude >= 10_000:
        return f"PKR {number / 1_000:.1f}K"
    return f"PKR {number:,.0f}"


def num(value, decimals: int = 0) -> str:
    number = _number(value)
    return "-" if number is None else f"{number:,.{decimals}f}"


def whole(value) -> str:
    """An identifier such as a booking number: no thousands separator."""
    number = _number(value)
    return "-" if number is None else str(int(number))


MONEY_COLUMNS = {
    "RoomCharge", "ServiceCharge", "BillTotal", "Paid", "Balance", "BalanceDue", "Bill", "Total",
    "Room charge", "Services", "Spend",
    "RoomSpend", "ServiceSpend", "LifetimeSpend", "LowestRate", "HighestRate", "RatePerNight",
    "BaseRate", "Price", "StayTotal", "Amount", "UnitPrice", "LineTotal",
}


def table(frame, *, height: int | str = "auto", key: str | None = None, labels: dict | None = None) -> None:
    """A result grid with PKR columns formatted with thousands separators."""
    import pandas as pd  # local import keeps this module light

    data = frame.rename(columns=labels or {})
    column_config = {}
    for name in data.columns:
        if not pd.api.types.is_numeric_dtype(data[name]) or pd.api.types.is_bool_dtype(data[name]):
            continue
        if str(name).endswith("_PKR") or name in MONEY_COLUMNS:
            column_config[name] = st.column_config.NumberColumn(format="%,.0f")
    st.dataframe(data, hide_index=True, width="stretch", height=height, key=key, column_config=column_config)


def pct(value, decimals: int = 1) -> str:
    number = _number(value)
    return "-" if number is None else f"{number:.{decimals}f}%"


def as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def short_date(value) -> str:
    """25 Nov 2026"""
    day = as_date(value)
    return "-" if day is None else f"{day.day} {day.strftime('%b %Y')}"


def long_date(value) -> str:
    """Wednesday, 25 November 2026"""
    day = as_date(value)
    return "-" if day is None else f"{day.strftime('%A')}, {day.day} {day.strftime('%B %Y')}"


# --------------------------------------------------------------------------
# Page chrome
# --------------------------------------------------------------------------

def render(markup: str) -> None:
    st.html(markup)


@st.cache_data(show_spinner=False)
def _css(modified: float) -> str:
    """The stylesheet, re-read whenever the file's modified time changes."""
    return (config.ASSETS_DIR / "style.css").read_text(encoding="utf-8")


def inject_css() -> None:
    path = config.ASSETS_DIR / "style.css"
    st.html(f"<style>{_css(path.stat().st_mtime)}</style>")


@st.cache_data(ttl=20, show_spinner=False)
def _database_online() -> bool:
    return db.ping()


def sidebar(pages: list) -> None:
    today = config.hotel_today()
    online = _database_online()
    with st.sidebar:
        render(
            '<div class="ag-brand">'
            '<div class="ag-monogram">AG</div>'
            f'<div class="ag-brand-name">{esc(config.HOTEL_NAME)}</div>'
            f'<div class="ag-brand-sub">{esc(config.APP_TITLE)}</div>'
            "</div>"
        )
        for page in pages:
            st.page_link(page, label=page.title, icon=page.icon)
        date_kind = "live" if config.uses_real_date() else "snapshot"
        status = (
            '<span class="ag-dot"></span>Connected' if online
            else '<span class="ag-dot off"></span>Offline'
        )
        settings = config.db_settings()
        render(
            '<div class="ag-side-foot">'
            f'<span class="k">Hotel date · {date_kind}</span><span class="v">{short_date(today)}</span>'
            f'<span class="k">Database</span><span class="v">{status}</span><br>'
            f'<span>{esc(settings["database"])} · SQL Server</span>'
            '<span class="k">DBMS Project</span><span class="v">Group 08 · 25F-DS · DUET</span>'
            "</div>"
        )


def page_header(overline: str, title: str, subtitle: str | None = None, side: str | None = None,
                hero: bool = False) -> None:
    subtitle_html = f'<div class="ag-subtitle">{esc(subtitle)}</div>' if subtitle else ""
    side_html = f'<div class="ag-header-side">{side}</div>' if side else ""
    title_class = "ag-title hero" if hero else "ag-title"
    render(
        '<div class="ag-header"><div class="ag-header-row"><div>'
        f'<div class="ag-overline">{esc(overline)}</div>'
        f'<div class="{title_class}">{esc(title)}</div>{subtitle_html}'
        f"</div>{side_html}</div></div>"
    )
    render_flash()


def section(title: str, note: str | None = None) -> None:
    note_html = f'<div class="ag-section-note">{esc(note)}</div>' if note else ""
    render(f'<div class="ag-section">{esc(title)}</div>{note_html}')


def hairline() -> None:
    render('<hr class="ag-hairline">')


def empty(text: str) -> None:
    render(f'<div class="ag-card"><div class="ag-empty">{esc(text)}</div></div>')


# --------------------------------------------------------------------------
# Small components
# --------------------------------------------------------------------------

def money_html(value, short: bool = True) -> str:
    """'PKR' in small caps before the figure, used inside KPI cards."""
    text = pkr(value, short=short)
    if text.startswith("PKR "):
        return f"<small>PKR</small>{esc(text[4:])}"
    return esc(text)


def kpi_row(cards: list[dict], columns: int = 6) -> None:
    """cards: [{'label': ..., 'value': html, 'sub': text}]"""
    css_class = {6: "ag-kpis", 4: "ag-kpis four", 3: "ag-kpis three"}.get(columns, "ag-kpis")
    parts = []
    for card in cards:
        sub = f'<div class="sub">{esc(card["sub"])}</div>' if card.get("sub") else ""
        parts.append(
            f'<div class="ag-kpi"><div class="label">{esc(card["label"])}</div>'
            f'<div class="value">{card["value"]}</div>{sub}</div>'
        )
    render(f'<div class="{css_class}">{"".join(parts)}</div>')


def tier_badge(tier) -> str:
    name = str(tier or "Silver")
    return f'<span class="ag-badge {esc(name.lower())}">{esc(name)}</span>'


def status_pill(status, label: str | None = None, count: int | None = None) -> str:
    name = str(status or "")
    pretty = {"CheckedIn": "Checked in", "CheckedOut": "Checked out", "NoShow": "No-show"}.get(name, name)
    count_html = f" <b>{count}</b>" if count is not None else ""
    return f'<span class="ag-pill {esc(name.lower())}"><i></i>{esc(label or pretty)}{count_html}</span>'


def status_legend(counts: dict, order=("Occupied", "Available", "Cleaning", "Maintenance")) -> str:
    """Legend row for room statuses, each with its count."""
    pills = "".join(status_pill(name, count=int(counts.get(name, 0))) for name in order)
    return f'<div class="ag-legend">{pills}</div>'


def invoice_card(invoice: dict, title: str = "Invoice", footer: str | None = None) -> None:
    """Render one row of vw_GuestInvoice (or a procedure's invoice result)."""
    if not invoice:
        return
    stay = ""
    if invoice.get("CheckInDate") is not None:
        stay = (f' · {short_date(invoice.get("CheckInDate"))} to {short_date(invoice.get("CheckOutDate"))}'
                f' · {num(invoice.get("Nights"))} night(s)')
    room = f' · Room {esc(invoice.get("RoomNumber"))}' if invoice.get("RoomNumber") else ""
    lines = ""
    if "RoomCharge" in invoice:
        lines += f'<div class="line"><span>Room charge</span><span>{pkr(invoice.get("RoomCharge"))}</span></div>'
    if "ServiceCharge" in invoice:
        lines += f'<div class="line"><span>Services</span><span>{pkr(invoice.get("ServiceCharge"))}</span></div>'
    lines += f'<div class="line total"><span>Bill total</span><span>{pkr(invoice.get("BillTotal"))}</span></div>'
    lines += f'<div class="line"><span>Paid</span><span>{pkr(invoice.get("Paid"))}</span></div>'
    lines += f'<div class="line balance"><span>Balance</span><span>{pkr(invoice.get("Balance"))}</span></div>'
    foot = f'<div class="foot">{esc(footer)}</div>' if footer else ""
    render(
        '<div class="ag-invoice">'
        f'<div class="head"><span class="t">{esc(title)}</span>'
        f'<span class="n">Booking #{esc(whole(invoice.get("BookingID")))}</span></div>'
        f'<div class="who"><b>{esc(invoice.get("Guest"))}</b>{room}{esc(stay)}</div>'
        f"{lines}{foot}</div>"
    )


# --------------------------------------------------------------------------
# Notices, toasts and errors
# --------------------------------------------------------------------------

_ICONS = {
    "success": ":material/check_circle:",
    "error": ":material/error:",
    "vip": ":material/workspace_premium:",
    "info": ":material/info:",
}


def notice(kind: str, title: str, body: str | None = None, meta: str | None = None) -> None:
    body_html = f'<div class="b">{esc(body)}</div>' if body else ""
    meta_html = f'<div class="m">{esc(meta)}</div>' if meta else ""
    render(f'<div class="ag-notice {esc(kind)}"><div class="t">{esc(title)}</div>{body_html}{meta_html}</div>')


def flash(kind: str, title: str, body: str | None = None, meta: str | None = None) -> None:
    """Queue a message that is shown (toast + banner) at the top of the next run."""
    st.session_state.setdefault("_flash", []).append(
        {"kind": kind, "title": title, "body": body, "meta": meta}
    )


def flash_error(error: db.DatabaseError) -> None:
    title = "Double booking blocked" if error.is_double_booking else {
        "rule": "The database said no",
        "constraint": "The database rejected this change",
        "connection": "Database unavailable",
    }.get(error.kind, "The database reported an error")
    meta_parts = [part for part in (error.source, f"error {error.number}" if error.number else None) if part]
    flash("error", title, error.message, " · ".join(meta_parts) or None)


def flash_vip(guest: str, tier: str) -> None:
    flash("vip", f"Upgraded to {tier}", f"{guest} has reached {tier} status.",
          "Trigger trg_Payments_VIPUpgrade")


def render_flash() -> None:
    """Show queued messages: a toast for the moment, a banner so the room can read it."""
    for message in st.session_state.pop("_flash", []):
        toast_text = message["title"] if not message["body"] else f'**{message["title"]}**  \n{message["body"]}'
        duration = "long" if message["kind"] in ("error", "vip") else "short"
        st.toast(toast_text, icon=_ICONS.get(message["kind"], _ICONS["info"]), duration=duration)
        notice(message["kind"], message["title"], message["body"], message["meta"])


def error_panel(error: Exception) -> None:
    """Full-page friendly error. Never shows a Python traceback."""
    if isinstance(error, db.DatabaseError):
        if error.kind == "connection":
            notice("error", "The hotel database is not reachable", error.message,
                   "Check that SQL Server (SQLEXPRESS) is running, then refresh this page.")
            if error.detail:
                st.caption(error.detail)
        else:
            meta_parts = [p for p in (error.source, f"error {error.number}" if error.number else None) if p]
            notice("error", "The database reported a problem", error.message, " · ".join(meta_parts) or None)
    else:
        log.exception("Unexpected error while rendering a page", exc_info=error)
        notice("error", "Something went wrong on this screen",
               "The page could not be displayed. Please refresh, or open another screen from the sidebar.",
               type(error).__name__)
