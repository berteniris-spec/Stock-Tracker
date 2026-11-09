#!/usr/bin/env python3
"""PreToolUse hook: ask before touching protected files. Fails open."""
import json
import os
import re
import sys

ASK = {"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason":
        "Protected file (congress.db, workflows, config.toml, or db.py with its schema). Proceed only if the owner asked for this change."}}

PROTECTED_TEXT = ("congress.db", ".github/workflows/", ".streamlit/config.toml")
# A shell command is a write to a protected file only when it redirects INTO it, or tee / sed -i / rm / mv / cp / ln
# has it as a target. Reading it (cp congress.db elsewhere, sqlite3 congress.db "select ...") passes.
_P = r"(?:\S*congress\.db\S*|\S*\.github/workflows/\S*|\S*\.streamlit/config\.toml\S*)"
WRITE_VERB = re.compile(
    r"(?:>>?\s*[\"']?" + _P +
    r"|\btee\b[^|;&\n]*" + _P +
    r"|\bsed\s+(?:-\S+\s+)*-i\S*[^|;&\n]*" + _P +
    r"|\b(?:rm|mv|ln|truncate)\b[^|;&\n]*" + _P +
    r"|\b(?:cp|mv|install)\b[^|;&\n]*\s[\"']?" + _P + r"[\"']?\s*(?:[|;&\n]|$)"
    r"|\bopen\(\s*[\"']\S*(?:congress\.db|\.streamlit/config\.toml)[\"']\s*,\s*[\"'][wa])")
SCHEMA_WORDS = re.compile(r"CREATE\s+(?:TABLE|INDEX|VIEW)|ALTER\s+TABLE|DROP\s+(?:TABLE|INDEX|VIEW)|\bSCHEMA\b|def _migrate|PRAGMA\s+foreign_keys", re.I)


def protected(path, root):
    full = os.path.realpath(os.path.join(root, path))
    root = os.path.realpath(root)
    rel = os.path.relpath(full, root).replace(os.sep, "/")
    return (rel == "congress.db" or rel == ".streamlit/config.toml"
            or rel.startswith(".github/workflows/"))


def schema_edit(path, inp, root):
    """db.py is protected only for edits that touch the schema (CREATE/ALTER/DROP TABLE, SCHEMA, _migrate); other queries pass."""
    if os.path.relpath(os.path.realpath(os.path.join(root, path)), os.path.realpath(root)) != "db.py":
        return False
    if inp.get("content") is not None:                    # a whole-file write can change anything
        return True
    return bool(SCHEMA_WORDS.search(str(inp.get("old_string", "")) + str(inp.get("new_string", ""))
                                    + str(inp.get("edits", ""))))


def shell_write(cmd, root):
    """True when a write verb targets a protected file inside the project (an absolute path elsewhere, e.g. a scratch copy, passes)."""
    root = os.path.realpath(root)
    for m in WRITE_VERB.finditer(cmd):
        toks = re.findall(_P, m.group(0))
        if re.match(r"(?:cp|install)\b", m.group(0)):          # only the destination of a copy is written
            toks = toks[-1:]
        for tok in toks:
            tok = tok.strip("\"';")
            if tok.startswith("/") and not os.path.realpath(tok).startswith(root + os.sep):
                continue
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
        root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
        tool = data.get("tool_name", "")
        inp = data.get("tool_input") or {}
        if tool == "Bash":
            cmd = inp.get("command", "")
            hit = any(p in cmd for p in PROTECTED_TEXT) and shell_write(cmd, root)
        else:
            path = inp.get("file_path") or inp.get("notebook_path")
            hit = bool(path) and (protected(path, root) or schema_edit(path, inp, root))
        if hit:
            print(json.dumps(ASK))
    except Exception:
        pass
    sys.exit(0)


main()
