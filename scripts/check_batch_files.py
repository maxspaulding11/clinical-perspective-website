# -*- coding: utf-8 -*-
"""Confirm a batch actually rendered, before anyone says it is done.

The first unattended build produced correct data for all 21 posts, all 21
covers, all 21 thumbnails -- and 10 Reels. It reported success. make_reels.py
had been backgrounded and the session ended while it was still working, and
nothing downstream noticed, because every other artefact was right.

So this counts files rather than trusting a run. One command, exit 1 if the
batch is incomplete:

    python scripts/check_batch_files.py 109 129
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
POSTS = os.path.join(ROOT, "Posts")

# Length is reported, not enforced. An earlier version failed a batch at 32
# seconds, which was never a platform limit -- just the range batch 5 happened
# to land in. Instagram allows minutes. The only duration worth failing on is
# one that means the render itself went wrong.
ABSURD = 120.0
TOO_SHORT = 5.0


def duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001 - no ffprobe, unreadable file
        return None


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python scripts/check_batch_files.py <first> <last>")
    lo, hi = int(sys.argv[1]), int(sys.argv[2])

    covers = {c["post"]: c for c in json.load(
        io.open(os.path.join(POSTS, "covers.json"), encoding="utf-8"))}

    missing, broken, durations, ok = [], [], [], 0
    for post in range(lo, hi + 1):
        c = covers.get(post)
        if not c:
            missing.append(f"Post{post}: no entry in covers.json")
            continue
        month = datetime.date.fromisoformat(c["date"]).strftime("%B %Y")
        folder = os.path.join(POSTS, "Videos", month)
        stem = f"{c['date']} Post{post}_{c['slug']}"
        mp4 = os.path.join(folder, stem + ".mp4")
        png = os.path.join(folder, stem + " cover.png")
        thumb = os.path.join(POSTS, "Videos", "Thumbnails",
                             f"{c['slug']}_cover.png")
        gaps = [n for n, p in (("reel", mp4), ("cover", png),
                               ("thumbnail", thumb)) if not os.path.exists(p)]
        if gaps:
            missing.append(f"Post{post} ({c['date']}, {c['slug']}): "
                           f"no {', '.join(gaps)}")
            continue
        d = duration(mp4)
        if d:
            durations.append((post, c["slug"], d))
            if d > ABSURD or d < TOO_SHORT:
                broken.append(f"Post{post} {c['slug']}: {d:.1f}s "
                              f"-- the render went wrong")
        ok += 1

    n = hi - lo + 1
    print(f"Post{lo}-Post{hi}: {ok} of {n} complete")
    if missing:
        print(f"\n{len(missing)} INCOMPLETE:")
        for m in missing:
            print("  " + m)
    if durations:
        ds = [d for _, _, d in durations]
        lo_p, lo_s, lo_d = min(durations, key=lambda t: t[2])
        hi_p, hi_s, hi_d = max(durations, key=lambda t: t[2])
        print(f"  length: {lo_d:.1f}s (Post{lo_p}) to {hi_d:.1f}s "
              f"(Post{hi_p}), mean {sum(ds)/len(ds):.1f}s")
    if broken:
        print(f"\n{len(broken)} with an impossible length:")
        for m in broken:
            print("  " + m)
    if missing:
        # Just the numbers. Splitting on ":" left the "(date, slug)" attached
        # and produced a command that could not be pasted.
        nums = " ".join(re.match(r"Post(\d+)", m).group(1)
                        for m in missing if re.match(r"Post(\d+)", m))
        print(f"\nRender the rest with:\n  python make_reels.py {nums}")
        return 1
    if broken:
        return 1
    print("\nEverything rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
