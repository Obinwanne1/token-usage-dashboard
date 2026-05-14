# Claude Code Token Usage Dashboard

A live, auto-refreshing analytics dashboard that reads Claude Code's local data files and visualises every token consumed, USD cost, session, project, and prompt — built entirely by AI using Claude Code.

> **No data leaves your device.** Everything reads directly from `~/.claude/` on your local machine.

---

## What It Does

Claude Code stores a rich log of everything you do — every prompt, every response, every token counted, every tool call fired — in plain JSON files on your computer. This dashboard reads those files and turns them into a live analytics view.

### Dashboard sections

| Section | What you see |
|---|---|
| **KPI Cards** | Total tokens · Est. USD cost · Sessions · Prompts sent · Top model |
| **Spend Forecast** | Linear regression on daily spend — projects avg/day, by Sunday, by month end |
| **Model Cost Simulator** | "What if I used Haiku instead?" — instant vectorized cost recalculation |
| **Token Trend** | Daily line chart of input / output / cache tokens over time |
| **Activity Heatmap** | GitHub-style calendar — see which days you coded most |
| **Top Projects** | Horizontal bar chart of token usage by project |
| **Prompts by Type** | Donut chart: planning / coding / debugging / design / review / skill / other |
| **What Eats Your Tokens** | 8 source cards: prompts, skills, CLAUDE.md context, sub-agents, pasted content, tool calls, context carryover, output |
| **Usage Stats** | Session / week / daily progress bars against your own historical peak budgets |
| **Session Cost Breakdown** | Anomaly detection (🔴 sessions 2× above project average), stacked bar, session/project table toggle, CSV export |
| **Prompt Log** | Full searchable prompt history with type, timestamp, tokens, cost |

---

## Setup

### Requirements

- Python 3.10+
- Claude Code installed and used (data must exist in `~/.claude/`)

### Install

```bash
git clone https://github.com/Obinwanne1/token-usage-dashboard.git
cd token-usage-dashboard
pip install -r requirements.txt
```

### Run

```bash
streamlit run src/dashboard.py
```

Opens at `http://localhost:8501`. Auto-refreshes every 30 seconds.

### Optional configuration

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Point to a different Claude data directory (default: ~/.claude)
CLAUDE_DATA_DIR=

# Hide prompt text and project names in presentation/classroom mode
TEACHING_MODE=false
```

---

## How It Was Built

This dashboard was built in a single Claude Code session using AI-assisted development. Here is exactly how it was designed and why each decision was made.

### The problem

Claude Code generates 200MB+ of local JSONL data but provides no way to explore it. You can run `/usage` in the terminal to see a snapshot, but there is no history, no charts, no cost breakdown by project, and no way to analyse your workflow patterns.

### The data

Claude Code stores everything in `~/.claude/`:

```
~/.claude/
├── history.jsonl              ← Every prompt you typed (408KB, 1,775+ entries)
├── sessions/                  ← Session metadata (29 JSON files)
│   └── {PID}.json
└── projects/                  ← Full conversation logs (208MB+, 333 files)
    └── {PROJECT_FOLDER}/
        └── {SESSION_ID}/
            ├── {UUID}.jsonl   ← Main conversation turns
            └── subagents/
                └── agent-*.jsonl  ← Sub-agent (background agent) calls
