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
        "Protected file. Proceed only if the owner asked for this change."}}

PROTECTED_TEXT = ("congress.db", ".github/workflows/", ".streamlit/config.toml")
WRITE_VERB = re.compile(r"(>|\btee\b|\bsed\s+(-\S+\s+)*-i|\brm\b|\bmv\b|\bcp\b)")


def protected(path, root):
    full = os.path.realpath(os.path.join(root, path))
    root = os.path.realpath(root)
    rel = os.path.relpath(full, root).replace(os.sep, "/")
    return (rel == "congress.db" or rel == ".streamlit/config.toml"
            or rel.startswith(".github/workflows/"))


def main():
    try:
        data = json.load(sys.stdin)
        root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
        tool = data.get("tool_name", "")
        inp = data.get("tool_input") or {}
        if tool == "Bash":
            cmd = inp.get("command", "")
            hit = any(p in cmd for p in PROTECTED_TEXT) and WRITE_VERB.search(cmd)
        else:
            path = inp.get("file_path") or inp.get("notebook_path")
            hit = bool(path) and protected(path, root)
        if hit:
            print(json.dumps(ASK))
    except Exception:
        pass
    sys.exit(0)


main()
