"""Reads the project's own .sql files and turns them into a labelled query catalogue.

The SQL Lab and the Analytics page both use this, so the SQL the app runs is
exactly the SQL in ``sql/03``, ``sql/04`` and ``sql/06`` - nothing is retyped.

  03_data_operations.sql   -> C01..  (CRUD)  and  K01.. (constraints)
  04_reporting_queries.sql -> R01..R15 (reports)
  06_advanced_demo.sql     -> A1..A8  (advanced objects)
  assets/sql_lab_extras.sql-> X1..    (trigger demos written for this app)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import config, db

GROUP_REPORTS = "Reports"
GROUP_CRUD = "CRUD"
GROUP_CONSTRAINTS = "Constraints"
GROUP_ADVANCED = "Advanced"
GROUP_TRIGGERS = "Trigger demos"
GROUPS = [GROUP_REPORTS, GROUP_CRUD, GROUP_CONSTRAINTS, GROUP_ADVANCED, GROUP_TRIGGERS]

MODE_READ = "read"          # SELECT only
MODE_ROLLBACK = "rollback"  # writes, but inside a transaction that is rolled back
MODE_LIVE = "live"          # really writes to the database (clearly marked in the UI)

FILE_CRUD = "03_data_operations.sql"
FILE_REPORTS = "04_reporting_queries.sql"
FILE_ADVANCED = "06_advanced_demo.sql"
FILE_EXTRAS = "sql_lab_extras.sql"

# The guest journey in file 06 cannot run inside an outer transaction: step 4b
# makes a trigger THROW on purpose, which would roll back the booking made in 4a.
_LIVE_ADVANCED = {"4"}


@dataclass(frozen=True)
class Query:
    id: str
    group: str
    title: str
    description: str
    sql: str
    source: str
    mode: str
    setup: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.id} · {self.title}"


_GO = re.compile(r"^[ \t]*GO[ \t]*;?[ \t]*$", re.I | re.M)
_USE = re.compile(r"^[ \t]*USE[ \t]+\w+[ \t]*;[ \t]*$", re.I | re.M)
_BANNER = re.compile(r"/\*[ \t]*[=-]{10,}[ \t]*\r?\n(?P<body>.*?)\r?\n[ \t]*[=-]{10,}[ \t]*\*/", re.S)
_ONE_LINE = re.compile(r"^/\*[ \t]*(?P<title>[^\r\n]*?)[ \t]*\*/[ \t]*$", re.M)
_WRITES = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE)\b|sp_(CreateBooking|CheckIn|AddService|CheckOut)\b", re.I)
_OWN_TRANSACTION = re.compile(r"\b(BEGIN\s+TRAN|ROLLBACK)", re.I)
_COMMENTS = re.compile(r"/\*.*?\*/|--[^\r\n]*", re.S)
_TODAY_DECLARATION = re.compile(r"DECLARE\s+@Today\s+DATE\s*=\s*'\d{4}-\d{2}-\d{2}'\s*;", re.I)


def _read(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def _batches(text: str) -> list[str]:
    """Split a script on GO and drop the USE statement and empty batches."""
    result = []
    for batch in _GO.split(text):
        batch = _USE.sub("", batch).strip()
        if batch and _COMMENTS.sub("", batch).strip():
            result.append(batch)
    return result


def _clean_title(raw: str) -> str:
    return raw.strip().strip("-").strip()


def _banner_lines(body: str) -> list[str]:
    return [line.strip() for line in body.split("\n") if line.strip()]


def _mode_for(sql: str) -> str:
    return MODE_ROLLBACK if _WRITES.search(_COMMENTS.sub("", sql)) else MODE_READ


def _leading_header(batch: str) -> tuple[str, str, str]:
    """Return (title, description, sql) using the comment that opens a batch."""
    banner = _BANNER.match(batch)
    if banner:
        lines = _banner_lines(banner["body"])
        title = lines[0] if lines else ""
        return title, " ".join(lines[1:]), batch[banner.end():].strip()
    marker = _ONE_LINE.match(batch)
    if marker:
        return _clean_title(marker["title"]), "", batch[marker.end():].strip()
    return "", "", batch.strip()


def _parse_reports(text: str) -> list[Query]:
    queries = []
    for batch in _batches(text):
        title, description, sql = _leading_header(batch)
        match = re.match(r"(R\d{2})\.\s*(.*)", title)
        if not match or not sql:
            continue
        queries.append(Query(match[1], GROUP_REPORTS, match[2].strip(), description, sql,
                             FILE_REPORTS, _mode_for(sql)))
    return queries


def _parse_numbered(text: str, *, prefix: str, group: str, source: str, live: set[str]) -> list[Query]:
    """One query per GO batch, titled by the comment that opens the batch (files 06 / extras)."""
    queries = []
    for batch in _batches(text):
        title, description, sql = _leading_header(batch)
        match = re.match(r"(?:[A-Z])?(\d+)\.\s*(.*)", title)
        if not match or not sql:
            continue
        number, name = match[1], match[2].strip()
        mode = MODE_LIVE if number in live else _mode_for(sql)
        queries.append(Query(f"{prefix}{number}", group, name, description, sql, source, mode))
    return queries


def _parse_crud(text: str) -> list[Query]:
    """File 03: statements are separated by one-line /* ... */ comments."""
    queries: list[Query] = []
    crud_count = constraint_count = 0

    for batch in _batches(text):
        section = "select"
        section_items: list[Query] = []
        banner_spans = [(m.start(), m.end(), _banner_lines(m["body"])) for m in _BANNER.finditer(batch)]
        headers = [(m.start(), m.end(), _clean_title(m["title"])) for m in _ONE_LINE.finditer(batch)]

        for index, (start, end, title) in enumerate(headers):
            # Which banner (if any) came most recently before this statement?
            for b_start, _b_end, lines in banner_spans:
                if b_start < start:
                    heading = " ".join(lines).upper()
                    new_section = ("constraint" if "CONSTRAINT" in heading
                                   else "write" if "INSERT" in heading else section)
                    if new_section != section:
                        section, section_items = new_section, []

            stop = headers[index + 1][0] if index + 1 < len(headers) else len(batch)
            for b_start, _b_end, _lines in banner_spans:
                if end <= b_start < stop:
                    stop = b_start
            sql = batch[end:stop].strip()
            if not sql or not title:
                continue

            keyword, _, rest = title.partition(" : ")
            nice_title = f"{keyword.strip()} · {rest.strip()}" if rest else title

            if section == "constraint":
                constraint_count += 1
                query = Query(f"K{constraint_count:02d}", GROUP_CONSTRAINTS, nice_title,
                              "Expected to fail: the constraint rejects the statement.",
                              sql, FILE_CRUD, MODE_ROLLBACK)
            else:
                crud_count += 1
                setup: tuple[str, ...] = ()
                if section == "write" and not _OWN_TRANSACTION.search(sql):
                    setup = tuple(q.sql for q in section_items if not _OWN_TRANSACTION.search(q.sql))
                query = Query(f"C{crud_count:02d}", GROUP_CRUD, nice_title, "", sql, FILE_CRUD,
                              _mode_for(sql), setup)
            section_items.append(query)
            queries.append(query)
    return queries


def _source_files() -> list[Path]:
    return [
        config.SQL_DIR / FILE_REPORTS,
        config.SQL_DIR / FILE_CRUD,
        config.SQL_DIR / FILE_ADVANCED,
        config.ASSETS_DIR / FILE_EXTRAS,
    ]


@lru_cache(maxsize=4)
def _load(_fingerprint: tuple) -> tuple[Query, ...]:
    reports, crud, advanced, extras = _source_files()
    queries: list[Query] = []
    if reports.exists():
        queries += _parse_reports(_read(reports))
    if crud.exists():
        queries += _parse_crud(_read(crud))
    if advanced.exists():
        queries += _parse_numbered(_read(advanced), prefix="A", group=GROUP_ADVANCED,
                                   source=FILE_ADVANCED, live=_LIVE_ADVANCED)
    if extras.exists():
        queries += _parse_numbered(_read(extras), prefix="X", group=GROUP_TRIGGERS,
                                   source=FILE_EXTRAS, live=set())
    return tuple(queries)


def all_queries() -> tuple[Query, ...]:
    """Every query, re-read automatically when a .sql file changes."""
    fingerprint = tuple((str(p), p.stat().st_mtime_ns) for p in _source_files() if p.exists())
    return _load(fingerprint)


def by_group(group: str) -> list[Query]:
    return [q for q in all_queries() if q.group == group]


def get(query_id: str) -> Query | None:
    return next((q for q in all_queries() if q.id == query_id), None)


def run_report(report_id: str, today: date | None = None) -> pd.DataFrame:
    """Run report R01..R15 for the Analytics page (cached, read-only).

    R01 and R12 declare ``@Today`` as a fixed date in the file. Here that one
    literal is replaced by a bound parameter so the report follows HOTEL_TODAY.
    """
    query = get(report_id)
    if query is None:
        raise db.DatabaseError(f"Report {report_id} was not found in {FILE_REPORTS}.")
    sql, params = query.sql, ()
    if _TODAY_DECLARATION.search(sql):
        sql = _TODAY_DECLARATION.sub("DECLARE @Today DATE = ?;", sql)
        params = (today or config.hotel_today(),)
    return db.read(sql, params)
