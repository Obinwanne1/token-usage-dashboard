"""Token Usage Dashboard — reads Claude Code local JSONL logs."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

sys.path.insert(0, str(Path(__file__).parent))

from data_parser import load_data_cached
from pricing import format_cost

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Token Usage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Theme state — must be read BEFORE CSS is rendered
# Using key="dark_mode" binds toggle directly to session_state["dark_mode"]
# ---------------------------------------------------------------------------

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

dark = st.session_state["dark_mode"]

# Color tokens
BG          = "#0A1F0A" if dark else "#FFFFFF"   # deep forest green
BG_SECONDARY= "#0F2D10" if dark else "#F9FAFB"   # slightly lighter green
SURFACE     = "#163A17" if dark else "#FFFFFF"   # card surface
BORDER      = "#2D5C2E" if dark else "#E5E7EB"   # green-tinted border
TEXT        = "#E8F5E8" if dark else "#1A1A1A"   # warm off-white green tint
TEXT_MUTED  = "#7DBF7E" if dark else "#6B7280"   # muted green
PRIMARY     = "#407E3C"
ACCENT      = "#5a9e56"
CARD_TOP    = "#5a9e56" if dark else PRIMARY      # brighter accent on dark
PLOT_BG     = "#163A17" if dark else "#FFFFFF"
GRID        = "#2D5C2E" if dark else "#F3F4F6"

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');

    html, body, [class*="css"], .stApp {{
        font-family: 'Poppins', sans-serif;
        background-color: {BG} !important;
        color: {TEXT} !important;
    }}

    /* Hide default header/footer */
    #MainMenu, footer, header {{ visibility: hidden; }}

    /* Sidebar open/close toggle — target multiple Streamlit versions */
    [data-testid="collapsedControl"],
    button[data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    button[aria-label="Open sidebar"],
    button[aria-label="Close sidebar"],
    section[data-testid="stSidebar"] + div button:first-child {{
        background-color: {PRIMARY} !important;
        border-radius: 0 8px 8px 0 !important;
        color: #fff !important;
        min-width: 24px !important;
        opacity: 1 !important;
        border: none !important;
    }}
    [data-testid="collapsedControl"] svg,
    button[aria-label="Open sidebar"] svg,
    button[aria-label="Close sidebar"] svg {{
        fill: #fff !important;
        stroke: #fff !important;
    }}

    /* Sidebar background */
    [data-testid="stSidebar"] {{
        background-color: {BG_SECONDARY} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {TEXT} !important;
    }}

    /* KPI card */
    .kpi-card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-top: 4px solid {CARD_TOP};
        border-radius: 8px;
        padding: 20px 16px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        text-align: center;
        height: 100%;
    }}
    .kpi-label {{
        font-size: 0.78rem;
        font-weight: 600;
        color: {TEXT_MUTED};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }}
    .kpi-value {{
        font-size: 1.9rem;
        font-weight: 700;
        color: {TEXT};
        line-height: 1.1;
    }}
    .kpi-sub {{
        font-size: 0.75rem;
        color: {TEXT_MUTED};
        margin-top: 4px;
    }}

    /* Source breakdown card */
    .source-card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-left: 4px solid {PRIMARY};
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }}
    .source-name {{
        font-size: 0.8rem;
        font-weight: 600;
        color: {TEXT_MUTED};
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    .source-value {{
        font-size: 1.25rem;
        font-weight: 700;
        color: {TEXT};
    }}
    .source-cost {{
        font-size: 0.78rem;
        color: {ACCENT};
        font-weight: 600;
    }}

    /* Live badge pulse animation */
    @keyframes pulse-ring {{
        0%   {{ box-shadow: 0 0 0 0 rgba(64,126,60,0.7); }}
        70%  {{ box-shadow: 0 0 0 8px rgba(64,126,60,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(64,126,60,0); }}
    }}
    @keyframes dot-blink {{
        0%, 100% {{ opacity: 1; }}
        50%       {{ opacity: 0.3; }}
    }}
    .live-badge {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: {PRIMARY};
        color: #fff;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 12px 4px 8px;
        border-radius: 20px;
        letter-spacing: 0.08em;
        animation: pulse-ring 2s ease-out infinite;
    }}
    .live-dot {{
        display: inline-block;
        width: 7px;
        height: 7px;
        background: #fff;
        border-radius: 50%;
        animation: dot-blink 1.2s ease-in-out infinite;
    }}

    /* Section header */
    .section-header {{
        font-size: 1rem;
        font-weight: 600;
        color: {TEXT};
        border-left: 4px solid {PRIMARY};
        padding-left: 10px;
        margin: 24px 0 12px;
    }}

    .sidebar-title {{
        font-size: 0.85rem;
        font-weight: 600;
        color: {PRIMARY};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* Divider */
    hr {{ border-color: {BORDER} !important; }}

    /* Dataframe */
    .stDataFrame {{ background: {SURFACE} !important; }}

    /* Widget labels — toggle, multiselect, text input, date */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label,
    [data-testid="stToggle"] p,
    [data-testid="stToggle"] label,
    [data-testid="stToggle"] span:not([data-testid]),
    .stToggle label, .stToggle p,
    .stMultiSelect label, .stMultiSelect p,
    .stTextInput label, .stTextInput p,
    .stDateInput label, .stDateInput p,
    .stExpander label, .stExpander p,
    .stExpander summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] p {{
        color: {TEXT} !important;
    }}

    /* Multiselect tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
        background-color: {PRIMARY} !important;
        color: #ffffff !important;
    }}

    /* Text input box */
    [data-testid="stTextInput"] input,
    [data-testid="stDateInput"] input {{
        background-color: {SURFACE} !important;
        color: {TEXT} !important;
        border-color: {BORDER} !important;
    }}

    /* Expander header */
    [data-testid="stExpander"] details summary {{
        background-color: {SURFACE} !important;
        color: {TEXT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 6px !important;
    }}

    /* st.caption */
    [data-testid="stCaptionContainer"] p {{
        color: {TEXT_MUTED} !important;
    }}

    /* Plotly modebar (zoom/pan/scale toolbar) — make always visible */
    .modebar {{
        background: transparent !important;
        opacity: 1 !important;
    }}
    .modebar-btn path {{
        fill: {PRIMARY} !important;
    }}
    .modebar-btn:hover path {{
        fill: {ACCENT} !important;
    }}
    .modebar-group {{
        background: {SURFACE} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px !important;
        padding: 2px !important;
    }}

    /* Sidebar toggle — broadest possible selector sweep */
    button[data-testid="collapsedControl"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [class*="collapsedControl"],
    button[aria-label*="sidebar"],
    button[aria-label*="Sidebar"] {{
        background-color: {PRIMARY} !important;
        border-radius: 0 8px 8px 0 !important;
        opacity: 1 !important;
        border: none !important;
        min-width: 24px !important;
        z-index: 9999 !important;
    }}
    button[data-testid="collapsedControl"] svg path,
    [data-testid="collapsedControl"] svg path,
    button[aria-label*="sidebar"] svg path {{
        fill: #ffffff !important;
        stroke: #ffffff !important;
    }}

    /* Download buttons — always green with white text */
    [data-testid="stDownloadButton"] button,
    [data-testid="stDownloadButton"] > button {{
        background-color: {PRIMARY} !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}
    [data-testid="stDownloadButton"] button:hover {{
        background-color: {ACCENT} !important;
    }}

    /* Radio button labels */
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] p,
    [data-testid="stRadio"] span,
    .stRadio label, .stRadio p {{
        color: {TEXT} !important;
    }}

    /* Number input labels */
    [data-testid="stNumberInput"] label,
    [data-testid="stNumberInput"] p {{
        color: {TEXT} !important;
    }}
    [data-testid="stNumberInput"] input {{
        background-color: {SURFACE} !important;
        color: {TEXT} !important;
        border-color: {BORDER} !important;
    }}

    /* st.dataframe — header text visible in dark mode */
    [data-testid="stDataFrame"] th {{
        background-color: {SURFACE} !important;
        color: {TEXT} !important;
    }}
    [data-testid="stDataFrame"] td {{
        color: {TEXT} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Auto-refresh every 30s
# ---------------------------------------------------------------------------

st_autorefresh(interval=30_000, key="data_refresh")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Loading token data..."):
    data = load_data_cached()

df_usage: pd.DataFrame = data["df_usage"]
df_history: pd.DataFrame = data["df_history"]
df_sessions: pd.DataFrame = data["df_sessions"]
df_tool_results: pd.DataFrame = data.get("df_tool_results", pd.DataFrame())

has_usage = not df_usage.empty
has_history = not df_history.empty

TEACHING_MODE = os.getenv("TEACHING_MODE", "false").lower() == "true"

# Read filter values from session_state (set by expander widgets on prior run).
# On first load, session_state keys don't exist — fall back to "all selected".
_all_proj   = sorted(df_usage["project_name"].unique().tolist()) if has_usage else []
_all_types  = sorted(df_history["prompt_type"].unique().tolist()) if has_history else []
_all_models = sorted([m for m in df_usage["model"].unique().tolist() if m != "tool_result"]) if has_usage else []

selected_projects = st.session_state.get("proj_filter_exp",   _all_proj)
selected_types    = st.session_state.get("type_filter_exp",   _all_types)
selected_models   = st.session_state.get("model_filter_exp",  _all_models)
date_range        = st.session_state.get("date_filter_exp",   None)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

df_filtered = df_usage[df_usage["source"] != "tool_result"].copy() if has_usage else df_usage.copy()
df_hist_filtered = df_history.copy()

if selected_projects and has_usage:
    df_filtered = df_filtered[df_filtered["project_name"].isin(selected_projects)]

if selected_models and has_usage:
    df_filtered = df_filtered[df_filtered["model"].isin(selected_models)]

if date_range and has_usage and len(date_range) == 2:
    start, end = date_range
    df_filtered = df_filtered[
        (df_filtered["date"] >= start) & (df_filtered["date"] <= end)
    ]

if selected_types and has_history:
    df_hist_filtered = df_hist_filtered[df_hist_filtered["prompt_type"].isin(selected_types)]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
col_title, col_dark, col_teach, col_live = st.columns([4, 1, 1, 1])
with col_title:
    st.markdown(
        f"<h1 style='font-family:Poppins;font-size:1.8rem;font-weight:700;"
        f"color:{TEXT};margin:0;padding:0;'>📊 Token Usage Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{TEXT_MUTED};font-size:0.8rem;margin:0;'>Claude Code Analytics &nbsp;·&nbsp; "
        f"Last refreshed: {now_str}</p>",
        unsafe_allow_html=True,
    )
with col_dark:
    st.markdown("<br>", unsafe_allow_html=True)
    # key="dark_mode" binds directly to session_state["dark_mode"] — auto-reruns on change
    st.toggle("Dark Mode", key="dark_mode")
with col_teach:
    st.markdown("<br>", unsafe_allow_html=True)
    teaching_toggle = st.toggle("Teaching Mode", key="teaching_toggle", value=TEACHING_MODE)
with col_live:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<span class="live-badge"><span class="live-dot"></span>LIVE</span>', unsafe_allow_html=True)

st.markdown("---")

# Inline filter expander — always accessible even when sidebar is collapsed
with st.expander("☰  Filters & Display", expanded=False):
    _fc1, _fc2, _fc3, _fc4 = st.columns(4)
    with _fc1:
        _all_proj = sorted(df_usage["project_name"].unique().tolist()) if has_usage else []
        selected_projects = st.multiselect("Projects", _all_proj, default=_all_proj, key="proj_filter_exp")
    with _fc2:
        _all_types = sorted(df_history["prompt_type"].unique().tolist()) if has_history else []
        selected_types = st.multiselect("Prompt Types", _all_types, default=_all_types, key="type_filter_exp")
    with _fc3:
        _all_models = sorted([m for m in df_usage["model"].unique().tolist() if m != "tool_result"]) if has_usage else []
        selected_models = st.multiselect("Models", _all_models, default=_all_models, key="model_filter_exp")
    with _fc4:
        if has_usage and "date" in df_usage.columns:
            _valid = df_usage["date"].dropna()
            if not _valid.empty:
                date_range = st.date_input("Date Range", value=(_valid.min(), _valid.max()),
                                               min_value=_valid.min(), max_value=_valid.max(), key="date_filter_exp")
            else:
                date_range = None
        else:
            date_range = None

    st.markdown("---")
    _a1, _a2 = st.columns([1, 3])
    with _a1:
        daily_threshold = st.number_input(
            "Daily cost alert threshold (USD)",
            min_value=0.01, max_value=500.0,
            value=float(st.session_state.get("daily_threshold", 5.0)),
            step=0.50, format="%.2f",
            key="daily_threshold",
            help="Show a warning banner when today's spend exceeds this amount",
        )

# ---------------------------------------------------------------------------
# Daily cost alert banner
# ---------------------------------------------------------------------------

if has_usage and "date" in df_filtered.columns:
    from datetime import date as _date
    _today = _date.today()
    _today_df = df_filtered[df_filtered["date"] == _today]
    _today_cost = _today_df["cost_usd"].sum()
    _today_tokens = int(_today_df["total_tokens"].sum())
    _threshold = st.session_state.get("daily_threshold", 5.0)

    if _today_cost > 0:
        if _today_cost >= _threshold:
            st.markdown(
                f"""<div style="background:#7f1d1d;border:1px solid #dc2626;border-left:6px solid #dc2626;
                border-radius:8px;padding:14px 18px;margin-bottom:12px;color:#fef2f2;">
                <strong>⚠️ Daily Cost Alert</strong> — Today's spend is
                <strong>{format_cost(_today_cost)}</strong>
                ({_today_tokens:,} tokens), exceeding your
                <strong>{format_cost(_threshold)}</strong> threshold.
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            _pct = (_today_cost / _threshold) * 100
            st.markdown(
                f"""<div style="background:{'#163A17' if dark else '#f0f7ee'};
                border:1px solid {'#2D5C2E' if dark else '#c3ddbf'};
                border-left:6px solid {PRIMARY};
                border-radius:8px;padding:14px 18px;margin-bottom:12px;color:{TEXT};">
                <strong>✓ Today's spend:</strong> {format_cost(_today_cost)}
                ({_today_tokens:,} tokens) &nbsp;·&nbsp;
                {_pct:.0f}% of {format_cost(_threshold)} daily limit
                </div>""",
                unsafe_allow_html=True,
            )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

