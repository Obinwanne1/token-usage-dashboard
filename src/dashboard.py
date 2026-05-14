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

    # 1. Prompts — input tokens from main (non-subagent) sessions
    main_df = df_filtered[df_filtered["source"] == "main"]
    prompt_tokens = int(main_df["input_tokens"].sum())
    prompt_cost = main_df["cost_usd"].sum() * (
        main_df["input_tokens"].sum() / main_df["total_tokens"].replace(0, 1).sum()
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
    total_tok_sum = df_filtered["total_tokens"].sum()
    claude_md_cost = (
        (df_filtered["cache_creation_tokens"] / df_filtered["total_tokens"].replace(0, 1))
        * df_filtered["cost_usd"]
    ).sum()

    # 4. Sub-agents
    subagent_df = df_filtered[df_filtered["source"] == "subagent"]
    subagent_tok = int(subagent_df["total_tokens"].sum())
    subagent_cost = subagent_df["cost_usd"].sum()
    subagent_count = subagent_df["sessionId"].nunique()

    # 5. Pasted content — prompts with pastedContents
    pasted_df = df_history[df_history.get("has_pasted", pd.Series(False, index=df_history.index))]
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
        (df_filtered["cache_read_tokens"] / df_filtered["total_tokens"].replace(0, 1))
        * df_filtered["cost_usd"]
    ).sum()

    # 8. Output / code written
    output_tokens = int(df_filtered["output_tokens"].sum())
    output_cost = (
        (df_filtered["output_tokens"] / df_filtered["total_tokens"].replace(0, 1))
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
st.caption("Computed from local JSONL data · Set your own budgets below to track limits")

from datetime import date as _date, timedelta as _td
import math as _math

_today = _date.today()
_week_start = _today - _td(days=_today.weekday())  # Monday
_next_monday = _week_start + _td(days=7)

# All-time df (not filtered) for usage stats — we want real totals
_all_usage = df_usage[df_usage["source"] == "main"].copy() if has_usage else pd.DataFrame()

# Current session — most recent sessionId by timestamp
_cur_session_tokens = 0
_cur_session_cost = 0.0
_cur_session_id = "—"
if has_usage and not _all_usage.empty and "timestamp" in _all_usage.columns:
    _latest_ts = _all_usage["timestamp"].max()
    if pd.notna(_latest_ts):
        _cur_sid = _all_usage.loc[_all_usage["timestamp"] == _latest_ts, "sessionId"].iloc[0]
        _cur_sess_df = _all_usage[_all_usage["sessionId"] == _cur_sid]
        _cur_session_tokens = int(_cur_sess_df["total_tokens"].sum())
        _cur_session_cost = _cur_sess_df["cost_usd"].sum()
        _cur_session_id = _cur_sid[:8]

# This week
_this_week_df = _all_usage[_all_usage["date"] >= _week_start] if has_usage and "date" in _all_usage.columns else pd.DataFrame()
_week_tokens = int(_this_week_df["total_tokens"].sum()) if not _this_week_df.empty else 0
_week_cost = _this_week_df["cost_usd"].sum() if not _this_week_df.empty else 0.0

# Today
_today_df = _all_usage[_all_usage["date"] == _today] if has_usage and "date" in _all_usage.columns else pd.DataFrame()
_today_tokens = int(_today_df["total_tokens"].sum()) if not _today_df.empty else 0
_today_cost = _today_df["cost_usd"].sum() if not _today_df.empty else 0.0

# Budget inputs (persisted in session_state)
with st.expander("⚙️ Set Usage Budgets", expanded=False):
    _b1, _b2, _b3 = st.columns(3)
    with _b1:
        session_token_budget = st.number_input(
            "Session token budget", min_value=1000, max_value=2_000_000,
            value=int(st.session_state.get("session_token_budget", 200_000)),
            step=10_000, format="%d", key="session_token_budget",
            help="Max tokens per session (claude-sonnet context window = 200K)"
        )
    with _b2:
        weekly_token_budget = st.number_input(
            "Weekly token budget", min_value=100_000, max_value=500_000_000,
            value=int(st.session_state.get("weekly_token_budget", 5_000_000)),
            step=500_000, format="%d", key="weekly_token_budget",
        )
    with _b3:
        daily_token_budget = st.number_input(
            "Daily token budget", min_value=10_000, max_value=50_000_000,
            value=int(st.session_state.get("daily_token_budget", 1_000_000)),
            step=100_000, format="%d", key="daily_token_budget",
        )

def _pbar(used: int, total: int, label: str, sublabel: str) -> str:
    pct = min(used / total * 100, 100) if total > 0 else 0
    color = "#dc2626" if pct >= 90 else "#f59e0b" if pct >= 70 else PRIMARY
    return f"""
    <div style="margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-weight:600;color:{TEXT};font-size:0.85rem;">{label}</span>
        <span style="color:{TEXT_MUTED};font-size:0.8rem;">{pct:.1f}% used</span>
      </div>
      <div style="background:{BORDER};border-radius:6px;height:10px;overflow:hidden;">
        <div style="background:{color};width:{pct:.1f}%;height:100%;border-radius:6px;
             transition:width 0.4s ease;"></div>
      </div>
      <div style="color:{TEXT_MUTED};font-size:0.75rem;margin-top:3px;">{sublabel}</div>
    </div>"""

_u1, _u2, _u3 = st.columns(3)
with _u1:
    st.markdown(_pbar(
        _cur_session_tokens, session_token_budget,
        f"Current Session · {_cur_session_id}",
        f"{_cur_session_tokens:,} / {session_token_budget:,} tokens · {format_cost(_cur_session_cost)}"
    ), unsafe_allow_html=True)
with _u2:
    st.markdown(_pbar(
        _week_tokens, weekly_token_budget,
        "Current Week (all models)",
        f"{_week_tokens:,} / {weekly_token_budget:,} tokens · {format_cost(_week_cost)} · resets {_next_monday.strftime('%b %d')}"
    ), unsafe_allow_html=True)
with _u3:
    st.markdown(_pbar(
        _today_tokens, daily_token_budget,
        "Today",
        f"{_today_tokens:,} / {daily_token_budget:,} tokens · {format_cost(_today_cost)}"
    ), unsafe_allow_html=True)

st.caption("🔒 Exact Claude.ai rate-limit % requires a private API — set your own budgets above to track limits")

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

    # Top 12 projects by total cost
    top_projects = (
        session_agg.groupby("project_name")["cost_usd"]
        .sum()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    chart_df = session_agg[session_agg["project_name"].isin(top_projects)].copy()

    # Stacked bar: one bar per project, each segment = one session
    fig_sess = go.Figure()
    colors = [
        "#407E3C","#5a9e56","#94c990","#c3ddbf","#2d6e28","#6BAF67",
        "#1a3d19","#d4edda","#163A17","#7DBF7E","#0A1F0A","#a8d5a2",
    ]
    proj_session_map = chart_df.groupby("project_name")
    for i, proj in enumerate(top_projects):
        if proj not in proj_session_map.groups:
            continue
        proj_data = proj_session_map.get_group(proj).sort_values("cost_usd", ascending=False)
        for _, row in proj_data.iterrows():
            fig_sess.add_trace(go.Bar(
                name=f"{proj} · {row['session_short']}",
                y=[proj],
                x=[row["cost_usd"]],
                orientation="h",
                marker_color=colors[i % len(colors)],
                hovertemplate=(
                    f"<b>{proj}</b><br>"
                    f"Session: {row['sessionId'][:16]}…<br>"
                    f"Date: {row['date']}<br>"
                    f"Tokens: {row['total_tokens']:,}<br>"
                    f"Cost: ${row['cost_usd']:.4f}<br>"
                    f"Tool calls: {int(row['tool_calls'])}<extra></extra>"
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

    # Drilldown table
    st.markdown(f"<p style='color:{TEXT_MUTED};font-size:0.8rem;margin:0 0 8px;'>Click column headers to sort · Hover bars for session detail</p>", unsafe_allow_html=True)

    table_df = session_agg.copy()
    table_df = table_df.sort_values("cost_usd", ascending=False)
    table_df["cost_usd_fmt"] = table_df["cost_usd"].apply(format_cost)
    table_df["model_short"] = table_df["model"].str.replace("claude-", "").str.replace("-", " ").str.title()

    display_sess = table_df[[
        "project_name", "date", "session_short", "model_short",
        "total_tokens", "input_tokens", "output_tokens",
        "cache_tokens", "tool_calls", "cost_usd",
    ]].copy()
    display_sess.columns = [
        "Project", "Date", "Session", "Model",
        "Total Tokens", "Input", "Output",
        "Cache Create", "Tool Calls", "Cost (USD)",
    ]

    st.dataframe(
        display_sess,
        use_container_width=True,
        height=360,
        column_config={
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
    st.caption(f"{len(session_agg):,} total sessions · sorted by cost descending")
else:
    st.info("No session data available.")

# ---------------------------------------------------------------------------
# Prompt Log Table
# ---------------------------------------------------------------------------

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
        log_df["prompt_preview"] = log_df["display"].str[:80] + log_df["display"].apply(
            lambda x: "…" if len(str(x)) > 80 else ""
        )

    # Pasted indicator
    if "has_pasted" in log_df.columns:
        log_df["pasted"] = log_df["has_pasted"].apply(lambda x: "📋" if x else "")
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
