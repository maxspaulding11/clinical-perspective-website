# -*- coding: utf-8 -*-
"""Tell the people watching a program that it changed.

    python scripts/watch_notify.py                    show what would be sent
    python scripts/watch_notify.py --send             actually send it
    python scripts/watch_notify.py --skip yale-university-phd --send
    python scripts/watch_notify.py --seed             accept the current state, send nothing

Dry run is the default and --send is the only thing that writes. An endpoint
that puts notices in other people's accounts should take a deliberate keystroke.

Why a snapshot and not a git diff of the last two commits: programs.json often
changes twice before anyone notifies, and comparing adjacent commits would then
silently skip the first change. This keeps the state it last notified on, in
"Tracker Snapshots" beside the Website folder, and diffs against that -- so a
change is reported exactly once no matter how the commits fall.

What counts as worth telling somebody, and what does not:

  Reported -- a program's status becoming "posted" or "closed", and a change in
  how many faculty a posted program lists. Those are the things an applicant
  would act on.

  Not reported -- anything moving in or out of "unverified" (that is our
  bookkeeping, not their news), and "pending" to "cohort" (that is our
  inference about their admissions model changing, not the program doing
  anything). Also nothing at all for a program nobody is watching.

  Corrections are the case the rule cannot catch. When a program director
  writes in and you fix an entry, the diff is indistinguishable from real news.
  Pass --skip <program-id> for those, which is why the dry run prints the ids.

Needs NOTIFY_SECRET in the environment, matching the value the Spare Change
app has. Without it this refuses to send rather than guessing.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROGRAMS = os.path.join(SITE, "data", "programs.json")
STATE = os.path.join(os.path.dirname(SITE), "Tracker Snapshots", "last-notified.json")
ENDPOINT = "https://spare.theclinicalperspective.org/api/notify"

NEWSWORTHY = {"posted", "closed"}
IGNORE_PAIRS = {("pending", "cohort"), ("cohort", "pending")}


def snapshot(programs):
    return {
        p["id"]: {
            "status": p["status"],
            "accepting": len(p.get("accepting") or []),
            # Carried so the notice can tell "published a list with
            # nobody on it" from "published a list of maybes". Not
            # compared for changes: a maybe count moving is usually us
            # reclassifying a name, not the program doing anything.
            "maybe": len(p.get("maybe") or []),
            "school": p["school"],
            "program": p["program"],
        }
        for p in programs
    }


def changes_between(old, new):
    out = []
    for pid, now in new.items():
        was = old.get(pid)
        if was is None:
            continue  # a program we have only just added is not a change

        if was["status"] != now["status"]:
            if "unverified" in (was["status"], now["status"]):
                continue
            if (was["status"], now["status"]) in IGNORE_PAIRS:
                continue
            if now["status"] not in NEWSWORTHY:
                continue
            out.append({
                "id": pid, "school": now["school"], "program": now["program"],
                "from": was["status"], "to": now["status"],
                "accepting": now["accepting"], "maybe": now["maybe"],
            })
        elif now["status"] == "posted" and was["accepting"] != now["accepting"]:
            out.append({
                "id": pid, "school": now["school"], "program": now["program"],
                "from": "posted", "to": "posted",
                "accepting": now["accepting"], "was": was["accepting"],
                "maybe": now["maybe"],
            })
    return sorted(out, key=lambda c: c["school"].lower())


def describe(c):
    # "0 faculty accepting" is true of the accepting column and wrong about a
    # program whose page lists seven people as considering applications. Say
    # which it is, or the line reads as bad news and gets the program crossed
    # off a list it belongs on.
    maybe = c.get("maybe") or 0
    if c["from"] == c["to"] == "posted":
        tail = f' ({maybe} considering)' if not c["accepting"] and maybe else ""
        return (f'{c["school"]} — accepting list changed from {c["was"]} to '
                f'{c["accepting"]} faculty{tail}')
    if c["to"] == "closed":
        return f'{c["school"]} — closed this cycle (was "{c["from"]}")'
    if not c["accepting"] and maybe:
        return (f'{c["school"]} — posted its list, nobody confirmed accepting '
                f'but {maybe} considering (was "{c["from"]}")')
    return (f'{c["school"]} — posted its list, {c["accepting"]} faculty '
            f'accepting (was "{c["from"]}")')


def report_email(e, label):
    """Say what became of the email half of the job.

    Worth printing even when nothing went wrong. The in-app notice and the
    email are two separate outcomes -- the server writes the notices first
    and reports a bounce rather than throwing -- so a run that wrote two
    notices but failed to mail one of them would otherwise be indis-
    tinguishable from a clean one.

    Addresses only appear here for a failure, which is the one case where
    you need to know which one to go and fix."""
    print(f"{label}: {e.get('sent', 0)} sent, {e.get('skipped', 0)} skipped.")
    if e.get("reason"):
        print(f"  {e['reason']}")
    for f in e.get("failures") or []:
        print(f"  failed: {f.get('to')} - {f.get('error')}")


def secret():
    """The environment first, then a .env beside the repo root.

    The file is there so this is one command rather than an export every
    time; .gitignore covers it, and the same value lives in the Spare Change
    project's own environment. If neither has it, this refuses rather than
    guessing -- the endpoint it guards writes to other people's accounts."""
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


