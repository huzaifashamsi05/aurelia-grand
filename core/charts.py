"""Plotly charts in the Aurelia Grand style.

Chart rules used throughout:
  * one y-axis per chart (never dual axis);
  * thin marks: 2px lines, bars at most ~22px thick with a rounded data end;
  * one hue for a single series; the validated 5-colour set only when the
    series themselves are the subject, always with a legend;
  * solid hairline grid, text in ink colours (never in the series colour);
  * hover on every chart, and the same numbers are always available as a table.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SURFACE = "#16161A"
INK = "#EDE6D6"
INK_SOFT = "#C9C2B2"
MUTED = "#8E8A80"
GRID = "#26262B"
AXIS = "#34343A"
FONT = "Inter, 'Segoe UI', system-ui, sans-serif"

# Validated on the #16161A surface (lightness band, chroma floor, CVD separation, contrast).
SERIES = ["#B28B39", "#4189CC", "#C96A56", "#8F7AD6", "#2A9D82"]
GOLD = SERIES[0]
GOLD_WASH = "rgba(178, 139, 57, 0.10)"


def _style(fig: go.Figure, height: int, *, legend: bool = False, unified: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=MUTED, size=12),
        margin=dict(l=4, r=12, t=30 if legend else 10, b=4),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=INK_SOFT, size=12), bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified" if unified else "closest",
        hoverlabel=dict(bgcolor="#1E1E23", bordercolor=AXIS, font=dict(color=INK, family=FONT, size=12)),
        barcornerradius=4,
        bargap=0.5,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=AXIS, tickcolor=AXIS,
                     tickfont=dict(color=MUTED, size=11), automargin=True)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=False, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=MUTED, size=11), automargin=True)
    return fig


def show(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False, "responsive": True})


def line_chart(
    frame: pd.DataFrame,
    x: str,
    series: dict[str, str],
    *,
    height: int = 250,
    prefix: str = "",
    suffix: str = "",
    decimals: int = 0,
    area: bool = False,
    zero_based: bool = True,
) -> go.Figure:
    """series = {"Legend label": "column name"}. End points are labelled directly."""
    fig = go.Figure()
    number_format = f",.{decimals}f"
    many = len(series) > 1
    for index, (label, column) in enumerate(series.items()):
        colour = SERIES[index % len(SERIES)]
        fig.add_trace(go.Scatter(
            x=frame[x], y=frame[column], name=label, mode="lines",
            line=dict(color=colour, width=2, shape="linear"),
            fill="tozeroy" if (area and not many) else None,
            fillcolor=GOLD_WASH if (area and not many) else None,
            hovertemplate=f"{label}: {prefix}%{{y:{number_format}}}{suffix}<extra></extra>",
        ))
        if len(frame):
            last_x, last_y = frame[x].iloc[-1], frame[column].iloc[-1]
            fig.add_trace(go.Scatter(
                x=[last_x], y=[last_y], mode="markers", showlegend=False, hoverinfo="skip",
                marker=dict(color=colour, size=9, line=dict(color=SURFACE, width=2)),
            ))
            fig.add_annotation(
                x=last_x, y=last_y, text=f"{prefix}{last_y:{number_format}}{suffix}",
                showarrow=False, xanchor="left", xshift=8,
                font=dict(color=INK, size=12, family=FONT),
            )
    _style(fig, height, legend=many, unified=True)
    fig.update_layout(margin=dict(r=64))
    fig.update_yaxes(tickprefix=prefix, ticksuffix=suffix, rangemode="tozero" if zero_based else "normal",
                     tickformat="~s" if not suffix else None)
    return fig


def bar_chart(
    frame: pd.DataFrame,
    category: str,
    value: str,
    *,
    horizontal: bool = True,
    height: int | None = None,
    prefix: str = "",
    suffix: str = "",
    decimals: int = 0,
    compact: bool = False,
    highlight: str | None = None,
) -> go.Figure:
    """One series, one hue. Values are printed at the bar tips.

    compact=True prints values as 45.6M / 52.4K. ``highlight`` names one category
    to keep in gold while the others fall back to a quiet grey (emphasis form).
    """
    data = frame.copy()
    if horizontal:
        data = data.iloc[::-1]  # plotly draws the first row at the bottom

    def label(number) -> str:
        if pd.isna(number):
            return ""
        if compact:
            magnitude = abs(number)
            if magnitude >= 1_000_000:
                return f"{prefix}{number / 1_000_000:.1f}M{suffix}"
            if magnitude >= 10_000:
                return f"{prefix}{number / 1_000:.1f}K{suffix}"
        return f"{prefix}{number:,.{decimals}f}{suffix}"

    colours = GOLD
    if highlight is not None:
        colours = [GOLD if str(c) == str(highlight) else "#55524C" for c in data[category]]

    texts = [label(v) for v in data[value]]
    hover = f"%{{{'y' if horizontal else 'x'}}}: {prefix}%{{{'x' if horizontal else 'y'}:,.{decimals}f}}{suffix}<extra></extra>"
    fig = go.Figure(go.Bar(
        x=data[value] if horizontal else data[category],
        y=data[category] if horizontal else data[value],
        orientation="h" if horizontal else "v",
        marker=dict(color=colours, line=dict(width=0)),
        text=texts, textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_SOFT, size=11, family=FONT),
        hovertemplate=hover,
    ))
    if height is None:
        height = max(150, 34 * len(data) + 40) if horizontal else 260
    _style(fig, height)
    if horizontal:
        fig.update_layout(margin=dict(r=70))
        fig.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False, linecolor="rgba(0,0,0,0)")
        fig.update_yaxes(showgrid=False, tickfont=dict(color=INK_SOFT, size=12), ticksuffix="  ")
    else:
        fig.update_layout(margin=dict(t=26))
        fig.update_yaxes(tickprefix=prefix, ticksuffix=suffix, tickformat="~s" if not suffix else None,
                         rangemode="tozero")
    return fig


def grouped_bar_chart(
    frame: pd.DataFrame,
    category: str,
    series: dict[str, str],
    *,
    height: int = 280,
    prefix: str = "",
    suffix: str = "",
    decimals: int = 0,
) -> go.Figure:
    """Two to four series side by side on one axis, with a legend."""
    fig = go.Figure()
    for index, (label, column) in enumerate(series.items()):
        fig.add_trace(go.Bar(
            x=frame[category], y=frame[column], name=label,
            marker=dict(color=SERIES[index % len(SERIES)], line=dict(color=SURFACE, width=2)),
            hovertemplate=f"{label}: {prefix}%{{y:,.{decimals}f}}{suffix}<extra></extra>",
        ))
    _style(fig, height, legend=True, unified=True)
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)
    fig.update_yaxes(tickprefix=prefix, ticksuffix=suffix, tickformat="~s" if not suffix else None,
                     rangemode="tozero")
    return fig
