# -*- coding: utf-8 -*-
"""Read the survey answers back, next to what the tracker currently says.

    python scripts/survey_pull.py                  every answer, newest first
    python scripts/survey_pull.py --disagree       only where we and they differ
    python scripts/survey_pull.py --csv answers.csv

This prints and nothing else. It does not touch data/programs.json.

That is the whole point of it. An answer is a statement a named person made
about their own program; a line on a program page is a statement the site
makes to applicants. The tracker's rule is that every such statement traces to
a source a reader can check, and "a director told us in an email" is a good
source -- but only once a person has read it, decided what the entry should
say, and written the sentence. A script that flipped statuses automatically
would put claims about real people's labs on the site that nobody had read.

So this sorts the answers into the three piles that need different work:

  Disagrees   they said something the tracker contradicts. Read these first;
              each one is either a correction to make or a question to ask.
  Confirms    they said what the entry already says. Nothing to do, and that
              is worth seeing -- it is the evidence the tracker is accurate.
  New         they answered where the entry had nothing, mostly "pending"
              programs saying yes or no. These are the additions.

An unanswered program appears nowhere. Silence is not a "no", and a program
must never be moved to closed because its director ignored an email.

Needs NOTIFY_SECRET, the same one the notifier uses.
"""
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROGRAMS = os.path.join(SITE, "data", "programs.json")
ENDPOINT = "https://spare.theclinicalperspective.org/api/survey/responses"

ANSWER_WORDS = {"yes": "admitting", "no": "not admitting",
                "undecided": "not decided yet"}


def secret():
    from_env = os.environ.get("NOTIFY_SECRET")
    if from_env:
        return from_env
    path = os.path.join(SITE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, _, value = line.partition("=")
            if key.strip() == "NOTIFY_SECRET":
                return value.strip().strip('"').strip("'")
    return None


def fetch(cycle):
    key = secret()
    if not key:
        raise SystemExit("NOTIFY_SECRET is not set, in the environment or "
                         "Website/.env.")
    url = ENDPOINT + (f"?cycle={urllib.parse.quote(cycle)}" if cycle else "")
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["responses"]
    except urllib.error.HTTPError as err:
        raise SystemExit(f"{ENDPOINT} returned {err.code}: "
                         f"{err.read().decode('utf-8', 'replace')[:200]}")


def latest(responses):
    """One answer per program per person, keeping the most recent.

    The table is append-only so a director can correct themselves, which means
    the raw rows can hold both answers. The newest is what they think now.
    The endpoint returns newest first, so the first one seen wins."""
    seen, out = set(), []
    for r in responses:
        keyed = (r.get("cycle"), r.get("programId"), r.get("email"))
        if keyed in seen:
            continue
        seen.add(keyed)
        out.append(r)
    return out


def verdict(answer, program):
    """Which pile this answer belongs in, and why in one phrase.

    "posted" and "cohort" both mean the program is admitting as far as the
    tracker is concerned -- a cohort-model program still takes students, it
    just does not assign them to a named lab up front. So a "yes" against
    either is a confirmation, not news."""
    status = program["status"]
    admitting = status in ("posted", "cohort")

    if answer == "yes":
        if admitting:
            return "confirms", f"entry already shows admitting ({status})"
        if status == "closed":
            return "disagrees", "entry says closed this cycle"
        return "new", "entry had nothing posted yet"
    if answer == "no":
        if status == "closed":
            return "confirms", "entry already says closed"
        if admitting:
            n = len(program.get("accepting") or [])
            return "disagrees", (f"entry shows {status}"
                                 + (f" with {n} faculty listed" if n else ""))
        return "new", "entry had nothing posted yet"
    # undecided
    if status == "pending":
        return "confirms", "entry already says not posted yet"
    if admitting:
        return "disagrees", f"entry shows {status}"
    return "new", f"entry says {status}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", help="default: the cycle in programs.json")
    ap.add_argument("--disagree", action="store_true",
                    help="only the answers that contradict the tracker")
    ap.add_argument("--csv", metavar="PATH", help="also write a spreadsheet")
    args = ap.parse_args()

    data = json.load(open(PROGRAMS, encoding="utf-8"))
    cycle = args.cycle or data.get("cycle")
    programs = {p["id"]: p for p in data["programs"]}

    rows = latest(fetch(cycle))
    if not rows:
        print(f"No survey answers recorded for {cycle}.")
        return 0

    piles = {"disagrees": [], "confirms": [], "new": []}
    orphans = []
    for r in rows:
        p = programs.get(r.get("programId"))
        if not p:
            orphans.append(r)
            continue
        pile, why = verdict(r.get("answer"), p)
        piles[pile].append((p, r, why))

    total = sum(len(v) for v in piles.values())
    print(f"{total} answer(s) for {cycle}, out of {len(programs)} programs "
          f"in the tracker\n")

    order = ["disagrees"] if args.disagree else ["disagrees", "confirms", "new"]
    for pile in order:
        items = sorted(piles[pile], key=lambda t: t[0]["school"].lower())
        if not items:
            continue
        print(f"--- {pile.upper()} ({len(items)}) ---")
        for p, r, why in items:
            said = ANSWER_WORDS.get(r.get("answer"), r.get("answer"))
            print(f"  {p['school']} — {p['program']}")
            print(f"      they say: {said}   ({why})")
            print(f"      {r.get('respondent') or '?'} <{r.get('email') or '?'}>"
                  f"  {(r.get('createdAt') or '')[:10]}")
            print(f"      {p.get('url', '')}")
        print()

    if orphans:
        print(f"{len(orphans)} answer(s) name a program id that is no longer "
              f"in programs.json.\n")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pile", "program_id", "school", "program",
                        "tracker_status", "they_say", "why", "respondent",
                        "email", "answered_on", "department_url"])
            for pile in ("disagrees", "confirms", "new"):
                for p, r, why in piles[pile]:
                    w.writerow([pile, p["id"], p["school"], p["program"],
                                p["status"], r.get("answer"), why,
                                r.get("respondent"), r.get("email"),
                                (r.get("createdAt") or "")[:10],
                                p.get("url", "")])
        print(f"Spreadsheet: {args.csv}")

    if piles["disagrees"]:
        print("Read the disagreements against the program's own page before "
              "changing anything.\nThe entry and the director can both be "
              "right about different things -- a list\nposted after we last "
              "looked, an answer about the program when the entry is\nabout a "
              "named lab.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
