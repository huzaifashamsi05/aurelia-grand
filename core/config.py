"""Central configuration: one place for the hotel date and the connection settings.

Every value can come from an environment variable or from .streamlit/secrets.toml.
Environment variables win, so the same code runs locally and in the cloud.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
ERD_DIR = ROOT / "erd"
ASSETS_DIR = ROOT / "assets"

HOTEL_NAME = "Aurelia Grand"
HOTEL_CITY = "Karachi"
APP_TITLE = "Command Center"

# The seed data is a snapshot taken on this date.
SNAPSHOT_DATE = "2026-11-25"

# Seconds that read queries stay cached. Every write clears the cache.
CACHE_TTL = 120

# Loyalty thresholds enforced by trg_Payments_VIPUpgrade (PKR lifetime spend).
GOLD_THRESHOLD = 750_000
PLATINUM_THRESHOLD = 2_000_000

CHANNELS = ["Website", "Walk-in", "Phone", "Booking.com", "Corporate"]
PAYMENT_METHODS = ["Card", "Cash", "Bank Transfer", "JazzCash", "Easypaisa"]


def _secrets_section(name: str | None = None) -> dict:
    """Read st.secrets safely: a missing secrets.toml must not crash the app."""
    try:
        source = st.secrets if name is None else st.secrets.get(name, {})
        return dict(source)
    except Exception:
        return {}


def setting(key: str, default=None):
    """Environment variable first, then secrets.toml, then the default."""
    env_value = os.environ.get(key)
    if env_value not in (None, ""):
        return env_value
    return _secrets_section().get(key, default)


def hotel_today() -> date:
    """HOTEL_TODAY: the hotel's "today". "auto" follows the real calendar."""
    raw = str(setting("HOTEL_TODAY", SNAPSHOT_DATE)).strip().lower()
    if raw in ("auto", "today", "real", "now"):
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.fromisoformat(SNAPSHOT_DATE)


def uses_real_date() -> bool:
    return hotel_today() == date.today()


def db_settings() -> dict:
    """Connection settings. Windows Authentication is used when no username is given."""
    section = _secrets_section("database")

    def pick(env_key: str, secret_key: str, default=None):
        env_value = os.environ.get(env_key)
        if env_value not in (None, ""):
            return env_value
        return section.get(secret_key, default)

    trust = pick("AURELIA_DB_TRUST_CERT", "trust_server_certificate", True)
    if isinstance(trust, str):
        trust = trust.strip().lower() in ("1", "true", "yes", "y")

    return {
        "server": pick("AURELIA_DB_SERVER", "server", r"localhost\SQLEXPRESS"),
        "database": pick("AURELIA_DB_NAME", "database", "AureliaGrand"),
        "driver": pick("AURELIA_DB_DRIVER", "driver", "auto"),
        "username": pick("AURELIA_DB_USER", "username", None),
        "password": pick("AURELIA_DB_PASSWORD", "password", None),
        "trust_server_certificate": bool(trust),
    }