```

Each `assistant` message in a `.jsonl` file contains a `message.usage` block:

```json
{
  "type": "assistant",
  "message": {
    "model": "claude-sonnet-4-6",
    "usage": {
      "input_tokens": 45231,
      "output_tokens": 1847,
      "cache_creation_input_tokens": 38200,
      "cache_read_input_tokens": 0
    }
  }
}
```

This is what the dashboard reads to compute token counts and USD costs.

### Architecture decisions

**Why Streamlit?**
Streamlit is the fastest way to build a Python data dashboard. One file, no frontend code, auto-reruns on state change. For a local analytics tool with no users, it is the right tool.

**Why read files directly (not an API)?**
Claude Code does not expose a public API for usage data. The local files are authoritative, always available, and contain more detail than any API would return.

**Why a mtime cache?**
Re-parsing 208MB of JSONL on every 30-second refresh would take 5–10 seconds and spike the CPU. The cache checks file modification times — if nothing changed, it returns the previous result instantly.

**Why pandas + Plotly?**
pandas handles multi-gigabyte DataFrames efficiently with vectorized operations. Plotly renders interactive charts with hover, zoom, and export without any JavaScript. Both integrate natively with Streamlit.

**Why NumPy for the forecast (not scipy)?**
`scipy` is not included in the requirements. `numpy.polyfit` does linear regression with identical results — one less dependency.

### Key technical concepts

#### Token types

| Token type | What it means | Cost tier |
|---|---|---|
| `input_tokens` | Text you sent to Claude (your prompt + conversation history) | Medium |
| `output_tokens` | Text Claude generated (response, code, plans) | High |
| `cache_creation_input_tokens` | Context loaded fresh (CLAUDE.md, system prompt) | Medium-high |
| `cache_read_input_tokens` | Context re-read from cache (prior turns carried forward) | Low |

Understanding cache tokens explains why long sessions get expensive — every turn re-feeds the entire conversation as input.

#### Prompt classification

The classifier uses a regex rule chain. First match wins:

```python
_RULES = [
    (r"^/",                                                  "skill/command"),
    (r"\b(plan|implement|architecture|phase|roadmap)\b",     "planning"),
    (r"\b(fix|bug|error|traceback|debug|issue|broken)\b",    "debugging"),
    (r"\b(write|create|function|class|api|code|script)\b",   "coding"),
    (r"\b(design|UI|UX|layout|dashboard|style|color)\b",     "design"),
    (r"\b(review|check|audit|test|verify|validate)\b",       "review"),
]
```

This lets you see what proportion of your Claude usage is debugging vs planning vs coding.

#### Anomaly detection

Uses pandas `transform("mean")` to compute each project's average session cost, then flags any session spending more than 2× that average:

```python
proj_avg = session_agg.groupby("project_name")["cost_usd"].transform("mean")
session_agg["is_anomaly"] = session_agg["cost_usd"] > (proj_avg * 2)
```

Fully vectorized — no Python loops.

#### Model Cost Simulator

Recalculates what your actual usage would have cost under a different model using vectorized numpy:

```python
_rates = PRICING[selected_model]
sim_cost = (
    df["input_tokens"]            * _rates["input"]        / 1_000_000
    + df["output_tokens"]         * _rates["output"]       / 1_000_000
    + df["cache_creation_tokens"] * _rates["cache_create"] / 1_000_000
    + df["cache_read_tokens"]     * _rates["cache_read"]   / 1_000_000
).sum()
```

No row-by-row `apply()` — the entire DataFrame computes in one numpy operation.

### Security decisions

- **`html.escape()`** wraps all user-derived strings before injection into HTML templates (XSS prevention)
- **`CLAUDE_DATA_DIR`** is validated as an existing directory before use (path traversal prevention)
- **`python-dotenv`** loads `.env` at startup so config actually works
- **Error boundary** wraps the data loader — any parse failure shows a friendly message instead of a Python traceback
- **Teaching Mode** hides prompt text and project names for classroom use — enables live demo without exposing private work

---

## Token Pricing Reference

USD per 1,000,000 tokens (Anthropic published rates, May 2026):

| Model | Input | Output | Cache Read | Cache Create |
|---|---|---|---|---|
| claude-opus-4-6 | $15.00 | $75.00 | $1.50 | $18.75 |
| claude-sonnet-4-6 | $3.00 | $15.00 | $0.30 | $3.75 |
| claude-sonnet-4-5 | $3.00 | $15.00 | $0.30 | $3.75 |
| claude-haiku-4-5 | $0.25 | $1.25 | $0.025 | $0.3125 |

---

## Running Tests

```bash
pytest tests/ -v
```

25 tests covering: token pricing math, prompt classifier (all 7 categories), project name parser, session loader with mocked file system.

---

## Reproduce This Dashboard

This project ships with a Claude Code custom command. In any new project directory, run:

```
/build-token-dashboard
```

Claude will read the full architecture spec embedded in that command and rebuild the entire dashboard from scratch — all three source files, tests, requirements, and config.

---

## Project Structure

```
token-usage-dashboard/
├── src/
│   ├── dashboard.py       # Streamlit app — all 15 sections, ~1,500 lines
│   ├── data_parser.py     # JSONL reader, DataFrame builder, mtime cache
│   └── pricing.py         # Model pricing table + cost calculation
├── tests/
│   └── test_data_parser.py  # 25 unit tests
├── .claude/
│   └── commands/
│       └── build-token-dashboard.md  # Custom command to reproduce this
├── .env.example
├── .gitignore
├── CLAUDE.md              # Technical reference for Claude Code
├── README.md              # This file
└── requirements.txt
```

---

## Built With

| Tool | Role |
|---|---|
| Claude Code (Sonnet 4.6) | AI pair programmer — wrote all code |
| Streamlit 1.56 | Web framework |
| pandas 2.3 | Data processing |
| Plotly 6.7 | Interactive charts |
| NumPy 2.4 | Linear regression |
| python-dotenv | Config management |
| pytest | Testing |

---

*Built by RECI Transport Ltd · Claude Code Analytics · All data stays local*
