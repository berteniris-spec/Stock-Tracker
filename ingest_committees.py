"""Load members and committee memberships from the congress-legislators repo.

Usage:
    python ingest_committees.py                 # clones the repo into ./.cache/ (needs git + network)
    python ingest_committees.py /path/to/clone  # use an existing clone
Re-running refreshes members/committees/memberships; trades are untouched.
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

import db

REPO = "https://github.com/unitedstates/congress-legislators.git"


def get_repo(arg):
    if arg:
        return Path(arg)
    cache = Path(__file__).with_name(".cache") / "congress-legislators"
    if cache.exists():
        subprocess.run(["git", "-C", str(cache), "pull", "-q"], check=True)
    else:
        cache.parent.mkdir(exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "-q", REPO, str(cache)], check=True)
    return cache


def load(path):
    return yaml.safe_load(open(path, encoding="utf-8"))


def main():
    repo = get_repo(sys.argv[1] if len(sys.argv) > 1 else None)
    legislators = load(repo / "legislators-current.yaml")
    committees = load(repo / "committees-current.yaml")
    membership = load(repo / "committee-membership-current.yaml")
    as_of = date.today().isoformat()

    con = db.connect()
    db.init_db(con)
    with con:
        con.execute("DELETE FROM memberships WHERE bioguide_id IN "
                    "(SELECT bioguide_id FROM members WHERE source='congress-legislators')")
        for p in legislators:
            term = p["terms"][-1]
            name = p["name"].get("official_full") or f"{p['name']['first']} {p['name']['last']}"
            con.execute(
                "INSERT INTO members(bioguide_id, name, chamber, state, party, last_name, first_name, district, source) "
                "VALUES (?,?,?,?,?,?,?,?,'congress-legislators') "
                "ON CONFLICT(bioguide_id) DO UPDATE SET name=excluded.name, chamber=excluded.chamber, "
                "state=excluded.state, party=excluded.party, last_name=excluded.last_name, "
                "first_name=excluded.first_name, district=excluded.district",
                (p["id"]["bioguide"], name,
                 "Senate" if term["type"] == "sen" else "House", term["state"], term["party"],
                 p["name"].get("last"), p["name"].get("first"),
                 term.get("district") if term["type"] == "rep" else None))

        known_members = {r[0] for r in con.execute("SELECT bioguide_id FROM members")}
        for c in committees:
            chamber = {"senate": "Senate", "house": "House", "joint": "Joint"}.get(c["type"], c["type"])
            con.execute("INSERT OR REPLACE INTO committees(id, name, chamber, parent_id) VALUES (?,?,?,NULL)",
                        (c["thomas_id"], c["name"], chamber))
            for s in c.get("subcommittees", []):
                con.execute("INSERT OR REPLACE INTO committees(id, name, chamber, parent_id) VALUES (?,?,?,?)",
                            (c["thomas_id"] + s["thomas_id"], f"{c['name']}: {s['name']}", chamber, c["thomas_id"]))

        known_committees = {r[0] for r in con.execute("SELECT id FROM committees")}
        skipped = 0
        for cid, people in membership.items():
            if cid not in known_committees:
                skipped += len(people)
                continue
            for p in people:
                if p["bioguide"] not in known_members:
                    skipped += 1
                    continue
                con.execute(
                    "INSERT OR REPLACE INTO memberships(bioguide_id, committee_id, title, rank, as_of) "
                    "VALUES (?,?,?,?,?)", (p["bioguide"], cid, p.get("title"), p.get("rank"), as_of))

    n = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"members={n('members')} committees={n('committees')} memberships={n('memberships')} skipped={skipped}")


if __name__ == "__main__":
    main()
