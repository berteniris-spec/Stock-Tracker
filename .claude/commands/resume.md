---
description: Read-only summary of where the project stands (context, branch, open PRs, next step)
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git branch --show-current), Bash(git remote get-url:*), Read, Glob, Grep
---

Make no edits. This command only reads.

1. Read `docs/CONTEXT.md`.
2. Run `git log -10 --oneline`, `git status -sb` and `git branch --show-current`.
3. If GitHub tools are available, list open pull requests (take owner/repo from `git remote get-url origin`). Otherwise say "PRs not checked".
4. Report, briefly:
   - Current state of the project
   - Branch and uncommitted work
   - Open PRs
   - The next step, taken from "Open work" in `docs/CONTEXT.md`
   - Anything in `docs/CONTEXT.md` that looks stale against the git log or the files (name the line)
