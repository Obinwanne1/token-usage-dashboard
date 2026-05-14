# /build-token-dashboard

Reproduce the full Token Usage Dashboard for this project. Read `src/dashboard.py`, `src/data_parser.py`, `src/pricing.py`, and `tests/test_data_parser.py` — then rebuild any missing or broken files to match the architecture described in `README.md` and the global `/build-token-dashboard` command.

Run `pytest tests/` after rebuilding. Verify the dashboard loads with `streamlit run src/dashboard.py`.
