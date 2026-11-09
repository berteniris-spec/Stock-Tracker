---
description: Test, check docs, commit and push the current work to main
allowed-tools: Bash(git status:*), Bash(git branch --show-current), Bash(git checkout -b:*), Bash(git switch -c:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push origin:*), Bash(git rev-parse:*), Bash(ls:*), Bash(scripts/test.sh:*), Bash(python tests/test_*.py), Bash(python tests/ui_smoke.py), Read, Glob, Grep
---

Ship the current work. Stop at the first failure and report it; never work around a failing step.

1. Run `git status -sb` and `git branch --show-current`.
2. Commit directly on `main` (the owner's choice). If you are on another branch, say so and ask before switching.
3. Run `scripts/test.sh --smoke`. If any test fails, stop and report the output. Never skip, disable or loosen a test. Exit 2 means `congress.db` is missing: say the smoke test was not run.
4. Check that `CHANGELOG.md` has a new top entry for this change and that `docs/CONTEXT.md` is refreshed (see `git diff --stat` and `git status`). If either is missing, stop and ask the owner to run the Documenter step.
5. If any of `.claude/settings.json`, `.claude/hooks/`, `.github/workflows/`, `.streamlit/config.toml` or the database schema (`db.py` SCHEMA) changed, tell the owner explicitly before committing.
6. Stage the changed files by name (`git add <paths>`). `git add -A` is fine only after `git status` shows nothing unexpected; never stage `congress.db` (it is git-ignored) or `.claude/settings.local.json`.
7. Commit with a short message about the change. End the message with the attribution lines given in the session instructions; do not hard-code them here.
8. `git push origin <branch>`. Commits and pushes do not prompt (they are allowed in `.claude/settings.json`); force-push and branch deletion are denied there.
9. Stop. Open a PR only if the owner said so in this conversation. Never merge, force-push or delete branches.
10. Report: branch, commit hash, what ran (with results) and what did not run.
