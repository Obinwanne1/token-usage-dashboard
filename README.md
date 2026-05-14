# Token Usage Dashboard

Live, auto-refreshing dashboard that reads Claude Code's local JSONL logs and surfaces token usage, cost estimates, project breakdowns, and prompt history.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run src/dashboard.py
```

Opens at `http://localhost:8501`. Auto-refreshes every 30 seconds.

## Environment

Copy `.env.example` to `.env`. Both vars are optional:

| Var | Default | Purpose |
|---|---|---|
| `CLAUDE_DATA_DIR` | `~/.claude` | Override Claude Code data location |
| `TEACHING_MODE` | `false` | Set `true` to truncate prompt previews in class demos |

## Data Sources

Reads directly from Claude Code's local files — no API key needed:

- `~/.claude/history.jsonl` — user prompt history
- `~/.claude/sessions/*.json` — session metadata
- `~/.claude/projects/**/*.jsonl` — full conversations with token counts

## Stack

Python · Streamlit · Plotly · Pandas
