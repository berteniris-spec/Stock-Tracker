#!/usr/bin/env bash
# Wait for the newest CI run on main and print its result and log annotations.
# Usage: scripts/wait_ci.sh [workflow-file, default ci.yml]   (needs gh, authenticated)
set -u
REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]##; s#\.git$##')
WF=${1:-ci.yml}
sleep 15
RUN=$(gh api "repos/$REPO/actions/workflows/$WF/runs?per_page=1" -q '.workflow_runs[0].id')
for _ in $(seq 1 60); do
  st=$(gh api "repos/$REPO/actions/runs/$RUN" -q '.status+" "+(.conclusion//"")')
  case "$st" in completed*) break;; esac
  sleep 15
done
echo "run $RUN: $st"
JOB=$(gh api "repos/$REPO/actions/runs/$RUN/jobs" -q '.jobs[0].id')
gh api "repos/$REPO/check-runs/$JOB/annotations" -q '.[]|select(.message|test("Node.js 20|ubuntu-latest")|not)|.title+": "+.message' | head -${LINES_MAX:-60}
case "$st" in *success*) exit 0;; *) exit 1;; esac
