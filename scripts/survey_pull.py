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
import collections
import csv
import json
import re
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


def flatten_faculty(faculty):
    """One cell for a spreadsheet: "Name: yes; Name: no"."""
    if not faculty:
        return ""
    return "; ".join(
        f'{(i.get("name") or "?")}: {i.get("answer")}'
        for i in faculty if isinstance(i, dict))


def name_key(name):
    """First initial plus surname, lowercased: "a|lau".

    The two datasets disagree about 84 of 363 names. The tracker's accepting
    lists and the faculty roster are read off different pages by different
    scripts, so the same person is "Anna Lau" in one and "Anna S. Lau" in the
    other, "Greg Fabiano" and "Gregory Fabiano", "Katie Karlsgodt" and
    "Katherine H. Karlsgodt". Comparing the raw strings marked a quarter of
    answers as agreement when they were the exact opposite -- a director
    saying "no" about somebody the entry lists, reported as "nothing to do".
    That is the one mistake this section exists to prevent.

    This gets 330 of 363. It does not attempt nicknames beyond the initial,
    and where a key is ambiguous the caller must say so rather than guess."""
    parts = [w for w in re.sub(r"[.,]", " ", name).split() if w]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0].lower()
    return f"{parts[0][0].lower()}|{parts[-1].lower()}"


MARKS = "+-~=?"


def faculty_lines(faculty, program):
    """The per-professor answers, marked up against what the entry claims.

    The marks are the whole value of this section. A director saying yes about
    somebody the tracker already lists needs no work; a director saying no
    about somebody the tracker lists as accepting is a name that should come
    off a page today, and it must not be buried in a list of twelve.

        +   they say yes, the entry does not list them as accepting
        -   they say no, the entry does list them as accepting
        ~   a name we could not line up with the entry's list -- check by hand
        =   the entry already agrees
        ?   not sure, so nothing to do
    """
    if not faculty:
        return []

    listed = collections.Counter()
    surnames = collections.Counter()
    for n in (program.get("accepting") or []):
        k = name_key(n)
        listed[k] += 1
        surnames[k.split("|")[-1]] += 1

    out, notable, unsure = [], 0, 0
    for item in faculty:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        ans = item.get("answer")
        k = name_key(name)

        if listed[k] == 1:
            on_list = True
        elif listed[k] > 1:
            on_list = None          # two people share the key
        elif surnames[k.split("|")[-1]]:
            on_list = None          # right surname, different initial
        else:
            on_list = False

        if on_list is None:
            mark = "~"
        elif ans == "yes":
            mark = "=" if on_list else "+"
        elif ans == "no":
            mark = "-" if on_list else "="
        else:
            mark = "?"

        if mark in "+-":
            notable += 1
        if mark == "~":
            unsure += 1
        out.append((mark, name, ans))

    # Changes first, then the ones needing a human, then agreements, then the
    # shrugs -- otherwise the one name that needs action sits below eleven
    # that do not.
    out.sort(key=lambda t: (MARKS.index(t[0]), t[1].lower()))
    head = f"faculty: {len(out)} answered, {notable} differ from the entry"
    if unsure:
        head += f", {unsure} to check by hand"
    lines = [head]
    lines += [f"  {m} {n} ({ANSWER_WORDS.get(a, a)})" for m, n, a in out]
    return lines


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
            for line in faculty_lines(r.get("faculty"), p):
                print(f"      {line}")
        print()

    if orphans:
        print(f"{len(orphans)} answer(s) name a program id that is no longer "
              f"in programs.json.\n")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pile", "program_id", "school", "program",
                        "tracker_status", "they_say", "why", "respondent",
                        "email", "answered_on", "department_url",
                        "faculty_answers"])
            for pile in ("disagrees", "confirms", "new"):
                for p, r, why in piles[pile]:
                    w.writerow([pile, p["id"], p["school"], p["program"],
                                p["status"], r.get("answer"), why,
                                r.get("respondent"), r.get("email"),
                                (r.get("createdAt") or "")[:10],
                                p.get("url", ""),
                                flatten_faculty(r.get("faculty"))])
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