total_tokens = int(df_filtered["total_tokens"].sum()) if has_usage else 0
total_input  = int(df_filtered["input_tokens"].sum()) if has_usage else 0
total_output = int(df_filtered["output_tokens"].sum()) if has_usage else 0
total_cost   = df_filtered["cost_usd"].sum() if has_usage else 0.0
session_count = df_filtered["sessionId"].nunique() if has_usage else 0
project_count = df_filtered["project_name"].nunique() if has_usage else 0
top_model = (
    df_filtered[df_filtered["model"] != "tool_result"]
    .groupby("model")["total_tokens"].sum().idxmax()
    if has_usage and not df_filtered.empty else "—"
)
prompt_count = len(df_history) if has_history else 0
tool_calls_total = int(df_filtered["tool_use_count"].sum()) if has_usage else 0
subagent_tokens = int(
    df_filtered[df_filtered["source"] == "subagent"]["total_tokens"].sum()
) if has_usage else 0


def _kpi(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )


k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(
        _kpi("Total Tokens", f"{total_tokens:,}", f"In: {total_input:,} · Out: {total_output:,}"),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi("Est. Cost (USD)", format_cost(total_cost), "All sessions combined"),
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        _kpi("Sessions", f"{session_count:,}", f"{project_count} projects"),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        _kpi("Prompts Sent", f"{prompt_count:,}", f"{tool_calls_total:,} tool calls"),
        unsafe_allow_html=True,
    )
