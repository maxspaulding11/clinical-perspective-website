# -*- coding: utf-8 -*-
"""Everything needed to schedule a batch by hand in Meta Business Suite.

The API route is not reliable for this account. Meta blocked the developer
account on 5 October, again on 9 October, and the second block arrived about
a day after the first was cleared -- on an account whose only activity is
publishing one Reel a day to its own Instagram. Confirming identity clears
the symptom, not the cause.

Business Suite needs no developer account, no token and no confirmation, and
it posted batch 5 at 06:00 every day for weeks without complaint. The cost is
that scheduling is manual, so this makes the manual part fast: one entry per
day, in order, with the two file paths to attach and the caption to paste.

    python scripts/schedule_pack.py                 # from today onward
    python scripts/schedule_pack.py --from 2026-10-12
    python scripts/schedule_pack.py --days 21

Writes ../Posts/Content/Scheduling Pack <first> to <last>.md
"""
import argparse
import datetime
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
POSTS = os.path.join(ROOT, "Posts")
OUTDIR = os.path.join(POSTS, "Content")
MANIFEST = os.path.join(SITE, "data", "reels.json")

POST_AT = "6:00 AM"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default=None,
                    help="YYYY-MM-DD; default today")
    ap.add_argument("--days", type=int, default=None,
                    help="how many days to include; default all remaining")
    args = ap.parse_args()

    start = (datetime.date.fromisoformat(args.start) if args.start
             else datetime.date.today())
    manifest = json.load(io.open(MANIFEST, encoding="utf-8"))
    covers = {c["post"]: c for c in json.load(
        io.open(os.path.join(POSTS, "covers.json"), encoding="utf-8"))}

    rows = [e for e in manifest["posts"]
            if datetime.date.fromisoformat(e["day"]) >= start]
    rows.sort(key=lambda e: e["day"])
    if args.days:
        rows = rows[:args.days]
    if not rows:
        raise SystemExit(f"nothing scheduled on or after {start}")

    L = []
    L.append(f"# Scheduling pack — {rows[0]['day']} to {rows[-1]['day']}")
    L.append("")
    L.append(f"{len(rows)} posts, one per day, all at **{POST_AT}**.")
    L.append("")
    L.append("## How")
    L.append("")
    L.append("In Meta Business Suite → **Planner** → **Create post** → "
             "**Reel**:")
    L.append("")
    L.append("1. Upload the **video** listed for the day.")
    L.append("2. At the cover step choose **Upload image** and pick the "
             "**cover** listed beside it — not a frame from the video, or "
             "the grid loses its checkerboard.")
    L.append("3. Paste the caption.")
    L.append("4. Set the date and **6:00 AM**, and schedule.")
    L.append("5. Tick both **Instagram** and **Facebook** if the composer "
             "offers it, so the two stay in step.")
    L.append("")
    L.append("Business Suite schedules up to **29 days ahead**, so a full "
             "batch may need two sittings.")
    L.append("")
    L.append("---")

    missing = 0
    for e in rows:
        post = int(e["postId"].split("_")[0].replace("Post", ""))
        c = covers.get(post)
        month = datetime.date.fromisoformat(e["day"]).strftime("%B %Y")
        folder = os.path.join(POSTS, "Videos", month)
        stem = f"{e['day']} Post{post}_{c['slug']}" if c else None
        mp4 = os.path.join(folder, stem + ".mp4") if stem else None
        png = os.path.join(folder, stem + " cover.png") if stem else None
        here = all(p and os.path.exists(p) for p in (mp4, png))
        if not here:
            missing += 1

        d = datetime.date.fromisoformat(e["day"])
        L.append("")
        L.append(f"## {d.strftime('%a %-d %B') if os.name != 'nt' else d.strftime('%a %d %B')}"
                 f" · {POST_AT} · Post{post}")
        L.append("")
        if not here:
            L.append("> **FILES MISSING — do not schedule this one yet.**")
            L.append("")
        L.append(f"**Video:** `{mp4}`")
        L.append("")
        L.append(f"**Cover:** `{png}`")
        L.append("")
        L.append("**Caption:**")
        L.append("")
        L.append("```")
        L.append(e["caption"])
        L.append("```")
        L.append("")
        L.append("---")

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(
        OUTDIR, f"Scheduling Pack {rows[0]['day']} to {rows[-1]['day']}.md")
    io.open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)}")
    print(f"  {len(rows)} posts, {rows[0]['day']} to {rows[-1]['day']}")
    if missing:
        print(f"  {missing} marked FILES MISSING -- render them first")
    else:
        print("  every video and cover is on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