def post(changes, dry_run, test_email=None):
    key = secret()
    if not key:
        raise SystemExit("NOTIFY_SECRET is not set, in the environment or "
                         "Website/.env. Refusing to send.")
    payload = {"changes": changes, "dryRun": dry_run}
    if test_email:
        # The server treats this as "mail one address and write nothing".
        payload = {"changes": changes, "testEmail": test_email}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"{ENDPOINT} returned {err.code}: "
                         f"{err.read().decode('utf-8', 'replace')[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true",
                    help="actually write the notifications")
    ap.add_argument("--skip", action="append", default=[], metavar="PROGRAM_ID",
                    help="suppress this program (use for corrections); repeatable")
    ap.add_argument("--seed", action="store_true",
                    help="record the current state as already notified, send nothing")
    ap.add_argument("--test-email", metavar="ADDRESS",
                    help="mail one sample notice to this address and stop: no "
                         "watcher is looked up, nothing is written, the state "
                         "is untouched")
    args = ap.parse_args()

    programs = json.load(open(PROGRAMS, encoding="utf-8"))["programs"]
    current = snapshot(programs)

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    if args.seed or not os.path.exists(STATE):
        if not os.path.exists(STATE) and not args.seed:
            print("No previous state, so there is nothing to compare against.")
            print("This run records the current state instead of reporting "
                  "every program as new.\n")
        json.dump({"recorded": date.today().isoformat(), "programs": current},
                  open(STATE, "w", encoding="utf-8"), indent=1)
        print(f"State recorded for {len(current)} programs: {STATE}")
        return 0

    previous = json.load(open(STATE, encoding="utf-8"))
    found = changes_between(previous.get("programs", {}), current)

    skipped = [c for c in found if c["id"] in args.skip]
    changes = [c for c in found if c["id"] not in args.skip]

    print(f"since {previous.get('recorded', 'last time')}: "
          f"{len(found)} change(s) worth telling somebody about\n")
    for c in changes:
        print(f"  {describe(c)}")
        print(f"      --skip {c['id']}")
    for c in skipped:
        print(f"  (skipped) {describe(c)}")

    if not changes:
        print("\nNothing to send.")
        if args.send:
            json.dump({"recorded": date.today().isoformat(), "programs": current},
                      open(STATE, "w", encoding="utf-8"), indent=1)
            print("State updated.")
        return 0

    # Counting who is watching needs the server, and the server needs the
    # secret. Without it a dry run can still show what changed, which is the
    # part you actually read before deciding to send.
    if not args.send and not secret():
        print("\nNOTIFY_SECRET is not set, so this cannot say how many people "
              "are watching.\nThe changes above are what would be sent.")
        return 0

    if args.test_email:
        r = post(changes, dry_run=False, test_email=args.test_email)
        report_email(r.get("email") or {}, f"\nTest to {args.test_email}")
        print("Nothing was written and the state is untouched.")
        return 0

    result = post(changes, dry_run=not args.send)
    print(f"\n{len(changes)} change(s) affect {result['watchers']} watch(es) "
          f"held by {result['people']} person/people.")

    if not args.send:
        print("\nDry run: nothing was written and the state is untouched.")
        print("Re-run with --send once the list above looks right.")
        return 0

    print(f"Wrote {result['wrote']} notification(s).")
    report_email(result.get("email") or {}, "Email")
    json.dump({"recorded": date.today().isoformat(), "programs": current},
              open(STATE, "w", encoding="utf-8"), indent=1)
    print("State updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
