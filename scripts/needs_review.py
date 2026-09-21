# -*- coding: utf-8 -*-
"""Which entries disagree with their own saved page.

    python scripts/needs_review.py            the report
    python scripts/needs_review.py --json     the same, for a script to read
    python scripts/needs_review.py --accept   record what is reported as judged
    python scripts/needs_review.py --stale 3  warn if the snapshots are older
                                              than this many days (default 2)

Run scripts/sweep.py first. This reads the snapshots sweep saved; it fetches
nothing itself.

Why this exists, separately from the sweep. The sweep answers "which pages
changed since I last looked", which is the right question for finding news and
the wrong one for finding mistakes. A program that posts its list between two
sweeps, gets captured, and never gets acted on is from then on identical to its
own snapshot, so the sweep never mentions it again. It is invisible precisely
because it was seen once. On 21 September that had happened to seven programs.

So this asks the other question: does what we publish still match the page we
last read. It compares our data against the snapshot, never against the
previous snapshot, so it keeps reporting a problem until somebody fixes it.

It decides nothing. Every hit is a candidate for a human, or for a session that
can open the page, because the text alone cannot settle what actually matters:

  * Whose list is it? Duke's and UNC Wilmington's pages cover a whole
    department; only some of those names are clinical.
  * Which cycle? Kent State's list is headed "the 2026-2027 incoming doctoral
    class", which is last cycle, not Fall 2027 entry.
  * How firm? "may be considering" and "will likely be reviewing" are maybes;
    a plain "will be accepting applications" is not.
  * Is it even shown? UAB keeps two previous cycles of recruiting tags in its
    markup as HTML comments. Stripped to text they read exactly like the live
    one, so a hit here is a reason to open the page, not to write anything
    down.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
SNAP = os.path.join(os.path.dirname(SITE), "Tracker Snapshots", "pages")
PROGRAMS = os.path.join(SITE, "data", "programs.json")

# Decisions already made, as program id -> hash of the page text they were made
# against. Without this the report names the same programs every run: Kent
# State's list really is last cycle's and Tulsa's page really is one lab, and
# both will go on looking like postings for as long as those pages stand.
# Re-reading them every two days is how a report stops being read. Keyed by
# page text, so the moment one of those pages changes it comes back.
REVIEWED = os.path.join(os.path.dirname(SNAP), "reviewed.json")

# The verbs a program uses to say somebody is taking students. "considering" is
# here for the same reason sweep.py has it: leaving it out is how a full list
# went unnoticed once already.
VERB = re.compile(
    r"(accepting|recruiting|admitting|reviewing applications|considering|"
    r"seeking|taking on|welcoming|open to|will admit|"
    r"plan(?:ning)? to (?:take|admit|recruit))", re.I)

# Wording that means "not yet", so a page saying it is not evidence of a list.
NOT_YET = re.compile(
    r"(will be posted|has not (?:yet )?been posted|not yet (?:been )?posted|"
    r"check back|coming soon|will be (?:added|available|updated)|"
    r"to be (?:announced|determined)|\bTBD\b)", re.I)

# Hedges. These do not disqualify a hit; they change what the reader should
# write down, accepting versus maybe, so they are reported alongside it.
HEDGE = re.compile(
    r"(may be|might be|likely|not (?:necessarily )?guarantee|no guarantee|"
    r"subject to change|anticipat|tentative|have not been made|"
    r"not been finalis|not been finaliz)", re.I)


def fold(s):
    """Compare text the way a reader would, not the way bytes do.

    Pages write O’Kelley with a curly apostrophe where we store O'Kelley
    with a straight one. That is the same name, and it was reported as a
    faculty member who had come off a list. Dashes and non-breaking spaces
    vary the same way.
    """
    s = unicodedata.normalize("NFKC", s)
    for a, b in ((u"’", "'"), (u"‘", "'"), (u"ʼ", "'"),
                 (u"–", "-"), (u"—", "-"), (u" ", " ")):
        s = s.replace(a, b)
    return s


def page_hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def load_reviewed():
    if not os.path.exists(REVIEWED):
        return {}
    try:
        with io.open(REVIEWED, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError:
        return {}


def save_reviewed(d):
    with io.open(REVIEWED, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
        fh.write("\n")


def load_programs():
    with io.open(PROGRAMS, encoding="utf-8") as fh:
        return json.load(fh)


def snapshot_text(pid):
    path = os.path.join(SNAP, pid + ".txt")
    if not os.path.exists(path):
        return None, None
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        return fold(fh.read()), os.path.getmtime(path)


def cycle_year(cycle):
    """The intake year from "Fall 2027". None if the cycle does not say."""
    m = re.search(r"(20\d\d)", cycle or "")
    return int(m.group(1)) if m else None


def windows(text, year):
    """Every stretch of page text naming this cycle beside a recruiting verb."""
    out = []
    for m in VERB.finditer(text):
        win = text[max(0, m.start() - 160):m.start() + 260]
        if re.search(r"\b%d\b|\bfall\s*%d\b" % (year, year % 100), win, re.I):
            out.append(re.sub(r"\s+", " ", win).strip())
    return out


def surnames_missing(program, text):
    """(names we publish that the page no longer mentions, all of them?)

    Surname only: pages switch between "Katie" and "Kathryn", "Dr Jeff" and
    "Jeffrey", and a first-name mismatch is not evidence somebody came off a
    list. A missing surname usually is.

    When every single name has gone, that is nearly always a page we are not
    really reading -- the list moved to a linked document, the URL now serves
    a PDF or an error under a 200, or the list is built by script in the
    browser so a saved copy holds only the shell. Reporting that as "8 of 8
    came off the list" would be a confident wrong answer, so the caller
    separates it.

    "Every" counts only the names actually testable. Short surnames are
    skipped, and counting them in the denominator is how Washington State
    reported five of six gone -- a page whose recruiting list is script-built,
    so not one of the six was really there -- and so missed being called what
    it was.
    """
    gone, checked = [], 0
    for n in (program.get("accepting") or []):
        last = fold(n).replace(",", " ").split()[-1].strip(".")
        if len(last) <= 2:
            continue
        checked += 1
        if last not in text:
            gone.append(n)
    return gone, bool(gone) and len(gone) == checked


def review(data, stale_days):
    year = cycle_year(data.get("cycle"))
    reviewed = load_reviewed()
    f = {"posted_but_we_say_pending": [], "already_judged": [],
         "names_gone": [], "wrong_source": [], "no_snapshot": [],
         "stale_snapshot": []}
    oldest = None

    for p in data["programs"]:
        text, mtime = snapshot_text(p["id"])
        if text is None:
            if p["status"] in ("pending", "posted"):
                f["no_snapshot"].append({"id": p["id"], "school": p["school"]})
            continue
        if oldest is None or mtime < oldest:
            oldest = mtime

        if p["status"] == "pending" and year:
            hits = [h for h in windows(text, year) if not NOT_YET.search(h)]
            if hits:
                h = page_hash(text)
                row = {"id": p["id"], "school": p["school"],
                       "url": p.get("url", ""), "checked": p.get("checked"),
                       "hash": h, "hedged": bool(HEDGE.search(hits[0])),
                       "evidence": hits[0][:300]}
                key = ("already_judged" if reviewed.get(p["id"]) == h
                       else "posted_but_we_say_pending")
                f[key].append(row)

        if p["status"] == "posted":
            gone, everything = surnames_missing(p, text)
            if gone:
                h = page_hash(text)
                row = {"id": p["id"], "school": p["school"],
                       "url": p.get("url", ""), "checked": p.get("checked"),
                       "hash": h, "names": gone,
                       "of": len(p.get("accepting") or [])}
                # Judged already, against this same page. Yale spells a name
                # differently from us and Washington State's list is built by
                # script; both are settled, and repeating them every run is
                # how the report stops being read.
                if reviewed.get(p["id"]) == h:
                    f["already_judged"].append(row)
                else:
                    f["wrong_source" if everything else "names_gone"].append(row)

    if oldest is not None:
        age = (time.time() - oldest) / 86400.0
        if age > stale_days:
            f["stale_snapshot"].append({
                "oldest_days": round(age, 1),
                "note": "run scripts/sweep.py first; this is only as current "
                        "as the snapshots it reads"})
    return f


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--stale", type=float, default=2,
                    help="warn if snapshots are older than this many days")
    ap.add_argument("--accept", action="store_true",
                    help="record everything reported as judged against its "
                         "current page, so it is not reported again until "
                         "that page changes")
    args = ap.parse_args()

    data = load_programs()
    f = review(data, args.stale)

    if args.accept:
        reviewed = load_reviewed()
        marked = (f["posted_but_we_say_pending"] + f["names_gone"]
                  + f["wrong_source"])
        for r in marked:
            reviewed[r["id"]] = r["hash"]
        save_reviewed(reviewed)
        print("Marked %d program(s) as judged against their current page."
              % len(marked))
        print()

    if args.json:
        json.dump(f, sys.stdout, indent=1, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    print("Checked %d entries against their saved pages, for %s."
          % (len(data["programs"]), data.get("cycle")))
    print()

    for s in f["stale_snapshot"]:
        print("!! snapshots are %.1f days old -- run scripts/sweep.py first."
              % s["oldest_days"])
        print()

    rows = f["posted_but_we_say_pending"]
    print("Pages that look like a posted list while we still show pending (%d)"
          % len(rows))
    if not rows:
        print("   none")
    for r in rows:
        print()
        print("   %s%s" % (r["school"],
                           "   [hedged wording]" if r["hedged"] else ""))
        print("      last checked %s   %s" % (r["checked"], r["url"]))
        print("      %s" % r["evidence"][:240])
    if rows:
        print()
        print("   Open each page before writing anything down. The text alone")
        print("   cannot tell you whose list it is, which cycle it names, how")
        print("   firm it is, or whether the tag is even displayed.")
    print()

    rows = f["names_gone"]
    print("Names we publish that are no longer on the page (%d)" % len(rows))
    if not rows:
        print("   none")
    for r in rows:
        print("   %-44s %d of %d gone: %s"
              % (r["school"][:44], len(r["names"]), r["of"],
                 ", ".join(r["names"])))
        print("      %s" % r["url"])

    rows = f["wrong_source"]
    if rows:
        print()
        print("Every name gone -- almost certainly the wrong source URL (%d)"
              % len(rows))
        for r in rows:
            print("   %-44s all %d names absent" % (r["school"][:44], r["of"]))
            print("      %s" % r["url"])
        print("   A list that moved to a linked document, or a URL now")
        print("   serving a PDF or an error page under a 200. Check the URL")
        print("   before touching the names.")

    if f["already_judged"]:
        print()
        print("Looks like a posting but already judged, page unchanged (%d):"
              % len(f["already_judged"]))
        print("   %s" % ", ".join(x["school"] for x in f["already_judged"]))

    if f["no_snapshot"]:
        print()
        print("No snapshot yet (%d): %s"
              % (len(f["no_snapshot"]),
                 ", ".join(x["id"] for x in f["no_snapshot"][:8])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
