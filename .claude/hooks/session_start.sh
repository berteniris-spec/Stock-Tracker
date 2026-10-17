#!/usr/bin/env bash
# SessionStart hook: prepare cloud sessions only. Never fails the session.
[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

cache=.claude/.cache
mkdir -p "$cache" 2>/dev/null

# Dependencies: reinstall only when requirements.txt is newer than the stamp.
if [ ! -f "$cache/deps.stamp" ] || [ requirements.txt -nt "$cache/deps.stamp" ]; then
  if timeout 60 pip install -q -r requirements.txt reportlab >/dev/null 2>&1; then
    touch "$cache/deps.stamp"
    echo "deps: installed"
  else
    echo "deps: install failed or timed out"
  fi
else
  echo "deps: up to date"
fi

# Database: fetch from the data branch unless a fresh copy exists.
if [ -s congress.db ] && [ -n "$(find "$cache/db.stamp" -mmin -720 2>/dev/null)" ]; then
  echo "db: fresh, skipped"
else
  tmp="congress.db.tmp.$$"
  if timeout 60 git fetch -q --depth=1 origin data 2>/dev/null \
     && git show FETCH_HEAD:congress.db > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    mv "$tmp" congress.db && touch "$cache/db.stamp" && echo "db: fetched"
  else
    echo "db: fetch failed, kept existing file if any"
  fi
  rm -f "$tmp" 2>/dev/null
fi

head -n 40 docs/CONTEXT.md 2>/dev/null
exit 0
