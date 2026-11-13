"""SQL Lab (for the viva): every query from files 03, 04 and 06, shown and runnable.

The SQL text is read straight from the .sql files. Statements that change data
run inside a transaction that is rolled back; the one script that cannot
(the guest journey of file 06) is clearly marked and asks for confirmation.
"""
from __future__ import annotations

import streamlit as st

from core import db, sql_catalog, ui

ui.page_header(
    "For the Viva",
    "SQL Lab",
    "Every query from files 03, 04 and 06, exactly as written. Pick one, read the SQL, run it.",
    side=f"<b>{len(sql_catalog.all_queries())} queries</b><br>read from the .sql files",
)

groups = [g for g in sql_catalog.GROUPS if sql_catalog.by_group(g)]
if not groups:
    ui.empty("No .sql files were found in the sql/ folder.")
    st.stop()

st.session_state.setdefault("lab_group", groups[0])
group = st.segmented_control("Group", groups, key="lab_group", required=True, label_visibility="collapsed") or groups[0]
queries = sql_catalog.by_group(group)
labels = {q.id: q.label for q in queries}

MODE_TEXT = {
    sql_catalog.MODE_READ: ("Read-only", "This query only reads data."),
    sql_catalog.MODE_ROLLBACK: ("Rolled back", "Runs inside a transaction that is rolled back. Nothing is saved."),
    sql_catalog.MODE_LIVE: ("Live write", "This script really changes the database, like pressing F5 in SSMS."),
}

list_column, work_column = st.columns([1, 2.2], gap="large")

with list_column:
    st.caption(f"{len(queries)} in {group}")
    with st.container(height=520, border=True):
        query_id = st.radio("Query", list(labels), format_func=labels.get, key=f"lab_pick_{group}",
                            label_visibility="collapsed")

query = sql_catalog.get(query_id)
results = st.session_state.setdefault("lab_results", {})

with work_column:
    badge, explanation = MODE_TEXT[query.mode]
    badge_class = {"Read-only": "", "Rolled back": "silver", "Live write": "gold"}[badge]
    ui.render(
        f'<div class="ag-overline">{ui.esc(query.id)} · {ui.esc(query.source)}</div>'
        f'<div class="ag-section" style="margin-top:0.15rem">{ui.esc(query.title)}</div>'
        f'<div class="ag-section-note">{ui.esc(query.description)}</div>'
        f'<div style="margin-bottom:0.5rem"><span class="ag-badge {badge_class}">{badge}</span>'
        f'<span class="ag-section-note">&nbsp; {ui.esc(explanation)}</span></div>'
    )

    confirmed = True
    if query.mode == sql_catalog.MODE_LIVE:
        ui.notice("info", "This one writes for real",
                  "The journey books a room for a real guest, checks in, adds services and checks out. "
                  "It cannot be wrapped in a rollback because step 4b makes a trigger THROW on purpose. "
                  "Re-running 00_BUILD_ALL.sql resets the data.")
        confirmed = st.checkbox("I understand. Run it and save the changes.", key=f"lab_confirm_{query.id}")

    if st.button("Run", type="primary", icon=":material/play_arrow:", key=f"lab_run_{query.id}",
                 disabled=not confirmed):
        with st.spinner("Running on SQL Server..."):
            results[query.id] = db.run_script(query.sql, setup=query.setup,
                                              persist=query.mode == sql_catalog.MODE_LIVE)

    line_count = query.sql.count("\n") + 1
    st.code(query.sql, language="sql", height="content" if line_count <= 16 else 340)

    if query.setup:
        with st.expander("Statements that run first, inside the same rolled-back transaction"):
            st.code("\n\n".join(query.setup), language="sql")

    result = results.get(query.id)
    if result is not None:
        ui.hairline()
        if not result.frames and not result.error and not result.messages:
            st.caption("The script ran and returned no result sets.")
        for index, frame in enumerate(result.frames, start=1):
            st.caption(f"Result {index} · {len(frame)} row(s)")
            ui.table(frame, height=min(360, 38 * (len(frame) + 1) + 4), key=f"lab_grid_{query.id}_{index}")
        if result.error:
            error = result.error
            meta = " · ".join(p for p in (error.source, f"error {error.number}" if error.number else None) if p)
            ui.notice("error", "SQL Server raised an error", error.detail or error.message, meta or None)
        if result.messages:
            with st.expander(f"Messages ({len(result.messages)})", expanded=not result.frames):
                st.code("\n".join(result.messages), language="text")
        if query.mode == sql_catalog.MODE_ROLLBACK:
            st.caption("Transaction rolled back: the database is unchanged.")
