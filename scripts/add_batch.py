# -*- coding: utf-8 -*-
"""Append a batch of posts to the four files the pipeline reads.

Takes one JSON file of entries and writes them into reel_scripts.json,
covers.json, lay_summaries.json (all in ../Posts) and this repo's
scripts/studies-source.json, deriving the post numbers and both dates from
what is already there. Nothing is hardcoded to a particular batch, so this
works for batch 7 and every one after it.

Idempotent: a post number already present is skipped rather than duplicated,
so a run that failed halfway can simply be repeated.

    python scripts/add_batch.py entries.json
    python scripts/add_batch.py entries.json --dry-run

Each entry needs:

    pmid      str, must already be in batch-citations.json (see --citations)
    slug      str, CamelCase, no spaces
    tag       str, from the site's tag set
    voice     "Andrew" | "Ava"      -- must alternate with the previous post
    theme     blue|green|plum|orange|slate
    symbol    one of make_reels.py's SYMBOLS
    base      [r,g,b] on even posts (coloured cover)
    accent    [r,g,b] on odd posts (cream cover)
    head, head_accent    cover copy, two short lines
    title     editorial headline for the website
    blurb     ~40 words
    summary   ~250-300 words, website
    ig        ~180-200 words, Instagram caption body, SINGLE PARAGRAPH
    blocks    9 one-sentence lines, ~58-64 words total
    stat      {value, suffix?, label?, block}
    hashtags  ~18 tags, space separated
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
POSTS = os.path.join(ROOT, "Posts")
SOURCE = os.path.join(HERE, "studies-source.json")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

REQUIRED = ("pmid", "slug", "tag", "voice", "theme", "symbol", "head",
            "head_accent", "title", "blurb", "summary", "ig", "blocks",
            "stat", "hashtags")

THEMES = {"blue", "green", "plum", "orange", "slate"}
VOICES = {"Andrew", "Ava"}
CAPTION_MAX = 2200


def load(path):
    return json.load(io.open(path, encoding="utf-8"))


def save(path, data):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def pretty(d):
    """The date convention lay_summaries.json actually uses: "Oct 8"."""
    return "%s %d" % (MONTHS[d.month - 1], d.day)


def check(entries, rs, cv, first_post, cits):
    """Refuse the whole batch rather than write a bad one.

    Everything here has gone wrong at least once. The voice rotation and the
    tag adjacency are what keep the feed from sounding and looking repetitive;
    the caption limit is a hard Instagram rejection; and a missing citation
    means a post that cannot say where its claim came from.
    """
    errs = []
    prev_voice = {r["post"]: r["voice"] for r in rs}.get(first_post - 1)
    prev_tag = {c["post"]: c["tag"] for c in cv}.get(first_post - 1)

    for i, e in enumerate(entries):
        post = first_post + i
        where = f"entry {i} (Post{post})"
        for k in REQUIRED:
            if not e.get(k):
                errs.append(f"{where}: missing {k}")
        if e.get("voice") not in VOICES:
            errs.append(f"{where}: voice must be Andrew or Ava")
        if e.get("theme") not in THEMES:
            errs.append(f"{where}: theme {e.get('theme')!r} is not one of {sorted(THEMES)}")
        if ("base" in e) == ("accent" in e):
            errs.append(f"{where}: give exactly one of base (even posts) or accent (odd)")
        if post % 2 == 0 and "base" not in e:
            errs.append(f"{where}: Post{post} is even, so it needs base (a coloured cover)")
        if post % 2 == 1 and "accent" not in e:
            errs.append(f"{where}: Post{post} is odd, so it needs accent (a cream cover)")
        if e.get("voice") == prev_voice:
            errs.append(f"{where}: voice {e['voice']} repeats the previous post")
        if e.get("tag") == prev_tag:
            errs.append(f"{where}: tag {e['tag']!r} repeats the previous post")
        if re.search(r"\s", e.get("slug", "x")):
            errs.append(f"{where}: slug must not contain spaces")
        blocks = e.get("blocks") or []
        if len(blocks) != 9:
            errs.append(f"{where}: {len(blocks)} blocks, expected 9")
        words = sum(len(b.split()) for b in blocks)
        if not 48 <= words <= 72:
            errs.append(f"{where}: {words} spoken words, expected roughly 58-64")
        for b in blocks:
            if b.count(".") + b.count("?") + b.count("!") > 1:
                errs.append(f"{where}: block is more than one sentence: {b!r}")
        if "\n" in (e.get("ig") or ""):
            errs.append(f"{where}: ig summary must be a single paragraph")
        if e["pmid"] not in cits:
            errs.append(f"{where}: pmid {e['pmid']} is not in the citations file")
        igw = len((e.get("ig") or "").split())
        if not 165 <= igw <= 215:
            errs.append(f"{where}: ig summary is {igw} words, expected 170-210")
        prev_voice, prev_tag = e.get("voice"), e.get("tag")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries", help="JSON file: a list of entry objects")
    ap.add_argument("--citations", default=None,
                    help="JSON map of pmid -> {title,journal,authors,pubdate,"
                         "doi,url}; defaults to batch-citations.json beside "
                         "the entries file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    entries = load(args.entries)
    cits_path = args.citations or os.path.join(
        os.path.dirname(os.path.abspath(args.entries)), "batch-citations.json")
    if not os.path.exists(cits_path):
        raise SystemExit(f"no citations file at {cits_path}")
    cits = load(cits_path)

    rs = load(os.path.join(POSTS, "reel_scripts.json"))
    cv = load(os.path.join(POSTS, "covers.json"))
    ls = load(os.path.join(POSTS, "lay_summaries.json"))
    src = load(SOURCE)

    # Continue from wherever the queue actually ends, on both sequences.
    first_post = max(r["post"] for r in rs) + 1
    ig_start = max(datetime.date.fromisoformat(c["date"])
                   for c in cv) + datetime.timedelta(days=1)
    web_start = max(datetime.date.fromisoformat(e["date"])
                    for e in src) + datetime.timedelta(days=1)

    print(f"continuing from Post{first_post}")
    print(f"  instagram dates start {ig_start}")
    print(f"  website dates start   {web_start}")

    errs = check(entries, rs, cv, first_post, cits)
    if errs:
        print(f"\n{len(errs)} problem(s); nothing written:")
        for e in errs:
            print("  " + e)
        return 1

    have = {r["post"] for r in rs}
    added = 0
    for i, e in enumerate(entries):
        post = first_post + i
        if post in have:
            print(f"skip (already present): Post{post}")
            continue
        c = cits[e["pmid"]]
        ig_date = ig_start + datetime.timedelta(days=i)
        web_date = web_start + datetime.timedelta(days=i)

        caption_chars = len(e["title"]) + 2 + len(e["ig"]) + 2 + len(e["hashtags"])
        if caption_chars > CAPTION_MAX:
            print(f"Post{post}: caption would be {caption_chars} characters, "
                  f"over Instagram's {CAPTION_MAX}; nothing written")
            return 1

        rs.append({"post": post, "slug": e["slug"], "tag": e["tag"],
                   "voice": e["voice"], "theme": e["theme"],
                   "symbol": e["symbol"], "stat": e["stat"],
                   "blocks": e["blocks"]})
        cov = {"post": post, "date": ig_date.isoformat(), "slug": e["slug"],
               "tag": e["tag"], "head": e["head"],
               "head_accent": e["head_accent"]}
        cov["base" if "base" in e else "accent"] = e.get("base") or e["accent"]
        cov["out"] = [
            "Videos/%s/%s Post%d_%s cover.png" % (
                ig_date.strftime("%B %Y"), ig_date.isoformat(), post, e["slug"]),
            "Videos/Thumbnails/%s_cover.png" % e["slug"]]
        cv.append(cov)
        ls.append({"post": post, "slug": e["slug"], "title": e["title"],
                   "journal": c["journal"], "authors": c["authors"],
                   "pmid": e["pmid"], "doi": c["doi"], "pubdate": c["pubdate"],
                   "date": pretty(ig_date), "summary": e["ig"],
                   "hashtags": e["hashtags"]})
        src.append({"index": post, "date": web_date.isoformat(),
                    "title": e["title"], "tag": e["tag"], "blurb": e["blurb"],
                    "summary": e["summary"], "journal": c["journal"],
                    "authors": c["authors"], "pubdate": c["pubdate"],
                    "pmid": e["pmid"], "doi": c["doi"], "url": c["url"],
                    "instagram": ""})
        added += 1
        print("added Post%-4d %-28s web %s  ig %s" % (
            post, e["slug"], web_date, ig_date))

    if args.dry_run:
        print(f"\nDRY RUN -- {added} would be added, nothing written.")
        return 0

    save(os.path.join(POSTS, "reel_scripts.json"), rs)
    save(os.path.join(POSTS, "covers.json"), cv)
    save(os.path.join(POSTS, "lay_summaries.json"), ls)
    save(SOURCE, src)
    print(f"\nadded {added}; now reel_scripts {len(rs)}, covers {len(cv)}, "
          f"lay_summaries {len(ls)}, studies-source {len(src)}")
    print(f"next: python make_covers.py {first_post} {first_post + added - 1}"
          f"  (from ../Posts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
