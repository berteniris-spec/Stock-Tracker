---
description: Read-only summary of where the project stands (context, branch, open PRs, next step)
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git branch --show-current), Bash(git remote get-url:*), Bash(gh pr list:*), Read, Glob, Grep
---

Make no edits. This command only reads.

1. Read `docs/CONTEXT.md`.
2. Run `git log -10 --oneline`, `git status -sb` and `git branch --show-current`.
3. List open pull requests with `gh pr list`. If `gh` is unavailable, say "PRs not checked".
4. Report, briefly:
   - Current state of the project
   - Branch and uncommitted work
   - Open PRs
   - The next step, taken from "Open work" in `docs/CONTEXT.md`
   - Anything in `docs/CONTEXT.md` that looks stale against the git log or the files (name the line)
