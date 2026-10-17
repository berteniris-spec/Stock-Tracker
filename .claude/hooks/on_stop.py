#!/usr/bin/env python3
"""Stop hook: run unit tests when Python changed; nudge about CHANGELOG. Fails open."""
import json
import os
import subprocess
import sys

CODE_SUFFIXES = (".py", ".toml", ".yml")


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True,
                       text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r.stdout


def changed_files(root):
    files = set()
    for line in git(root, "status", "--porcelain", "-uall").splitlines():
        name = line[3:].split(" -> ")[-1].strip().strip('"')
        if name:
            files.add(name)
    files.update(n for n in git(root, "diff", "--name-only", "HEAD").splitlines() if n)
    return files


def main():
    try:
        try:
            data = json.load(sys.stdin)
        except Exception:
            data = {}
        if data.get("stop_hook_active"):
            sys.exit(0)
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        files = changed_files(root)
    except Exception:
        sys.exit(0)

    if any(f.endswith(".py") for f in files):
        try:
            r = subprocess.run(
                ["bash", "-c", 'for t in tests/test_*.py; do python "$t" || exit 1; done'],
                cwd=root, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                out = (r.stdout + r.stderr).strip().splitlines()[-40:]
                print("Unit tests failed:\n" + "\n".join(out), file=sys.stderr)
                sys.exit(2)
        except subprocess.TimeoutExpired:
            pass

    code = any(f.endswith(CODE_SUFFIXES) or os.path.basename(f) == "requirements.txt"
               for f in files)
    if code and "CHANGELOG.md" not in files:
        print(json.dumps({"systemMessage":
                          "Code changed but CHANGELOG.md was not updated."}))
    sys.exit(0)


main()
