# -*- coding: utf-8 -*-
"""Turn a batch of Reels into a manifest the publisher can run from.

The pipeline in ../Posts already produces everything a post needs, but it
produces it for a human: an .mp4 and a cover .png sitting in a month folder,
and the words for them in a .docx meant to be read and copied by hand. This
reads both and writes data/reels.json, which is the same information in the
one shape the Instagram API wants -- a date, two public URLs, and a caption.

Two things it deliberately does NOT do:

  It does not post. Writing the manifest and publishing from it are separate
  so that the whole batch can be checked, and corrected, while nothing has
  gone out. ig_publish.py is the half that talks to Instagram.

  It does not invent captions. Every line comes from the .docx the pipeline
  already writes. If a post is missing its summary or its hashtags, that is
  an error here rather than a thinner caption on the day.

Media is staged into media/reels/, which is gitignored here and pushed to a
separate repo instead -- see BASE_URL. A public URL is the only form the
Instagram API accepts: it fetches the video and the cover itself, so a local
path, a localhost address or anything behind a login all fail.

Usage:
  python scripts/ig_manifest.py "../Posts/Videos/October 2026" \
      "../Posts/Content/Post67-87 Lay Summaries & Hashtags.docx" --year 2026
"""
import argparse
import datetime
import json
import os
import re
import shutil
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
MEDIA = os.path.join(SITE, "media", "reels")
OUT = os.path.join(SITE, "data", "reels.json")

# Where the media is served from, which is deliberately NOT this site.
#
# A batch of Reels is about 33MB against a repo whose entire history is 6MB,
# so committing them here would grow it by roughly 560MB a year -- permanently,
# because git keeps every blob forever -- for files that are already public on
# Instagram the moment they post. They live in their own repo instead, served
# by GitHub Pages, which can be emptied or deleted outright when it gets large
# without touching a single thing the site depends on.
BASE_URL = os.environ.get(
    "REEL_MEDIA_BASE", "https://maxspaulding11.github.io/tcp-reel-media")

# Instagram rejects a caption over 2,200 characters outright, so a post that
# would be truncated is a failure to fix here, not on the day.
CAPTION_MAX = 2200

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# "1.  Sep 17  --  Post67_PEvsCPT" -- the separator is an em dash in the
# document, but these files have been through enough encodings that matching
# only one dash character is asking to be broken by a copy-paste.
ENTRY_RE = re.compile(
    r"^\s*(\d+)\.\s+([A-Z][a-z]{2})\s+(\d{1,2})\s*[-‐-―]+\s*(\S+)\s*$")


def docx_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        text = re.sub(r"<[^>]+>", "", text)
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&apos;", "'"))
        text = unicodedata.normalize("NFKC", text).strip()
        if text:
            out.append(text)
    return out


def parse_docx(path, year):
    """Split the document into one record per post.

    The structure is positional rather than labelled -- headline, body, then
    journal, identifiers, authors, date, then hashtags -- so this keys off the
    two lines that ARE identifiable (the numbered heading and the "Hashtags:"
    line) and treats everything between them as the post's own.
    """
    paras = docx_paragraphs(path)
    posts, current = {}, None
    for line in paras:
        m = ENTRY_RE.match(line)
        if m:
            _, mon, day, post_id = m.groups()
            if mon not in MONTHS:
                continue
            current = {
                "postId": post_id,
                "day": datetime.date(year, MONTHS[mon], int(day)).isoformat(),
                "lines": [],
                "hashtags": "",
            }
            posts[post_id] = current
            continue
        if current is None:
            continue
        if line.lower().startswith("hashtags:"):
            current["hashtags"] = line.split(":", 1)[1].strip()
            current = None  # everything after this belongs to the next post
            continue
        current["lines"].append(line)
    return posts


def dashes(s):
    """Write the document's " -- " as a real em dash.

    The .docx is typed in ASCII, which is fine in a Word file nobody but the
    author reads. In a caption it looks like a typo, and it is the only
    difference between what the pipeline writes and what a person would have
    typed into Instagram by hand. Spaced only -- an unspaced "--" inside a
    word is far more likely to be a range or a filename than a dash."""
    return s.replace(" -- ", " — ")


