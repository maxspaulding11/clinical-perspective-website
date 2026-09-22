# -*- coding: utf-8 -*-
"""Record on the dashboard calendar what a run did.

    python scripts/calendar_note.py --note "no changes"
    python scripts/calendar_note.py --day 2026-09-23 --note "Published 3."
    python scripts/calendar_note.py --title "Tracker sweep" --note "..."

Writes one entry for a day, replacing that day's entry of the same title rather
than adding a second, so a run that records itself twice leaves one row saying
the later thing.

Why this posts to Spare Change instead of writing the database directly: the
calendar lives in the other repo, and a run here must not depend on that repo
being installed. The first scheduled sweep was told to write the calendar
through Prisma, which needs spare-change's node_modules -- 807MB of files
OneDrive had no reason to sync, deleted the same evening. The step would have
failed on the 23rd for a reason having nothing to do with calendars. Over HTTP
it works from a bare checkout, and it writes to production rather than to
whatever happens to be on this machine.

The day defaults to today in the same fixed zone the calendar itself uses, not
the machine's. This can run at 08:00 local or unattended at any hour, and a
date is a square on a wall calendar either way.

Needs NOTIFY_SECRET, the same one watch_notify.py uses.
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)

ENDPOINT = os.environ.get(
    "CP_CALENDAR_ENDPOINT",
    "https://spare.theclinicalperspective.org/api/calendar")

# The zone the calendar's own day keys are computed in. Hard-coded rather than
# read from the machine so a run at 23:00 does not file itself on tomorrow.
CALENDAR_TZ_OFFSET_HOURS = -4  # America/New_York, daylight time


def today_key():
    now = datetime.now(timezone.utc) + timedelta(hours=CALENDAR_TZ_OFFSET_HOURS)
    return now.strftime("%Y-%m-%d")


def secret():
    """The environment first, then Website/.env. Same rule as watch_notify."""
    from_env = os.environ.get("NOTIFY_SECRET")
    if from_env:
        return from_env
    path = os.path.join(SITE, ".env")
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as fh:
            for line in fh:
                key, _, value = line.partition("=")
                if key.strip() == "NOTIFY_SECRET":
                    return value.strip().strip('"').strip("'")
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--note", required=True,
                    help="what happened, in a sentence or three")
    ap.add_argument("--day", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--title", default="Tracker sweep",
                    help="the entry to write or replace")
    ap.add_argument("--kind", default="note",
                    choices=["note", "deadline", "post", "outreach"])
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be sent and stop")
    args = ap.parse_args()

    key = secret()
    if not key:
        raise SystemExit("NOTIFY_SECRET is not set, in the environment or "
                         "Website/.env. Refusing to send.")

    payload = {"day": args.day or today_key(), "title": args.title,
               "note": args.note, "kind": args.kind}

    if args.dry_run:
        print("DRY RUN, nothing sent:")
        print(json.dumps(payload, indent=1, ensure_ascii=False))
        return 0

    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as err:
        raise SystemExit("%s returned %s: %s"
                         % (ENDPOINT, err.code,
                            err.read().decode("utf-8", "replace")[:200]))
    except urllib.error.URLError as err:
        raise SystemExit("could not reach %s: %s" % (ENDPOINT, err.reason))

    print("%s %s on %s." % (out.get("action", "wrote"), args.title,
                            payload["day"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
