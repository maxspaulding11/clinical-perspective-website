# -*- coding: utf-8 -*-
"""Write Reddit-ready drafts for a batch, to be posted by hand.

Deliberately not automated past this point. Reddit's API would allow posting,
but a daily feed of your own links is spam by any subreddit's definition and
the bans are per-subreddit and permanent. Posting one or two a week, by hand,
to a sub whose rules you have read, is the only version of this that works.

So this does the writing and leaves the judgment: for each post in a batch it
produces titles and a body in Reddit's register, which is not Instagram's.
What changes:

  No hashtags, no handle, no "link in bio". They read as advertising.
  The finding goes in the title. Reddit rewards a title that is the claim.
  The body stands on its own. A post that only makes sense after clicking
  through gets downvoted, so the number and the caveat are both in the text.
  The source is named. This audience checks.

Ordered with the null and weaker-than-claimed findings first, because those
are what this feed does that nobody else does, and they are the ones that get
read rather than scrolled past.

    python scripts/reddit_drafts.py 109 129
"""
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
LAY = os.path.join(POSTS, "lay_summaries.json")
SOURCE = os.path.join(HERE, "studies-source.json")
OUTDIR = os.path.join(POSTS, "Content")

# Where each kind of finding has a chance of being welcome. Deliberately
# short: the two general subs carry most of it, and a post that fits nowhere
# obvious is usually a post that should not be made.
SUBS = {
    "Treatment":      ["r/psychologystudents", "r/AcademicPsychology"],
    "Psychosis":      ["r/AcademicPsychology", "r/schizophrenia"],
    "Personality":    ["r/AcademicPsychology", "r/BPD"],
    "Trauma":         ["r/AcademicPsychology", "r/psychologystudents"],
    "Addiction":      ["r/AcademicPsychology", "r/psychologystudents"],
    "Forensic":       ["r/AcademicPsychology", "r/psychologystudents"],
    "Myth Check":     ["r/psychologystudents", "r/AcademicPsychology"],
    "Assessment":     ["r/AcademicPsychology", "r/psychometrics"],
    "Neuroscience":   ["r/neuroscience", "r/AcademicPsychology"],
    "Public Health":  ["r/psychologystudents", "r/AcademicPsychology"],
    "Digital Health": ["r/psychologystudents", "r/AcademicPsychology"],
    "Diagnosis":      ["r/AcademicPsychology", "r/psychologystudents"],
}
DEFAULT_SUBS = ["r/psychologystudents", "r/AcademicPsychology"]

# The language that marks a post as one of the honest ones. Same list the
# candidate scorer uses, for the same reason.
WEAK = ("did not", "no significant", "not associated", "no evidence",
        "failed to", "not reach", "very low certainty", "cannot be",
        "weaker", "null", "no effect", "did not reach", "not statistically")


def is_weak(rec):
    blob = (rec["title"] + " " + rec["summary"]).lower()
    return any(w in blob for w in WEAK)


def first_sentences(text, n):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def titles_for(rec):
    """Two angles: the finding as stated, and the tension in it.

    The second is usually the better post. "X worked" is a press release;
    "X worked, and missed its own threshold" is a discussion.
    """
    head = rec["title"].rstrip(".")
    out = [head]
    s = rec["summary"]
    m = re.search(r"([^.]*\b(?:but|however|though|although)\b[^.]*)\.", s)
    if m:
        clause = m.group(1).strip()
        if 40 < len(clause) < 180:
            out.append(clause[0].upper() + clause[1:])
    return out[:2]


def body_for(rec, url):
    """Method, number, caveat, source -- in Reddit's register."""
    summary = rec["summary"].strip()
    lines = [
        summary,
        "",
        f"Source: {rec['journal']}, {rec['authors']}, {rec['pubdate']}. "
        f"DOI: {rec['doi']}",
        "",
        f"I write these up daily at {url} -- happy to be told where I've got "
        f"something wrong.",
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python scripts/reddit_drafts.py <first> <last>")
    lo, hi = int(sys.argv[1]), int(sys.argv[2])

    lay = {p["post"]: p for p in json.load(io.open(LAY, encoding="utf-8"))}
    src = {e["index"]: e for e in json.load(io.open(SOURCE, encoding="utf-8"))}

    recs = []
    for post in range(lo, hi + 1):
        if post not in lay or post not in src:
            continue
        p, s = lay[post], src[post]
        recs.append({"post": post, "slug": p["slug"], "tag": s["tag"],
                     "title": s["title"], "summary": p["summary"],
                     "journal": p["journal"], "authors": p["authors"],
                     "pubdate": p["pubdate"], "doi": p["doi"],
                     "pmid": p["pmid"], "date": p["date"]})
    if not recs:
        raise SystemExit(f"no posts found in the range {lo}-{hi}")

    # Honest findings first; they are the ones worth a post.
    recs.sort(key=lambda r: (not is_weak(r), r["post"]))
    weak = sum(1 for r in recs if is_weak(r))

    site = "theclinicalperspective.org"
    out = os.path.join(OUTDIR, f"Post{lo}-{hi} Reddit Drafts.md")
    L = []
    L.append(f"# Reddit drafts — Post{lo} to Post{hi}")
    L.append("")
    L.append(f"{len(recs)} drafts, strongest first. {weak} report a null, "
             f"negative or weaker-than-claimed finding — post those.")
    L.append("")
    L.append("**Before posting anything:**")
    L.append("")
    L.append("- One or two a week, not one a day. The same link posted often "
             "is what spam filters and mods look for.")
    L.append("- Read the subreddit's rules, then search it for \"self "
             "promotion\" to see how mods have handled it before.")
    L.append("- Several run application-season megathreads. A comment there "
             "is usually better received than a post, and lasts longer.")
    L.append("- If it's ambiguous, message the mods first. A one-line ask "
             "costs nothing against a ban you can't appeal.")
    L.append("- Vary the title between subs. Identical crossposts read as a "
             "bot.")
    L.append("")
    L.append("---")

    for r in recs:
        subs = SUBS.get(r["tag"], DEFAULT_SUBS)
        L.append("")
        L.append(f"## Post{r['post']} · {r['tag']} · {r['date']}"
                 + ("  **[honest finding]**" if is_weak(r) else ""))
        L.append("")
        L.append(f"*Suggested: {', '.join(subs)}*")
        L.append("")
        for i, t in enumerate(titles_for(r), 1):
            L.append(f"**Title {i}:** {t}")
            L.append("")
        L.append("**Body:**")
        L.append("")
        L.append("```")
        L.append(body_for(r, site))
        L.append("```")
        L.append("")
        L.append(f"<sub>PMID {r['pmid']} · {r['journal']}</sub>")
        L.append("")
        L.append("---")

    os.makedirs(OUTDIR, exist_ok=True)
    io.open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)}")
    print(f"  {len(recs)} drafts, {weak} of them honest findings")
    print(f"  longest body: {max(len(body_for(r, site)) for r in recs)} characters")


if __name__ == "__main__":
    sys.exit(main())
