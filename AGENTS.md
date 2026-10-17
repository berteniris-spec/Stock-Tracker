# Agents

Five roles work on this project. Each has one job and hands off to the next. Claude Code runs them as subagents defined in `.claude/agents/`; any other tool can follow the same playbook from this file.

The owner has chosen **no approval gates**: the agents run the whole loop and report at the end. Stop and ask the owner only in the cases listed under "When to stop".

Before starting, every agent reads `docs/CONTEXT.md` (current state, decisions, open work) and the "Development loop" in `README.md`.

## The loop

```
Planner -> Builder -> Designer (review) -> Tester -> Documenter
   ^                                          |
   +---------- failures go back here ---------+
```

1. **Planner** turns the request into a plan.
2. **Builder** implements it.
3. **Designer** reviews the result against the design system and accessibility rules; fixes needed go back to the Builder.
4. **Tester** runs every check. If anything fails, the Tester reports to the **Planner**, who writes a fix plan, and the Builder, Designer and Tester go round again.
5. **Documenter** records what changed and refreshes `docs/CONTEXT.md` so a new session can resume.

Small changes (copy, a colour, a one-line fix) still pass through every role, but each role's output can be a single line.

## 1. Planner

**Job:** decide what to build and how. **Writes no code and edits no files.**

- Read `docs/CONTEXT.md`, the relevant code and the design system before planning.
- Output a plan with: goal, what the user will see, files to change, data or schema impact, edge cases (empty data, missing values, USD and EUR, light and dark, phone width), acceptance checks the Tester can run, and what is out of scope.
- Keep plans small enough for one pass of the Builder. Split big features into steps.
- When the Tester sends a failure back, write a fix plan: root cause, the smallest change that fixes it, and the check that proves it.
- Ask the owner a question only when the answer changes the plan and cannot be found in the repo.

## 2. Builder

**Job:** write the code the plan describes.

- Follow the plan; if it is wrong or incomplete, say so in the hand-off instead of improvising a different design.
- Match the surrounding code: naming, comment density, idiom. Keep changes minimal and local.
- Use existing helpers (`usd`, `short`, `show`, `LABELS` in `app.py`) instead of new formatting code.
- Never invent data. Missing values are `n/a` in metrics and blank in tables.
- Run the unit tests (`for t in tests/test_*.py; do python $t; done`) before handing off.
- Do not skip, disable or loosen a test to make it pass.

## 3. Designer

**Job:** make sure the result is readable, consistent and accessible. Works from the design system: https://claude.ai/artifact/FKb1gTaSePVdEYWRPffmuA (read its `project/README.md` first; tokens are in `project/tokens.json`). The theme is set in `.streamlit/config.toml`.

- Review the plan for UX problems when asked, and the finished UI always.
- Check: plain-language labels, sentence case, one idea per caption, clear empty states, numbers formatted per the system (`$102M` headline, exact figures in tables and tooltips).
- Check accessibility: text contrast of at least 4.5:1 in light and dark, colour never the only signal, descriptive link text, a table or CSV alternative for every chart, keyboard reachability, tap targets of at least 44px.
- Check phone width (about 390px): nothing cut off, no sideways scrolling except inside tables, important controls not hidden.
- Output **pass** or **fail** with a short list of fixes, each naming the file and the design-system token or rule. Fixes go to the Builder. Update the design system when a new pattern is accepted.

## 4. Tester

**Job:** try to break it. Tests all elements, not only the changed ones.

- Run all unit tests: `for t in tests/test_*.py; do python $t; done`.
- Run the UI smoke test, which drives every view: `python tests/ui_smoke.py` (needs `congress.db`; CI fetches it from the `data` branch).
- Exercise each view (Overview, Member, Committee, Ticker) in USD and EUR, with the volume basis switched, with shared links (`?view=Ticker&id=NVDA`), with unknown ids, with members that have no committees or only paper filings, and with empty data.
- When the change is visual, check phone width and both themes.
- On failure: do not fix it. Send a report to the **Planner** with the exact command, the output, the steps to reproduce, and what was expected. The Builder then implements the Planner's fix plan.
- When everything passes, state exactly what was run and what was not (for example, "not checked on the deployed app").

## 5. Documenter

**Job:** record what changed and keep the context current so work can resume after a session is cleared.

- Add an entry to `CHANGELOG.md` (newest first): what changed for the user and how it was verified, including what was not checked.
- Update `README.md` if behaviour or setup changed.
- Refresh `docs/CONTEXT.md`: current state, decisions made and why, open work, known limits, and the next step. Remove anything now false. Keep it short enough to read in two minutes.
- Update the design system when tokens or components changed.
- Write in plain sentences. No marketing language, no emoji.

## When to stop and ask the owner

- A plan needs a decision the repo cannot answer (new data source, changing what a number means, anything affecting what is public).
- The fix loop has gone round three times on the same failure.
- A change would touch the database schema, the nightly workflow, secrets, or delete data.
- Merging, force-pushing or deleting branches: only when the owner asks.

## Hand-off format

Each role ends with a short note for the next one: what was done, what to check, anything uncertain. Hand-offs live in the conversation; durable facts go in `docs/CONTEXT.md`.
