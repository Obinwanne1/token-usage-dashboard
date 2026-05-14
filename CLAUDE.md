# CLAUDE.md — Token Usage Dashboard

## Project Overview

**Business:** RECI Transport Ltd / AI Consultancy
**Project:** Claude Code Token Usage Dashboard
**Client:** Internal (teaching tool + personal analytics)
**Goal:** Read Claude Code's local `~/.claude/` JSONL files and render a live, auto-refreshing Streamlit dashboard showing token consumption, USD cost, sessions, projects, and prompt history — with no data leaving the device.
**Status:** Production-ready · Actively maintained

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run src/dashboard.py
# Opens at http://localhost:8501
```

To reproduce or extend this dashboard from scratch, run:
```
/build-token-dashboard
```

---

## Design System

**Brand:** RECI Transport Ltd
**Font:** Poppins (Google Fonts)

| Role | Hex | Usage |
|---|---|---|
| Primary | `#407E3C` | Buttons, bars, KPI card top-border |
| Secondary | `#FFFFFF` | Light mode backgrounds |
| Accent | `#5a9e56` | Hover states, highlights |
| Text | `#1A1A1A` | Light mode body |
| Text Muted | `#6B7280` | Captions, sub-labels |
| Error | `#DC2626` | Red alert bars, anomaly flags |
| Success | `#16A34A` | Green trend indicators |

Dark mode: deep forest green palette (`#0A1F0A` → `#163A17`). Toggle in header — re-renders entire CSS block via f-string theme tokens.

---

## Tech Stack

**Frontend + Backend:** Streamlit (single-file web app)
**Data:** pandas DataFrames built from local JSONL files
**Charts:** Plotly (line, bar, pie, heatmap)
**Math:** NumPy (linear regression for Spend Forecast)
**Config:** python-dotenv
**Testing:** pytest
**Run command:** `streamlit run src/dashboard.py`
**Port:** 8501 (Streamlit default)

---

## Architecture

```
src/
├── pricing.py       # Token → USD. PRICING dict + calculate_cost() + format_cost()
├── data_parser.py   # Reads ~/.claude/ JSONL. Loaders + build_dataframes() + mtime cache
└── dashboard.py     # Streamlit UI. All sections rendered top-to-bottom each run.
```

### Data flow

```
~/.claude/history.jsonl          → load_history()      → df_history  (prompts)
~/.claude/sessions/*.json        → load_sessions()     → df_sessions (metadata)
~/.claude/projects/**/*.jsonl    → load_project_usage()→ df_usage    (tokens + cost)
                                   ↓
                              build_dataframes()
                                   ↓
                           load_data_cached()  ← 30s mtime cache
                                   ↓
                            dashboard.py render
```

### Cache strategy

`load_data_cached()` checks mtime of every project subdirectory, not just files. Rebuilds only when something changed. Avoids re-parsing 200MB+ JSONL on every 30s refresh.

---

## Data Sources

| File | Content | Key Fields |
|---|---|---|
| `~/.claude/history.jsonl` | User prompts | `display`, `timestamp` (ms), `sessionId`, `pastedContents` |
| `~/.claude/sessions/*.json` | Session metadata | `sessionId`, `startedAt`, `cwd`, `version`, `entrypoint` |
| `~/.claude/projects/{P}/{S}.jsonl` | Flat sessions (older) | `message.usage.*`, `message.model`, `type`, `timestamp` |
| `~/.claude/projects/{P}/{S}/*.jsonl` | Subfolder sessions (newer) | same |
| `~/.claude/projects/{P}/{S}/subagents/*.jsonl` | Sub-agent calls | same, tracked as `source="subagent"` |

---

## Key Implementation Details

### Prompt classifier (`data_parser.py`)
Regex rule list checked in order — first match wins:
1. `^/` → `skill/command`
2. `plan|implement|architecture|phase` → `planning`
3. `fix|bug|error|traceback|debug` → `debugging`
4. `write|create|function|class|api|code` → `coding`
5. `design|UI|layout|dashboard|style` → `design`
6. `review|check|audit|test` → `review`
7. else → `other`

### Token pricing
Model name: exact match → prefix match → default (sonnet rates). Handles versioned model IDs like `claude-sonnet-4-6-20250514`.

### Anomaly detection
Sessions spending > 2× their project average are flagged 🔴. Detection uses `groupby().transform("mean")` — fully vectorized.

### Budget defaults
On first load, session/weekly/daily budgets are seeded to 2× the user's historical peak. This makes usage bars show meaningful percentages rather than always 100% or 0%.

---

## Environment Variables

```bash
CLAUDE_DATA_DIR=     # Override ~/.claude path (validated as existing directory)
TEACHING_MODE=false  # Hide prompt text + project names in Teaching Mode
```

Both read from `.env` via `python-dotenv`. `.env` is gitignored; `.env.example` is committed.

---

## Security Rules

- `CLAUDE_DATA_DIR` validated with `.resolve()` + `.is_dir()` before use
- All user-derived strings into `unsafe_allow_html` MUST use `html.escape()`
- `errors="ignore"` on file I/O (not `"replace"` which embeds U+FFFD noise into JSON)
- Error boundary around `load_data_cached()` — crash shows friendly `st.error()`, not raw traceback
- `.credentials.json` in `~/.claude/` is never read or displayed

---

## Coding Standards

- PEP8 · `black` format · `snake_case` vars/functions · `PascalCase` classes
- Type hints on all function signatures
- `encoding='utf-8'` on all file I/O
- No magic numbers — use named constants
- No imports inside render path — all at top of file
- No row-by-row `apply()` where vectorized numpy/pandas ops work

---

## Testing

**Runner:** pytest
**Location:** `tests/test_data_parser.py`
**Run:** `pytest tests/ -v`
**Coverage:** pricing math, prompt classifier, project name parser, session loader

Tests use `tmp_path` fixture + `unittest.mock.patch` for file system isolation — no real `~/.claude/` data touched.

---

## Dashboard Sections (in order)

1. Header — title, timestamp, Dark/Teaching toggles, LIVE badge
2. Filters & Display expander — project, type, model, date range, alert threshold
3. Daily Cost Alert — red/green banner
4. KPI Cards (5) — tokens, cost, sessions, prompts, top model
5. Spend Forecast — linear regression, avg/day, by Sunday, by month end
6. Model Cost Simulator — vectorized cost recalc for any model
7. Token Trend — daily line chart (input/output/cache)
8. Activity Heatmap — GitHub-style calendar
9. Top Projects bar chart
10. Prompts by Type donut
11. What Eats Your Tokens — 8 source breakdown cards + stacked bar
12. Usage Stats — session/week/daily progress bars with budgets
13. Session Cost Breakdown — anomaly panel + stacked bar + session/project table toggle + CSV export
14. Prompt Log — searchable, filterable, Teaching Mode aware + CSV export
15. Footer

---

## Reproduce from Scratch

```
/build-token-dashboard
```

This command contains the full architecture spec, implementation rules, pricing tables, and verification checklist needed to build this dashboard in any new project directory.