with k5:
    model_display = (
        top_model.replace("claude-", "").replace("-", " ").title()
        if top_model != "—" else "—"
    )
    st.markdown(
        _kpi("Top Model", model_display, "by token volume"),
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Spend Forecast + Model Cost Simulator
# ---------------------------------------------------------------------------

_sf_col, _ms_col = st.columns([3, 2])

with _sf_col:
    st.markdown('<div class="section-header">Spend Forecast</div>', unsafe_allow_html=True)
    if has_usage and "date" in df_filtered.columns and not df_filtered.empty:
        import numpy as np

        _daily_cost = (
            df_filtered.groupby("date")["cost_usd"].sum().reset_index()
        )
        _daily_cost["date"] = pd.to_datetime(_daily_cost["date"])
        _daily_cost = _daily_cost.sort_values("date")

        if len(_daily_cost) >= 3:
            _x = np.arange(len(_daily_cost), dtype=float)
            _y = _daily_cost["cost_usd"].values.astype(float)
            _coeffs = np.polyfit(_x, _y, 1)
            _slope, _intercept = float(_coeffs[0]), float(_coeffs[1])
            _y_pred = _slope * _x + _intercept
            _ss_res = float(np.sum((_y - _y_pred) ** 2))
            _ss_tot = float(np.sum((_y - _y.mean()) ** 2))
            _r = float(np.sqrt(1 - _ss_res / _ss_tot)) if _ss_tot > 0 else 0.0

            _today_dt = pd.Timestamp.today().normalize()
            _last_date = _daily_cost["date"].max()
            _days_since_last = (_today_dt - _last_date).days
            _days_to_sunday = (6 - _today_dt.weekday()) % 7 or 7
            _days_to_month_end = (
                (_today_dt.replace(day=1) + pd.offsets.MonthEnd(1)) - _today_dt
            ).days

            def _proj(n_days: int) -> float:
                future_x = len(_daily_cost) + _days_since_last + n_days
                return max(0.0, _intercept + _slope * future_x)

            _eow_cost = sum(_proj(d) for d in range(_days_to_sunday + 1))
            _eom_cost = sum(_proj(d) for d in range(_days_to_month_end + 1))
            _avg_daily = float(_y.mean())
            _trend_icon = "↑" if _slope > 0.01 else "↓" if _slope < -0.01 else "→"
            _trend_color = "#dc2626" if _slope > 0.01 else "#16A34A" if _slope < -0.01 else TEXT_MUTED

            st.markdown(
                f"""<div style="background:{SURFACE};border:1px solid {BORDER};
                border-left:4px solid {PRIMARY};border-radius:8px;padding:14px 18px;">
                <div style="display:flex;gap:24px;flex-wrap:wrap;">
                  <div>
                    <div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Avg/Day</div>
                    <div style="color:{TEXT};font-size:1.2rem;font-weight:700;">{format_cost(_avg_daily)}</div>
                  </div>
                  <div>
                    <div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">By Sunday</div>
                    <div style="color:{TEXT};font-size:1.2rem;font-weight:700;">{format_cost(_eow_cost)}</div>
                  </div>
                  <div>
                    <div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">By Month End</div>
                    <div style="color:{TEXT};font-size:1.2rem;font-weight:700;">{format_cost(_eom_cost)}</div>
                  </div>
                  <div>
                    <div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">Trend</div>
                    <div style="color:{_trend_color};font-size:1.2rem;font-weight:700;">{_trend_icon} {"+" if _slope > 0 else ""}{format_cost(_slope)}/day</div>
                  </div>
                </div>
                <div style="color:{TEXT_MUTED};font-size:0.72rem;margin-top:8px;">
                  Linear regression · R²={_r**2:.2f} · {len(_daily_cost)} days of data
                </div></div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("Need ≥ 3 days of data for forecast.")
    else:
        st.info("No usage data.")

with _ms_col:
    st.markdown('<div class="section-header">Model Cost Simulator</div>', unsafe_allow_html=True)
    if has_usage and not df_filtered.empty:
        from pricing import PRICING, calculate_cost as _calc_cost

        _sim_model = st.selectbox(
            "Simulate with model",
            options=list(PRICING.keys()),
            index=list(PRICING.keys()).index("claude-haiku-4-5"),
            key="sim_model",
        )
        # Recalculate cost using simulated model for all rows
        _sim_cost = df_filtered.apply(
            lambda row: _calc_cost(
                {
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_creation_input_tokens": row.get("cache_creation_tokens", 0),
                    "cache_read_input_tokens": row.get("cache_read_tokens", 0),
                },
                _sim_model,
            ),
            axis=1,
        ).sum()
        _actual_cost = df_filtered["cost_usd"].sum()
        _diff = _sim_cost - _actual_cost
        _diff_pct = (_diff / _actual_cost * 100) if _actual_cost > 0 else 0
        _diff_color = "#dc2626" if _diff > 0 else "#16A34A"
        _arrow = "▲" if _diff > 0 else "▼"
        _sim_label = _sim_model.replace("claude-", "").replace("-", " ").title()

        st.markdown(
            f"""<div style="background:{SURFACE};border:1px solid {BORDER};
            border-left:4px solid {'#16A34A' if _diff < 0 else '#f59e0b'};
            border-radius:8px;padding:14px 18px;">
            <div style="color:{TEXT_MUTED};font-size:0.75rem;margin-bottom:6px;">
              If you used <strong style="color:{TEXT};">{_sim_label}</strong> instead:
            </div>
            <div style="font-size:1.6rem;font-weight:700;color:{TEXT};">{format_cost(_sim_cost)}</div>
            <div style="color:{_diff_color};font-size:0.85rem;font-weight:600;margin-top:4px;">
              {_arrow} {format_cost(abs(_diff))} ({abs(_diff_pct):.1f}%)
              {"more" if _diff > 0 else "saved"} vs actual {format_cost(_actual_cost)}
            </div></div>""",
            unsafe_allow_html=True,
        )
    else:
        st.info("No usage data.")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Token Trend
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Token Trend Over Time</div>', unsafe_allow_html=True)

if has_usage and "date" in df_filtered.columns and not df_filtered.empty:
    trend = (
        df_filtered.groupby("date")
        .agg(
            input_tokens=("input_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
            cache_tokens=("cache_creation_tokens", "sum"),
        )
        .reset_index()
    )
    trend["date"] = pd.to_datetime(trend["date"])

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend["date"], y=trend["input_tokens"],
        name="Input", mode="lines+markers",
        line=dict(color=PRIMARY, width=2),
        fill="tozeroy", fillcolor=f"rgba(64,126,60,{'0.15' if dark else '0.08'})",
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend["date"], y=trend["output_tokens"],
        name="Output", mode="lines+markers",
        line=dict(color=ACCENT, width=2),
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend["date"], y=trend["cache_tokens"],
        name="Cache Create", mode="lines",
        line=dict(color="#94c990", width=1.5, dash="dot"),
    ))
    fig_trend.update_layout(
        margin=dict(l=0, r=0, t=8, b=0),
        height=260,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=TEXT)),
        xaxis_title=None,
        yaxis_title="Tokens",
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=BG,
        font=dict(family="Poppins", color=TEXT),
        yaxis=dict(gridcolor=GRID, color=TEXT),
        xaxis=dict(gridcolor=GRID, color=TEXT),
    )
    st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "modeBarButtonsToRemove": ["sendDataToCloud"]})
else:
    st.info("No usage data for selected filters.")

# ---------------------------------------------------------------------------
# Activity Heatmap — GitHub-style daily token calendar
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Activity Heatmap</div>', unsafe_allow_html=True)

if has_usage and "date" in df_filtered.columns and not df_filtered.empty:
    _heat_daily = (
        df_filtered.groupby("date")["total_tokens"]
        .sum()
        .reset_index()
    )
    _heat_daily["date"] = pd.to_datetime(_heat_daily["date"])
    _heat_daily["dow"] = _heat_daily["date"].dt.dayofweek          # 0=Mon … 6=Sun
    _heat_daily["week_idx"] = (
        (_heat_daily["date"] - _heat_daily["date"].min()).dt.days // 7
    )
    _heat_daily["date_str"] = _heat_daily["date"].dt.strftime("%Y-%m-%d")

    _n_weeks = int(_heat_daily["week_idx"].max()) + 1
    _heat_z   = [[None] * _n_weeks for _ in range(7)]
    _heat_txt = [[""] * _n_weeks for _ in range(7)]
    for _, r in _heat_daily.iterrows():
        d, w = int(r["dow"]), int(r["week_idx"])
        _heat_z[d][w] = int(r["total_tokens"])
        _heat_txt[d][w] = f"{r['date_str']}<br>{int(r['total_tokens']):,} tokens"

    _day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig_heat = go.Figure(go.Heatmap(
        z=_heat_z,
        text=_heat_txt,
        hovertemplate="%{text}<extra></extra>",
        x=list(range(_n_weeks)),
        y=_day_labels,
        colorscale=[
            [0.0,  BG_SECONDARY],
            [0.01, "#1a3d19"],
            [0.25, "#2d6e28"],
            [0.55, PRIMARY],
            [0.80, ACCENT],
            [1.0,  "#94c990"],
        ],
        showscale=True,
        colorbar=dict(
            title=dict(text="Tokens", font=dict(color=TEXT, size=11)),
            tickfont=dict(color=TEXT, size=10),
            thickness=12,
        ),
        xgap=3,
        ygap=3,
    ))
    fig_heat.update_layout(
        margin=dict(l=0, r=60, t=8, b=0),
        height=170,
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font=dict(family="Poppins", color=TEXT),
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(color=TEXT, tickfont=dict(size=11), autorange="reversed",
                   showgrid=False, zeroline=False),
    )
    st.plotly_chart(fig_heat, use_container_width=True,
                    config={"displayModeBar": False})
else:
    st.info("No data for heatmap.")

# ---------------------------------------------------------------------------
# Project breakdown + Prompt type pie
# ---------------------------------------------------------------------------

col_bar, col_pie = st.columns([3, 2])

with col_bar:
    st.markdown('<div class="section-header">Top Projects by Token Usage</div>', unsafe_allow_html=True)
    if has_usage and not df_filtered.empty:
        proj_agg = (
            df_filtered.groupby("project_name")["total_tokens"]
            .sum()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
        )
        fig_bar = px.bar(
            proj_agg, x="total_tokens", y="project_name", orientation="h",
            labels={"total_tokens": "Tokens", "project_name": "Project"},
            color_discrete_sequence=[PRIMARY],
        )
        fig_bar.update_layout(
            margin=dict(l=0, r=0, t=8, b=0),
            height=300,
            plot_bgcolor=PLOT_BG,
            paper_bgcolor=BG,
            font=dict(family="Poppins", color=TEXT),
            xaxis=dict(gridcolor=GRID, color=TEXT),
            yaxis=dict(color=TEXT),
            yaxis_title=None,
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "modeBarButtonsToRemove": ["sendDataToCloud"]})
    else:
        st.info("No project data.")

with col_pie:
    st.markdown('<div class="section-header">Prompts by Type</div>', unsafe_allow_html=True)
    if has_history and not df_hist_filtered.empty:
        type_counts = df_hist_filtered["prompt_type"].value_counts().reset_index()
        type_counts.columns = ["type", "count"]
        fig_pie = px.pie(
            type_counts, names="type", values="count", hole=0.45,
            color_discrete_sequence=[
                "#407E3C", "#5a9e56", "#94c990", "#c3ddbf",
                "#1a3d19", "#6BAF67", "#d4edda",
            ],
        )
        fig_pie.update_layout(
            margin=dict(l=0, r=0, t=8, b=0),
            height=300,
            paper_bgcolor=BG,
            font=dict(family="Poppins", color=TEXT),
            legend=dict(font=dict(color=TEXT)),
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "modeBarButtonsToRemove": ["sendDataToCloud"]})
    else:
        st.info("No prompt type data.")

# ---------------------------------------------------------------------------
# Token Cost by Source — the "what eats your tokens" section
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">What Eats Your Tokens</div>', unsafe_allow_html=True)
st.caption("Breakdown of every token consumer across your Claude Code sessions")

if has_usage and has_history:

    # Compute safe_total once — reused across all proportional cost calculations
    _safe_total = df_filtered["total_tokens"].where(df_filtered["total_tokens"] != 0, 1)

    # 1. Prompts — input tokens from main (non-subagent) sessions
    main_df = df_filtered[df_filtered["source"] == "main"]
    prompt_tokens = int(main_df["input_tokens"].sum())
    _main_safe_total = main_df["total_tokens"].where(main_df["total_tokens"] != 0, 1)
    prompt_cost = main_df["cost_usd"].sum() * (
        main_df["input_tokens"].sum() / _main_safe_total.sum()
        if main_df["total_tokens"].sum() > 0 else 0
    )

    # 2. Skills / commands — sessions triggered by /slash commands
    skill_session_ids = set(
        df_history[df_history["prompt_type"] == "skill/command"]["sessionId"].unique()
    )
    skill_df = df_filtered[df_filtered["sessionId"].isin(skill_session_ids)]
    skill_tokens = int(skill_df["total_tokens"].sum())
    skill_cost = skill_df["cost_usd"].sum()

    # 3. CLAUDE.md context — cache_creation tokens (context window load per session)
    claude_md_tokens = int(df_filtered["cache_creation_tokens"].sum())
    claude_md_cost = (
        (df_filtered["cache_creation_tokens"] / _safe_total)
        * df_filtered["cost_usd"]
    ).sum()

    # 4. Sub-agents
    subagent_df = df_filtered[df_filtered["source"] == "subagent"]
    subagent_tok = int(subagent_df["total_tokens"].sum())
    subagent_cost = subagent_df["cost_usd"].sum()
    subagent_count = subagent_df["sessionId"].nunique()

    # 5. Pasted content — prompts with pastedContents
    _has_pasted_col = "has_pasted" in df_history.columns
    pasted_df = df_history[df_history["has_pasted"]] if _has_pasted_col else df_history.iloc[:0]
    pasted_prompt_count = len(pasted_df)
    pasted_chars = int(pasted_df["pasted_chars"].sum()) if "pasted_chars" in pasted_df.columns else 0
    # Rough token estimate: ~4 chars per token
    pasted_est_tokens = pasted_chars // 4

    # 6. Tool calls — count of tool_use blocks fired
    tool_calls_count = int(df_filtered["tool_use_count"].sum())
    # Output tokens roughly proportional to tool call share
    tool_call_cost_est = df_filtered["cost_usd"].sum() * 0.12  # rough: ~12% of cost driven by tool outputs

    # 7. Context carryover — cache_read tokens (context re-fed each turn)
    cache_read_tokens = int(df_filtered["cache_read_tokens"].sum())
    cache_read_cost = (
        (df_filtered["cache_read_tokens"] / _safe_total)
        * df_filtered["cost_usd"]
    ).sum()

    # 8. Output / code written
    output_tokens = int(df_filtered["output_tokens"].sum())
    output_cost = (
        (df_filtered["output_tokens"] / _safe_total)
        * df_filtered["cost_usd"]
    ).sum()

    sources = [
        ("Prompts (User Text)",    f"{prompt_tokens:,} tokens",     format_cost(prompt_cost),
         "Direct user messages fed as input"),
        ("Skills / Commands",      f"{skill_tokens:,} tokens",      format_cost(skill_cost),
         f"Sessions triggered by /slash commands ({len(skill_session_ids)} sessions)"),
        ("CLAUDE.md Context",      f"{claude_md_tokens:,} tokens",  format_cost(claude_md_cost),
         "Cache-creation overhead from loading CLAUDE.md + system context each session"),
        ("Sub-agents",             f"{subagent_tok:,} tokens",      format_cost(subagent_cost),
         f"Parallel agent calls spawned within sessions ({subagent_count} agent sessions)"),
        ("Pasted Content",         f"~{pasted_est_tokens:,} est. tokens", "—",
         f"{pasted_prompt_count} prompts with pasted text · {pasted_chars:,} chars total"),
        ("Tool Calls",             f"{tool_calls_count:,} calls",   format_cost(tool_call_cost_est),
         "Bash, Read, Write, Grep, Edit executions — each call re-feeds results as context"),
        ("Context Carryover",      f"{cache_read_tokens:,} tokens", format_cost(cache_read_cost),
         "Cached context re-read each turn (prior messages + tool results accumulate)"),
        ("Output / Code Written",  f"{output_tokens:,} tokens",     format_cost(output_cost),
         "Tokens Claude generated — responses, code, plans, docs"),
    ]

    # Stacked bar chart — token volume by source
    source_names = [s[0] for s in sources]
    source_tok_vals = [
        prompt_tokens, skill_tokens, claude_md_tokens, subagent_tok,
        pasted_est_tokens, tool_calls_count * 50,  # rough: avg 50 tokens per tool call result
        cache_read_tokens, output_tokens,
    ]
    colors = [
        "#407E3C", "#5a9e56", "#1a3d19", "#94c990",
        "#6BAF67", "#c3ddbf", "#2d6e28", "#d4edda",
    ]

    fig_src = go.Figure(go.Bar(
        x=source_tok_vals,
        y=source_names,
        orientation="h",
        marker_color=colors,
        text=[f"{v:,}" for v in source_tok_vals],
        textposition="outside",
        textfont=dict(color=TEXT, size=11),
    ))
    fig_src.update_layout(
        margin=dict(l=0, r=80, t=8, b=0),
        height=320,
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=BG,
        font=dict(family="Poppins", color=TEXT),
        xaxis=dict(gridcolor=GRID, color=TEXT, title="Tokens"),
        yaxis=dict(color=TEXT, autorange="reversed"),
    )
    st.plotly_chart(fig_src, use_container_width=True, config={"displayModeBar": True, "displaylogo": False, "modeBarButtonsToRemove": ["sendDataToCloud"]})

    # Detail cards — two rows of 4
    rows = [sources[:4], sources[4:]]
    for row in rows:
        cols = st.columns(4)
        for col, (name, tokens_str, cost_str, desc) in zip(cols, row):
            with col:
                st.markdown(
                    f'<div class="source-card">'
                    f'<div class="source-name">{name}</div>'
                    f'<div class="source-value">{tokens_str}</div>'
                    f'<div class="source-cost">{cost_str}</div>'
                    f'<div class="kpi-sub" style="margin-top:6px;">{desc}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
else:
    st.info("Load some Claude Code sessions first.")

# ---------------------------------------------------------------------------
# Session-Level Cost Breakdown per Project
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Usage Stats (mirrors Claude Code /usage panel)
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Usage Stats</div>', unsafe_allow_html=True)
st.caption("Computed from local JSONL data · Budgets auto-scaled from your historical peak usage")

from datetime import date as _date, timedelta as _td

_today = _date.today()
_week_start = _today - _td(days=_today.weekday())  # Monday
_last_week_start = _week_start - _td(days=7)
_next_monday = _week_start + _td(days=7)
_yesterday = _today - _td(days=1)

# All-time df (not filtered) for usage stats — we want real totals
_all_usage = df_usage[df_usage["source"] == "main"].copy() if has_usage else pd.DataFrame()

# Current session — most recent sessionId by timestamp
_cur_session_tokens = 0
_cur_session_cost = 0
_cur_session_id = "—"
if has_usage and not _all_usage.empty and "timestamp" in _all_usage.columns:
    _latest_ts = _all_usage["timestamp"].max()
    if pd.notna(_latest_ts):
        _cur_sid = _all_usage.loc[_all_usage["timestamp"] == _latest_ts, "sessionId"].iloc[0]
        _cur_sess_df = _all_usage[_all_usage["sessionId"] == _cur_sid]
        _cur_session_tokens = int(_cur_sess_df["total_tokens"].sum())
        _cur_session_cost = _cur_sess_df["cost_usd"].sum()
        _cur_session_id = _cur_sid[:8]

# This week vs last week
_has_date = has_usage and "date" in _all_usage.columns and not _all_usage.empty
_this_week_df  = _all_usage[_all_usage["date"] >= _week_start] if _has_date else pd.DataFrame()
_last_week_df  = _all_usage[(_all_usage["date"] >= _last_week_start) & (_all_usage["date"] < _week_start)] if _has_date else pd.DataFrame()
_week_tokens   = int(_this_week_df["total_tokens"].sum()) if not _this_week_df.empty else 0
_week_cost     = _this_week_df["cost_usd"].sum() if not _this_week_df.empty else 0.0
_lw_tokens     = int(_last_week_df["total_tokens"].sum()) if not _last_week_df.empty else 0
_lw_cost       = _last_week_df["cost_usd"].sum() if not _last_week_df.empty else 0.0

# Today vs yesterday
_today_df      = _all_usage[_all_usage["date"] == _today]     if _has_date else pd.DataFrame()
_yesterday_df  = _all_usage[_all_usage["date"] == _yesterday] if _has_date else pd.DataFrame()
_today_tokens  = int(_today_df["total_tokens"].sum())  if not _today_df.empty else 0
_today_cost    = _today_df["cost_usd"].sum()           if not _today_df.empty else 0.0
_yest_tokens   = int(_yesterday_df["total_tokens"].sum()) if not _yesterday_df.empty else 0

# Data-driven default budgets — 2× historical max so scale makes sense
# Only seed defaults once; user overrides persist in session_state
if has_usage and not _all_usage.empty and _has_date:
    _hist_sess_max   = int(_all_usage.groupby("sessionId")["total_tokens"].sum().max())
    _hist_daily_max  = int(_all_usage.groupby("date")["total_tokens"].sum().max())
    _hist_weekly_max = int(
        _all_usage.set_index("timestamp")
        .resample("W")["total_tokens"].sum().max()
    )
else:
    _hist_sess_max, _hist_daily_max, _hist_weekly_max = 200_000, 1_000_000, 5_000_000

_def_sess_budget   = max(_hist_sess_max * 2,   1_000_000)
_def_daily_budget  = max(_hist_daily_max * 2,  2_000_000)
_def_weekly_budget = max(_hist_weekly_max * 2, 50_000_000)

# Seed session_state defaults only on first load
if "session_token_budget" not in st.session_state:
    st.session_state["session_token_budget"] = _def_sess_budget
if "weekly_token_budget" not in st.session_state:
    st.session_state["weekly_token_budget"] = _def_weekly_budget
if "daily_token_budget" not in st.session_state:
    st.session_state["daily_token_budget"] = _def_daily_budget

# Budget inputs
with st.expander("⚙️ Set Usage Budgets", expanded=False):
    _b1, _b2, _b3 = st.columns(3)
    with _b1:
        session_token_budget = st.number_input(
            "Session token budget", min_value=1_000, max_value=2_000_000_000,
            value=int(st.session_state["session_token_budget"]),
            step=max(1_000, _hist_sess_max // 20), format="%d",
            key="session_token_budget",
            help="Tokens per session. Auto-seeded to 2× your historical session peak."
        )
    with _b2:
        weekly_token_budget = st.number_input(
            "Weekly token budget", min_value=100_000, max_value=10_000_000_000,
            value=int(st.session_state["weekly_token_budget"]),
            step=max(100_000, _hist_weekly_max // 20), format="%d",
            key="weekly_token_budget",
        )
    with _b3:
        daily_token_budget = st.number_input(
            "Daily token budget", min_value=10_000, max_value=2_000_000_000,
            value=int(st.session_state["daily_token_budget"]),
            step=max(10_000, _hist_daily_max // 20), format="%d",
            key="daily_token_budget",
        )

def _usage_row(used: int, total: int, label: str, reset_line: str, delta_tokens: int = 0) -> str:
    """Full-width usage bar matching the Claude Code /usage dialog style."""
    pct = min(used / total * 100, 100) if total > 0 else 0
    bar_color = "#dc2626" if pct >= 90 else "#f59e0b" if pct >= 70 else PRIMARY
    if delta_tokens > 0:
        delta_pct = (used - delta_tokens) / delta_tokens * 100
        arrow = "▲" if delta_pct > 0 else "▼"
        d_color = "#dc2626" if delta_pct > 15 else "#f59e0b" if delta_pct > 0 else "#16A34A"
        delta_badge = (
            f'<span style="background:{d_color}22;color:{d_color};font-size:0.7rem;'
            f'padding:1px 6px;border-radius:4px;margin-left:8px;">'
            f'{arrow} {abs(delta_pct):.0f}% vs prior</span>'
        )
    else:
        delta_badge = ""
    return f"""
    <div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;
                padding:16px 20px;margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;">
        <span style="font-weight:600;color:{TEXT};font-size:0.95rem;">{label}{delta_badge}</span>
        <span style="color:{TEXT_MUTED};font-size:0.85rem;font-weight:500;">{pct:.0f}% used</span>
      </div>
      <div style="background:{BORDER};border-radius:4px;height:14px;overflow:hidden;">
        <div style="background:{bar_color};width:{pct:.1f}%;height:100%;border-radius:4px;
             transition:width 0.5s ease;"></div>
      </div>
      <div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:8px;">
        {used:,} / {total:,} tokens &nbsp;·&nbsp; {reset_line}
      </div>
    </div>"""

# Session start time
_sess_start_str = "—"
if has_usage and not _all_usage.empty and "timestamp" in _all_usage.columns:
    _sess_start_ts = _all_usage[_all_usage["sessionId"] == (_cur_sid if _cur_session_id != "—" else "")]["timestamp"].min()
    if pd.notna(_sess_start_ts):
        _sess_start_str = pd.Timestamp(_sess_start_ts).strftime("%b %d, %H:%M UTC")

st.markdown(
    _usage_row(
        _cur_session_tokens, session_token_budget,
        f"Current session · {_cur_session_id} &nbsp;<span style='color:{TEXT_MUTED};font-size:0.78rem;font-weight:400;'>({format_cost(_cur_session_cost)})</span>",
        f"Started {_sess_start_str} &nbsp;·&nbsp; budget: {session_token_budget:,} tokens",
    ),
    unsafe_allow_html=True,
)
st.markdown(
    _usage_row(
        _week_tokens, weekly_token_budget,
        f"Current week (all models) &nbsp;<span style='color:{TEXT_MUTED};font-size:0.78rem;font-weight:400;'>({format_cost(_week_cost)})</span>",
        f"Resets {_next_monday.strftime('%b %d')} &nbsp;·&nbsp; budget: {weekly_token_budget:,} tokens",
        delta_tokens=_lw_tokens,
    ),
    unsafe_allow_html=True,
)

# Today — compact row below
_today_pct = min(_today_tokens / daily_token_budget * 100, 100) if daily_token_budget > 0 else 0
_today_bar_color = "#dc2626" if _today_pct >= 90 else "#f59e0b" if _today_pct >= 70 else ACCENT
_yest_delta = ""
if _yest_tokens > 0:
    _td_pct = (_today_tokens - _yest_tokens) / _yest_tokens * 100
    _td_arrow = "▲" if _td_pct > 0 else "▼"
    _td_color = "#dc2626" if _td_pct > 15 else "#f59e0b" if _td_pct > 0 else "#16A34A"
    _yest_delta = (
        f'<span style="background:{_td_color}22;color:{_td_color};font-size:0.7rem;'
        f'padding:1px 6px;border-radius:4px;margin-left:8px;">'
        f'{_td_arrow} {abs(_td_pct):.0f}% vs yesterday</span>'
    )
st.markdown(
    f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;'
    f'padding:12px 20px;margin-bottom:10px;display:flex;align-items:center;gap:16px;">'
    f'<div style="flex:0 0 auto;">'
    f'<span style="font-weight:600;color:{TEXT};font-size:0.88rem;">Today{_yest_delta}</span>'
    f'</div>'
    f'<div style="flex:1;background:{BORDER};border-radius:4px;height:10px;overflow:hidden;">'
    f'<div style="background:{_today_bar_color};width:{_today_pct:.1f}%;height:100%;border-radius:4px;transition:width 0.5s ease;"></div>'
    f'</div>'
    f'<div style="flex:0 0 auto;color:{TEXT_MUTED};font-size:0.8rem;">'
    f'{_today_pct:.0f}% &nbsp;·&nbsp; {_today_tokens:,} tokens &nbsp;·&nbsp; {format_cost(_today_cost)}'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.caption("🔒 Percentages vs your budgets (above), not Anthropic rate limits — exact rate-limit % requires a private API")

# ---------------------------------------------------------------------------
# Session Cost Breakdown by Project
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Session Cost Breakdown by Project</div>', unsafe_allow_html=True)

if has_usage and not df_filtered.empty:
    session_agg = (
        df_filtered[df_filtered["source"] == "main"]
        .groupby(["project_name", "sessionId"])
        .agg(
            total_tokens=("total_tokens", "sum"),
            input_tokens=("input_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
            cache_tokens=("cache_creation_tokens", "sum"),
            cost_usd=("cost_usd", "sum"),
            tool_calls=("tool_use_count", "sum"),
            model=("model", "first"),
            date=("timestamp", "min"),
        )
        .reset_index()
    )
    session_agg["date"] = pd.to_datetime(session_agg["date"], utc=True).dt.strftime("%Y-%m-%d")
    session_agg["session_short"] = session_agg["sessionId"].str[:8]

    # Anomaly detection — flag sessions > 2× their project average cost
    _proj_avg = session_agg.groupby("project_name")["cost_usd"].transform("mean")
    session_agg["is_anomaly"] = session_agg["cost_usd"] > (_proj_avg * 2)
    _anomalies = session_agg[session_agg["is_anomaly"]].sort_values("cost_usd", ascending=False)
    if not _anomalies.empty:
        _anom_items = "".join([
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:6px 0;border-bottom:1px solid {BORDER};">'
            f'<span style="color:{TEXT};font-size:0.82rem;">'
            f'🔴 <strong>{r["project_name"]}</strong> · {r["session_short"]}</span>'
            f'<span style="color:#dc2626;font-size:0.82rem;font-weight:600;">'
            f'{format_cost(r["cost_usd"])} &nbsp;'
            f'<span style="color:{TEXT_MUTED};font-weight:400;">({r["cost_usd"]/_proj_avg[r.name]:.1f}× avg)</span>'
            f'</span></div>'
            for _, r in _anomalies.head(5).iterrows()
        ])
        st.markdown(
            f'<div style="background:{"#1a0a0a" if dark else "#fff5f5"};border:1px solid #dc2626;'
            f'border-left:4px solid #dc2626;border-radius:8px;padding:12px 16px;margin-bottom:12px;">'
            f'<div style="font-weight:600;color:#dc2626;font-size:0.85rem;margin-bottom:8px;">'
            f'⚠️ {len(_anomalies)} Anomalous Session{"s" if len(_anomalies)>1 else ""} '
            f'— spending 2× or more above project average</div>'
            f'{_anom_items}</div>',
            unsafe_allow_html=True,
        )

    # Top 12 projects by total cost
    top_projects = (
        session_agg.groupby("project_name")["cost_usd"]
        .sum()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    chart_df = session_agg[session_agg["project_name"].isin(top_projects)].copy()

    # Stacked bar: one bar per project, top-5 sessions shown individually,
    # remainder aggregated into an "other" bucket — caps trace count to ~72
    fig_sess = go.Figure()
    colors = [
        "#407E3C","#5a9e56","#94c990","#c3ddbf","#2d6e28","#6BAF67",
        "#1a3d19","#d4edda","#163A17","#7DBF7E","#0A1F0A","#a8d5a2",
    ]
    _TOP_N_SESSIONS = 5
    proj_session_map = chart_df.groupby("project_name")
    for i, proj in enumerate(top_projects):
        if proj not in proj_session_map.groups:
            continue
        proj_data = proj_session_map.get_group(proj).sort_values("cost_usd", ascending=False)
        top_rows = proj_data.head(_TOP_N_SESSIONS)
        rest = proj_data.iloc[_TOP_N_SESSIONS:]
        color = colors[i % len(colors)]
        for _, row in top_rows.iterrows():
            fig_sess.add_trace(go.Bar(
                name=f"{proj} · {row['session_short']}",
                y=[proj],
                x=[row["cost_usd"]],
                orientation="h",
                marker_color=color,
                hovertemplate=(
                    f"<b>{proj}</b><br>"
                    f"Session: {row['sessionId'][:16]}…<br>"
                    f"Date: {row['date']}<br>"
                    f"Tokens: {int(row['total_tokens']):,}<br>"
                    f"Cost: ${row['cost_usd']:.4f}<br>"
                    f"Tool calls: {int(row['tool_calls'])}<extra></extra>"
                ),
                showlegend=False,
            ))
        if not rest.empty:
            fig_sess.add_trace(go.Bar(
                name=f"{proj} · other",
                y=[proj],
                x=[rest["cost_usd"].sum()],
                orientation="h",
                marker_color=color,
                opacity=0.45,
                hovertemplate=(
                    f"<b>{proj}</b><br>"
                    f"Other sessions: {len(rest)}<br>"
                    f"Combined cost: ${rest['cost_usd'].sum():.4f}<br>"
                    f"Combined tokens: {int(rest['total_tokens'].sum()):,}<extra></extra>"
                ),
                showlegend=False,
            ))

    fig_sess.update_layout(
        barmode="stack",
        margin=dict(l=0, r=0, t=8, b=0),
        height=max(280, len(top_projects) * 36),
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=BG,
        font=dict(family="Poppins", color=TEXT),
        xaxis=dict(gridcolor=GRID, color=TEXT, title="Cost (USD)"),
        yaxis=dict(color=TEXT, autorange="reversed"),
    )
    st.plotly_chart(fig_sess, use_container_width=True,
                    config={"displayModeBar": True, "displaylogo": False,
                            "modeBarButtonsToRemove": ["sendDataToCloud"]})

    # View toggle — by session or grouped by project
    _tbl_col, _dl_col = st.columns([3, 1])
    with _tbl_col:
        _breakdown_view = st.radio(
            "Group by", ["Session", "Project"],
            horizontal=True, key="breakdown_view",
        )
    st.markdown(
        f"<p style='color:{TEXT_MUTED};font-size:0.8rem;margin:0 0 8px;'>"
        "Click column headers to sort · Hover bars for session detail</p>",
        unsafe_allow_html=True,
    )

    if _breakdown_view == "Project":
        # Aggregate session_agg by project
        proj_grouped = (
            session_agg.groupby("project_name")
            .agg(
                sessions=("sessionId", "nunique"),
                total_tokens=("total_tokens", "sum"),
                input_tokens=("input_tokens", "sum"),
                output_tokens=("output_tokens", "sum"),
                cache_tokens=("cache_tokens", "sum"),
                tool_calls=("tool_calls", "sum"),
                cost_usd=("cost_usd", "sum"),
                first_date=("date", "min"),
                last_date=("date", "max"),
            )
            .reset_index()
            .sort_values("cost_usd", ascending=False)
        )
        proj_grouped["avg_cost_per_session"] = proj_grouped["cost_usd"] / proj_grouped["sessions"].clip(lower=1)
        proj_grouped["output_ratio"] = (
            proj_grouped["output_tokens"] / proj_grouped["input_tokens"].replace(0, 1)
        ).round(2)

        display_proj = proj_grouped[[
            "project_name", "sessions", "first_date", "last_date",
            "total_tokens", "output_ratio", "tool_calls",
            "avg_cost_per_session", "cost_usd",
        ]].copy()
        display_proj.columns = [
            "Project", "Sessions", "First Used", "Last Used",
            "Total Tokens", "Output/Input Ratio", "Tool Calls",
            "Avg Cost/Session", "Total Cost (USD)",
        ]

        with _dl_col:
            st.download_button(
                "⬇ Export CSV",
                data=display_proj.to_csv(index=False).encode("utf-8"),
                file_name="project_cost_breakdown.csv",
                mime="text/csv",
                key="dl_proj",
            )

        st.dataframe(
            display_proj,
            use_container_width=True,
            height=380,
            column_config={
                "Project":            st.column_config.TextColumn(width="medium"),
                "Sessions":           st.column_config.NumberColumn(format="%d"),
                "Total Tokens":       st.column_config.NumberColumn(format="%d"),
                "Tool Calls":         st.column_config.NumberColumn(format="%d"),
                "Output/Input Ratio": st.column_config.NumberColumn(format="%.2f",
                                        help="Output tokens ÷ input tokens — higher = more verbose responses"),
                "Avg Cost/Session":   st.column_config.NumberColumn(format="$%.4f"),
                "Total Cost (USD)":   st.column_config.NumberColumn(format="$%.4f"),
            },
        )
        st.caption(
            f"{len(proj_grouped):,} projects · "
            f"most expensive: {proj_grouped.iloc[0]['project_name']} "
            f"({format_cost(proj_grouped.iloc[0]['cost_usd'])})"
        )

    else:
        # Original per-session table
        table_df = session_agg.sort_values("cost_usd", ascending=False).copy()
        table_df["model_short"] = (
            table_df["model"].str.replace("claude-", "").str.replace("-", " ").str.title()
        )
        table_df["flag"] = table_df["is_anomaly"].map({True: "🔴", False: ""})
        display_sess = table_df[[
            "flag", "project_name", "date", "session_short", "model_short",
            "total_tokens", "input_tokens", "output_tokens",
            "cache_tokens", "tool_calls", "cost_usd",
        ]].copy()
        display_sess.columns = [
            "⚠", "Project", "Date", "Session", "Model",
            "Total Tokens", "Input", "Output",
            "Cache Create", "Tool Calls", "Cost (USD)",
        ]

        with _dl_col:
            st.download_button(
                "⬇ Export CSV",
                data=display_sess.to_csv(index=False).encode("utf-8"),
                file_name="session_cost_breakdown.csv",
                mime="text/csv",
                key="dl_sess",
            )

        st.dataframe(
            display_sess,
            use_container_width=True,
            height=360,
            column_config={
                "⚠":            st.column_config.TextColumn(width="small"),
                "Project":      st.column_config.TextColumn(width="medium"),
                "Session":      st.column_config.TextColumn(width="small"),
                "Model":        st.column_config.TextColumn(width="small"),
                "Total Tokens": st.column_config.NumberColumn(format="%d"),
                "Input":        st.column_config.NumberColumn(format="%d"),
                "Output":       st.column_config.NumberColumn(format="%d"),
                "Cache Create": st.column_config.NumberColumn(format="%d"),
                "Tool Calls":   st.column_config.NumberColumn(format="%d"),
                "Cost (USD)":   st.column_config.NumberColumn(format="$%.4f"),
            },
        )
        _anom_count = int(session_agg["is_anomaly"].sum())
        st.caption(
            f"{len(session_agg):,} total sessions · sorted by cost descending"
            + (f" · 🔴 {_anom_count} anomalous session{'s' if _anom_count != 1 else ''}" if _anom_count else "")
        )
else:
    st.info("No session data available.")

# ---------------------------------------------------------------------------
# Prompt Log Table
# ---------------------------------------------------------------------------

_pl_hdr, _pl_dl = st.columns([4, 1])
with _pl_hdr:
    st.markdown('<div class="section-header">Prompt Log</div>', unsafe_allow_html=True)

search_query = st.text_input(
    "Search prompts", placeholder="Type to filter...", key="prompt_search"
)

if has_history and not df_hist_filtered.empty:
    log_df = df_hist_filtered.copy()

    if has_usage:
        usage_per_session = (
            df_filtered.groupby("sessionId")
            .agg(
                session_input=("input_tokens", "sum"),
                session_output=("output_tokens", "sum"),
                session_cost=("cost_usd", "sum"),
                session_tools=("tool_use_count", "sum"),
            )
            .reset_index()
        )
        log_df = log_df.merge(usage_per_session, on="sessionId", how="left")
    else:
        log_df["session_input"] = 0
        log_df["session_output"] = 0
        log_df["session_cost"] = 0.0
        log_df["session_tools"] = 0

    if search_query:
        log_df = log_df[log_df["display"].str.contains(search_query, case=False, na=False)]

    if teaching_toggle:
        log_df["prompt_preview"] = "[hidden — teaching mode]"
        log_df["project"] = "[hidden — teaching mode]"
    else:
        _truncated = log_df["display"].str.len() > 80
        log_df["prompt_preview"] = log_df["display"].str[:80] + _truncated.map({True: "…", False: ""})

    # Pasted indicator
    if "has_pasted" in log_df.columns:
        log_df["pasted"] = log_df["has_pasted"].map({True: "📋", False: ""})
    else:
        log_df["pasted"] = ""

    display_df = log_df[[
        "timestamp", "project", "prompt_type", "prompt_preview", "pasted",
        "session_input", "session_output", "session_tools", "session_cost",
    ]].copy()
    display_df.columns = [
        "Timestamp", "Project", "Type", "Prompt", "Paste",
        "Input Tokens", "Output Tokens", "Tool Calls", "Cost (USD)",
    ]
    display_df["Timestamp"] = display_df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    display_df["Cost (USD)"] = display_df["Cost (USD)"].apply(
        lambda x: format_cost(x) if pd.notna(x) else "—"
    )
    display_df = display_df.sort_values("Timestamp", ascending=False)

    with _pl_dl:
        st.markdown("<br>", unsafe_allow_html=True)
        _export_df = display_df.copy()
        if teaching_toggle:
            _export_df["Prompt"] = "[hidden]"
            _export_df["Project"] = "[hidden]"
        st.download_button(
            "⬇ Export CSV",
            data=_export_df.to_csv(index=False).encode("utf-8"),
            file_name="prompt_log.csv",
            mime="text/csv",
            key="dl_prompts",
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        column_config={
            "Prompt": st.column_config.TextColumn(width="large"),
            "Type":   st.column_config.TextColumn(width="small"),
            "Paste":  st.column_config.TextColumn(width="small"),
            "Input Tokens":  st.column_config.NumberColumn(format="%d"),
            "Output Tokens": st.column_config.NumberColumn(format="%d"),
            "Tool Calls":    st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption(f"Showing {len(display_df):,} prompts · 📋 = contained pasted content")
else:
    st.info("No prompt history found.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    f"<p style='text-align:center;color:{TEXT_MUTED};font-size:0.75rem;'>"
    "Token Usage Dashboard · Claude Code Analytics · "
    "Reads <code>~/.claude/</code> locally · No data leaves your device"
    "</p>",
    unsafe_allow_html=True,
)