def caption_for(rec):
    """Headline, summary, source, hashtags -- in that order, nothing invented.

    The lines between the heading and the hashtags are, in order: headline,
    summary, journal, identifiers, authors, month. The identifiers are dropped
    because a PMID in an Instagram caption helps nobody; the journal and
    authors stay, because a claim about a study should say whose study.
    """
    lines = [dashes(l) for l in rec["lines"]]
    if len(lines) < 2:
        raise ValueError(f"{rec['postId']}: only {len(lines)} lines of copy")
    headline, summary = lines[0], lines[1]
    source = [l for l in lines[2:] if not l.startswith(("PMID", "DOI"))]
    parts = [headline, summary]
    if source:
        parts.append(" · ".join(source))
    if rec["hashtags"]:
        parts.append(rec["hashtags"])
    return "\n\n".join(parts)


def find_media(folder):
    """Pair each .mp4 with the cover sitting beside it.

    The pipeline names them "<date> <PostID>.mp4" and "<date> <PostID>
    cover.png", so the video's stem is the cover's stem minus " cover". A
    video with no cover is an error: Instagram would pick its own frame, and
    the covers are the only reason the profile grid looks deliberate.
    """
    pairs = {}
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".mp4"):
            continue
        stem = name[:-4]
        cover = os.path.join(folder, stem + " cover.png")
        if not os.path.exists(cover):
            raise SystemExit(f"no cover for {name} -- expected {stem} cover.png")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\S+)$", stem)
        if not m:
            raise SystemExit(f"cannot read a date and post id from {name}")
        pairs[m.group(2)] = {
            "day": m.group(1),
            "video": os.path.join(folder, name),
            "cover": cover,
        }
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="a month folder under Posts/Videos")
    # A month folder is not the same unit as a batch. October 2026 holds the
    # tail of Post67-87 and all of Post88-108, so its copy lives in two
    # documents and taking only one would leave a week of posts with no
    # caption -- which find_media would then report as missing copy rather
    # than as a missing argument.
    ap.add_argument("docx", nargs="+",
                    help="the Lay Summaries & Hashtags .docx files covering "
                         "that folder; pass as many as it spans")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--time", default="09:00",
                    help="local time of day to post, HH:MM (default 09:00)")
    args = ap.parse_args()

    media = find_media(args.folder)
    copy = {}
    for path in args.docx:
        found = parse_docx(path, args.year)
        clash = set(found) & set(copy)
        if clash:
            raise SystemExit("the same post appears in two documents: "
                             + ", ".join(sorted(clash)))
        copy.update(found)

    missing = sorted(set(media) - set(copy))
    if missing:
        raise SystemExit("no copy in the .docx for: " + ", ".join(missing))

    os.makedirs(MEDIA, exist_ok=True)
    entries, warnings = [], []
    for post_id, m in sorted(media.items(), key=lambda kv: kv[1]["day"]):
        rec = copy[post_id]
        if rec["day"] != m["day"]:
            # The filename and the document disagree about the date. The
            # filename wins -- it is what the pipeline scheduled -- but this
            # is worth saying out loud, because one of them is wrong.
            warnings.append(f"{post_id}: file says {m['day']}, "
                            f"document says {rec['day']} -- using {m['day']}")
        caption = caption_for(rec)
        if len(caption) > CAPTION_MAX:
            raise SystemExit(f"{post_id}: caption is {len(caption)} characters, "
                             f"Instagram's limit is {CAPTION_MAX}")
        video_name = os.path.basename(m["video"]).replace(" ", "_")
        cover_name = os.path.basename(m["cover"]).replace(" ", "_")
        shutil.copy2(m["video"], os.path.join(MEDIA, video_name))
        shutil.copy2(m["cover"], os.path.join(MEDIA, cover_name))
        entries.append({
            "postId": post_id,
            "day": m["day"],
            "time": args.time,
            "videoUrl": f"{BASE_URL}/media/reels/{video_name}",
            "coverUrl": f"{BASE_URL}/media/reels/{cover_name}",
            "caption": caption,
            "captionChars": len(caption),
        })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "_readme": ("Generated by scripts/ig_manifest.py from the Reels "
                        "pipeline in ../Posts. Do not edit by hand -- re-run "
                        "the script. scripts/ig_publish.py reads this."),
            "builtOn": datetime.date.today().isoformat(),
            "posts": entries,
        }, f, indent=1, ensure_ascii=False)
        f.write("\n")

    for w in warnings:
        print("  warning: " + w)
    print(f"{len(entries)} posts written to data/reels.json")
    print(f"  {entries[0]['day']} -> {entries[-1]['day']}")
    print(f"  longest caption: {max(e['captionChars'] for e in entries)} "
          f"of {CAPTION_MAX} characters")
    print(f"  media copied into media/reels/ "
          f"({sum(os.path.getsize(os.path.join(MEDIA, os.path.basename(e['videoUrl']))) for e in entries) / 1048576:.0f} MB of video)")


if __name__ == "__main__":
    main()
