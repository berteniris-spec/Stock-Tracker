---
description: Test, check docs, commit and push the current work on a branch (never on main)
allowed-tools: Bash(git status:*), Bash(git branch --show-current), Bash(git checkout -b:*), Bash(git switch -c:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push -u origin:*), Bash(git rev-parse:*), Bash(ls:*), Bash(python tests/test_*.py), Bash(python tests/ui_smoke.py), Read, Glob, Grep
---

Ship the current work. Stop at the first failure and report it; never work around a failing step.

1. Run `git status -sb` and `git branch --show-current`.
2. If the branch is `main`, create a short kebab-case branch for the change (`git checkout -b <name>`). Never commit on `main`.
3. Run the unit tests as separate commands: `ls tests/test_*.py`, then `python tests/<file>` for each file. If any fail, stop and report the output. Never skip, disable or loosen a test.
4. Run `python tests/ui_smoke.py` only if `congress.db` exists. If it does not, say the smoke test was not run.
5. Check that `CHANGELOG.md` has a new top entry for this change and that `docs/CONTEXT.md` is refreshed (see `git diff --stat` and `git status`). If either is missing, stop and ask the owner to run the Documenter step.
6. If any of `.claude/settings.json`, `.claude/hooks/`, `.github/workflows/`, `.streamlit/config.toml` or the database schema (`db.py` SCHEMA) changed, tell the owner explicitly before committing.
7. Stage files by name. Never use `git add -A` or `git add .`, and never stage `congress.db`.
8. Commit with a short message about the change. End the message with the attribution lines given in the session instructions; do not hard-code them here.
9. `git push -u origin <branch>`.
10. Stop. Open a PR only if the owner said so in this conversation. Never merge, force-push or delete branches.
11. Report: branch, commit hash, what ran (with results) and what did not run.
