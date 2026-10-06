# -*- coding: utf-8 -*-
"""Check the days that are about to post, not the one that just did.

A missing Reel is invisible until the morning it is due. The first unattended
build left eleven unrendered and reported success; every data file and every
cover was correct, so the first symptom would have been a failed post weeks
later with no obvious cause.

This looks forward instead. Run after publishing, it checks that the next
few days have an entry in the manifest and that their video and cover are
actually being served. A gap surfaces a week early, while there is time to
render, rather than at six in the morning on the day.

It fails loudly on purpose. Run after the publish step, a non-zero exit marks
the day's run red without having stopped the post that already went out --
which is the right trade: the post is not held hostage to a warning, and the
warning is impossible to miss.

    python scripts/check_upcoming.py            # next 7 days
    python scripts/check_upcoming.py --days 14
"""
import argparse
import datetime
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
MANIFEST = os.path.join(SITE, "data", "reels.json")


def reachable(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--from-day", default=None,
                    help="YYYY-MM-DD; default is tomorrow, US Eastern")
    args = ap.parse_args()

    manifest = json.load(io.open(MANIFEST, encoding="utf-8"))
    by_day = {e["day"]: e for e in manifest["posts"]}
    last = max(by_day) if by_day else None
    # The manifest deliberately starts after the days Meta Business Suite's
    # own calendar owns, so a gap before it begins is the handover, not a
    # fault -- the same as a gap after the queue ends.
    first = min(by_day) if by_day else None

    start = (datetime.date.fromisoformat(args.from_day) if args.from_day
             else (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.timedelta(hours=5)).date()
             + datetime.timedelta(days=1))

    print(f"checking {args.days} days from {start}")
    print(f"manifest runs to {last}\n")

    problems = []
    for i in range(args.days):
        day = (start + datetime.timedelta(days=i)).isoformat()
        e = by_day.get(day)
        if not e:
            # Past the end of the queue is not a fault -- it is the thing the
            # batch routine exists to notice, and it reports separately.
            if last and day > last:
                print(f"  {day}  (past the end of the queue)")
                continue
            if first and day < first:
                print(f"  {day}  (before the queue starts -- another "
                      f"scheduler owns this day)")
                continue
            problems.append(f"{day}: no entry in the manifest, "
                            f"though the queue runs to {last}")
            print(f"  {day}  NO ENTRY")
            continue
        v, c = reachable(e["videoUrl"]), reachable(e["coverUrl"])
        bad = [n for n, s in (("video", v), ("cover", c)) if s != 200]
        if bad:
            problems.append(f"{day} ({e['postId']}): {', '.join(bad)} "
                            f"not served (video {v}, cover {c})")
            print(f"  {day}  {e['postId']}  {' '.join(bad).upper()} MISSING")
        else:
            print(f"  {day}  {e['postId']}  ok")

    if problems:
        print(f"\n{len(problems)} problem(s) in the next {args.days} days:")
        for p in problems:
            print("  " + p)
        print("\nThese have not stopped today's post. They will stop theirs.")
        return 1
    print(f"\nThe next {args.days} days are all present and served.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
