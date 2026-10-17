# Stock-Tracker

Streamlit dashboard joining US congressional trades to committees.

- Roles and the build loop: `AGENTS.md`. Current state and open work: `docs/CONTEXT.md`. Read both first.
- Unit tests: `for t in tests/test_*.py; do python $t; done`
- UI smoke test (needs `congress.db`): `python tests/ui_smoke.py`
- Branch off `main`. Do not merge, force-push or delete branches unless the owner asks.

## Hooks (`.claude/hooks/`, registered in `.claude/settings.json`)
- Session start (cloud only): installs dependencies, fetches `congress.db` from the `data` branch, prints the top of `docs/CONTEXT.md`.
- Before edits: asks for confirmation on protected paths.
- On stop: runs the unit tests if a `.py` file changed (exit 2 on failure) and warns when code changed without a `CHANGELOG.md` entry.

## Protected paths
`congress.db`, `.github/workflows/`, `.streamlit/config.toml`, and the database schema. Change them only when the owner has said so.
