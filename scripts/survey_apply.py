# -*- coding: utf-8 -*-
"""Record what each program told us, into data/programs.json.

    python scripts/survey_apply.py            write the confirmations
    python scripts/survey_apply.py --dry-run  show what would change

What this writes is deliberately narrow. For every program that answered the
survey it adds one block:

    "confirmed": {"answer": "yes", "on": "2026-09-18", "cycle": "Fall 2027"}

and it changes nothing else. Not `status`, not `accepting`, not `sourceQuote`,
not `checked`. Those describe what the program has *published* and what we
read on their page on a given day, and a director's email is not that. Two
separate facts, kept separately, each traceable to its own source.

That split is also what lets the page be honest when the two disagree. A
department page listing four faculty for Fall 2027 and a director saying "not
decided yet" are not a contradiction to resolve by picking a winner -- they
are two dated statements, and an applicant is better served seeing both than
seeing whichever one a script happened to write last.

The director's name and email are on purpose NOT written here.
data/programs.json is served publicly. They answered a question about their
program; nobody offered to put their name on a public page, and a survey reply
is not consent to be quoted by name. The name stays in the database, where
survey_pull.py shows it to the one person who reads these.

Plenty of directors ignore the survey link and just hit reply. Those answers
are as good as a click and the database cannot see them, so they are kept by
hand in data/survey-email-answers.json and merged in here. Without that they
would be written in once and wiped by the next run of this script.

Where both exist for one program, the later date wins, and the survey form
wins an exact tie -- a click is a deliberate answer to the exact question
asked, where an email is prose somebody had to read.

Re-runnable. Running it twice changes nothing the second time, and a director
who corrects themselves later overwrites their own earlier answer.

Needs NOTIFY_SECRET, the same one survey_pull.py uses.
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROGRAMS = os.path.join(SITE, "data", "programs.json")

sys.path.insert(0, HERE)
from survey_pull import fetch, latest, verdict  # noqa: E402


EMAILED = os.path.join(SITE, "data", "survey-email-answers.json")


def load():
    with io.open(PROGRAMS, encoding="utf-8") as fh:
        return json.load(fh)


def emailed(cycle):
    """Answers that arrived as a reply, shaped like the database's rows.

    Missing file is not an error -- it only exists because somebody replied.
    """
    if not os.path.exists(EMAILED):
        return []
    with io.open(EMAILED, encoding="utf-8") as fh:
        doc = json.load(fh)
    out = []
    for a in doc.get("answers", []):
        c = a.get("cycle") or doc.get("cycle") or cycle
        if c != cycle:
            continue
        out.append({"programId": a["programId"], "answer": a["answer"],
                    "createdAt": a["on"], "cycle": c, "via": "email"})
    return out


def merge(from_db, from_email):
    """One answer per program, the later date winning.

    A tie goes to the survey form: it answered the exact question asked, and
    an email is prose that had to be read and interpreted.
    """
    best = {}
    for r in list(from_email) + list(from_db):
        pid = r.get("programId")
        prev = best.get(pid)
        if prev is None or (r.get("createdAt") or "")[:10] >= (prev.get("createdAt") or "")[:10]:
            best[pid] = r
    return list(best.values())


def save(data):
    # Matches how the file is already written: 1-space indent, real unicode,
    # trailing newline. Anything else turns a two-line change into a diff of
    # the whole file.
    with io.open(PROGRAMS, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycle", help="only this cycle (default: the tracker's)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the changes and write nothing")
    args = ap.parse_args()

    data = load()
    cycle = args.cycle or data.get("cycle")
    by_id = {p["id"]: p for p in data["programs"]}

    by_email = emailed(cycle)
    answers = merge(latest(fetch(cycle)), by_email)
    if not answers:
        print("No answers for %s yet. Nothing to record." % cycle)
        return 0

    added, updated, unchanged, unknown = [], [], [], []
    contested = []

    for r in answers:
        pid = r.get("programId")
        program = by_id.get(pid)
        if program is None:
            # A program answered that is no longer in the tracker. Never
            # invent an entry for it -- say so and move on.
            unknown.append(pid)
            continue

        block = {
            "answer": r["answer"],
            "on": (r.get("createdAt") or "")[:10],
            "cycle": r.get("cycle") or cycle,
        }
        # Only recorded when it was not the survey form, so the 15 blocks
        # already written stay byte-identical and this stays a small diff.
        if r.get("via"):
            block["via"] = r["via"]
        pile, why = verdict(r["answer"], program)
        if pile == "disagrees":
            contested.append((program, r["answer"], why))

        before = program.get("confirmed")
        if before == block:
            unchanged.append(program)
        elif before is None:
            program["confirmed"] = block
            added.append((program, block))
        else:
            program["confirmed"] = block
            updated.append((program, before, block))

    if args.dry_run:
        print("DRY RUN — nothing written.\n")
    else:
        save(data)

    def line(p, b):
        return "  %-52s %s (%s)" % (p["school"][:52], b["answer"], b["on"])

    print("%d answer(s) for %s (%d of them by email)"
          % (len(answers), cycle, len(by_email)))
    if added:
        print("\nrecorded (%d):" % len(added))
        for p, b in added:
            print(line(p, b))
    if updated:
        print("\nchanged their answer (%d):" % len(updated))
        for p, old, new in updated:
            print("  %-52s %s -> %s" % (p["school"][:52], old["answer"], new["answer"]))
    if unchanged:
        print("\nalready recorded (%d)" % len(unchanged))
    if unknown:
        print("\nnot in the tracker (%d): %s" % (len(unknown), ", ".join(unknown)))

    if contested:
        print("\n--- these contradict the entry, and are YOURS to decide (%d) ---"
              % len(contested))
        for p, answer, why in contested:
            print("  %s" % p["school"])
            print("      they say %s; %s" % (answer, why))
            print("      %s" % p.get("url", ""))
        print("\nThe page shows both, so nothing here is being hidden from")
        print("readers while it waits. Changing `status` or `accepting` is a")
        print("human call: read their page first.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
