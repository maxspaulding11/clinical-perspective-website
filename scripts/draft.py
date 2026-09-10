# -*- coding: utf-8 -*-
"""Scaffold a draft study entry from a PMID or DOI.

    python scripts/draft.py 42597212
    python scripts/draft.py 10.3389/fpsyt.2026.1865917
    python scripts/draft.py 42597212 --date 2026-09-20 --tag Assessment
    python scripts/draft.py 42597212 --instagram https://www.instagram.com/p/ABC123/
    python scripts/draft.py 42597212 --dry-run

What it fills in, and what it deliberately will not:

  Filled, from the source of record -- journal, authors, publication date,
  PMID, DOI, the link to the paper. These are facts with an authority to check
  them against, so a machine should copy them and a person should not retype
  them. Every one comes from PubMed or Crossref, never from a search summary.

  NOT filled -- the title, the blurb, the summary, the tag. Those are the
  claims a reader trusts, and every one of them has to trace to the paper. A
  generated summary would read exactly as confidently as a written one and be
  wrong in ways nobody could see, so this writes TODO markers instead and
  build.py refuses to publish an entry that still has them.

The abstract is printed to the terminal to read, and is not written into the
file. It is the paper's words, not ours, and the summaries here are ours.

A new entry is marked "draft": true. build.py skips drafts no matter what date
they carry, so a half-written entry cannot go live by the calendar catching up
with it. Delete that line when the writing is done.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from xml.etree import ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "studies-source.json")

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CROSSREF = "https://api.crossref.org/works/"
TOOL = "the-clinical-perspective"

# NCBI asks callers to identify themselves with an email so they can get in
# touch before rate-limiting you. Fill this in if you like; it is left empty
# rather than filled in for you, because it gets sent to a third party on every
# request.
CONTACT_EMAIL = ""

TODO = "TODO"
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
PMID_RE = re.compile(r"^\d{5,9}$")

TAGS = ["Addiction", "Assessment", "Diagnosis", "Digital Health", "Forensic",
        "Genetics", "Myth Check", "Neurodevelopmental", "Neuroscience",
        "Personality", "Psychedelics", "Psychopharmacology", "Psychosis",
        "Public Health", "Stigma", "Training", "Trauma", "Treatment"]


def get(url, tries=4):
    """NCBI allows a few requests a second and answers 429 past that. Backing
    off and retrying is the difference between this working and it failing on
    the third study of an afternoon."""
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/1.0"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as err:
            if err.code != 429 or attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def eutils(path, **params):
    params.setdefault("tool", TOOL)
    if CONTACT_EMAIL:
        params.setdefault("email", CONTACT_EMAIL)
    return get(f"{EUTILS}/{path}?" + urllib.parse.urlencode(params))


def pmid_from_doi(doi):
    data = json.loads(eutils("esearch.fcgi", db="pubmed", retmode="json",
                             term=f"{doi}[DOI]"))
    ids = data.get("esearchresult", {}).get("idlist") or []
    return ids[0] if ids else None


def fmt_authors(names):
    """First author, then "et al." -- how the citation line on a study page
    reads. The name itself is formatted by whichever source supplied it."""
    if not names:
        return ""
    first = names[0]
    return first if len(names) == 1 else f"{first}, et al."


def from_pubmed(pmid):
    summary = json.loads(eutils("esummary.fcgi", db="pubmed", id=pmid,
                                retmode="json"))
    rec = summary.get("result", {}).get(str(pmid))
    if not rec or rec.get("error"):
        return None

    authors = [a["name"] for a in rec.get("authors", [])
               if a.get("authtype") == "Author"]
    doi = ""
    for aid in rec.get("articleids", []):
        if aid.get("idtype") == "doi":
            doi = aid.get("value", "")

    # PubMed carries two dates: the issue the paper appeared in, and the date
    # it went online ahead of that issue. Existing entries use both -- six
    # follow the online date, five the issue date, and one follows neither --
    # so there is no house rule to encode here. The default below is the
    # common case; both are printed so the choice is visible, and --pubdate
    # overrides it.
    issue = tidy_pubdate(rec.get("pubdate", ""))
    online = tidy_pubdate(rec.get("epubdate", ""))

    return {
        "paperTitle": (rec.get("title") or "").rstrip("."),
        "journal": rec.get("fulljournalname") or rec.get("source") or "",
        "authors": fmt_authors(authors),
        "pubdate": pick_pubdate(issue, online),
        "issueDate": issue,
        "onlineDate": online,
        "pmid": str(pmid),
        "doi": doi,
    }


def pick_pubdate(issue, online):
    """Prefer the online-first date when it belongs to the same year as the
    issue -- a paper that appeared in July and was bound into the September
    issue is July's news. When the online date falls in an earlier year, the
    issue date is the one the entries use."""
    if not online:
        return issue
    if not issue:
        return online
    return issue if issue.split()[-1] != online.split()[-1] else online


def from_crossref(doi):
    """Fallback for anything PubMed does not index."""
    try:
        msg = json.loads(get(CROSSREF + urllib.parse.quote(doi)))["message"]
    except Exception:
        return None
    # "Dylan M. Horton" rather than PubMed's "Horton DM". Two thirds of the
    # entries already here are written the first way, and Crossref is where the
    # given name with its middle initial survives.
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip()
               for a in msg.get("author", []) if a.get("family")]
    parts = (msg.get("published-print") or msg.get("published-online")
             or msg.get("issued") or {}).get("date-parts", [[]])[0]
    pub = ""
    if parts:
        y = parts[0]
        m = parts[1] if len(parts) > 1 else None
        pub = f"{date(y, m, 1).strftime('%B')} {y}" if m else str(y)
    return {
        "paperTitle": (msg.get("title") or [""])[0].strip(),
        "journal": (msg.get("container-title") or [""])[0],
        "authors": fmt_authors(authors),
        "pubdate": pub,
        "pmid": "",
        "doi": msg.get("DOI", doi),
    }


def tidy_pubdate(raw):
    """PubMed gives "2026 Jul 14" or "2026 Jul"; entries here read "July 2026"."""
    m = re.match(r"(\d{4})\s+([A-Za-z]{3})", raw or "")
    if not m:
        return (raw or "").split()[0] if raw else ""
    try:
        month = date(2000, ["jan", "feb", "mar", "apr", "may", "jun", "jul",
                            "aug", "sep", "oct", "nov", "dec"]
                     .index(m.group(2).lower()) + 1, 1).strftime("%B")
    except ValueError:
        return raw
    return f"{month} {m.group(1)}"


def abstract(pmid):
    try:
        xml = ElementTree.fromstring(eutils("efetch.fcgi", db="pubmed",
                                            id=pmid, retmode="xml"))
    except Exception:
        return ""
    out = []
    for node in xml.iter("AbstractText"):
        label = node.get("Label")
        text = "".join(node.itertext()).strip()
        out.append(f"{label}: {text}" if label else text)
    return "\n\n".join(out)


def next_date(entries):
    """One study goes out per day, so the obvious slot is the day after the
    last one already scheduled."""
    dates = [e["date"] for e in entries if e.get("date")]
    if not dates:
        return date.today().isoformat()
    y, m, d = (int(x) for x in max(dates).split("-"))
    return (date(y, m, d) + timedelta(days=1)).isoformat()


def wrap(text, width=76, indent="    "):
    out, line = [], indent
    for word in text.split():
        if len(line) + len(word) + 1 > width and line.strip():
            out.append(line)
            line = indent
        line += ("" if line == indent else " ") + word
    if line.strip():
        out.append(line)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="Scaffold a draft study entry from a PMID or DOI.")
    ap.add_argument("id", help="PubMed ID or DOI")
    ap.add_argument("--date", help="publication date on the site (YYYY-MM-DD)")
    ap.add_argument("--tag", help="one of: " + ", ".join(TAGS))
    ap.add_argument("--pubdate", help='override the paper date, e.g. "July 2026"')
    ap.add_argument("--instagram", default="", help="permalink to the post")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the entry without writing it")
    args = ap.parse_args()

    raw = args.id.strip()
    if raw.startswith("http"):
        m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", raw)
        raw = m.group(1) if m else re.sub(r"^https?://(dx\.)?doi\.org/", "", raw)

    if PMID_RE.match(raw):
        pmid, doi = raw, None
    elif DOI_RE.match(raw):
        doi, pmid = raw, pmid_from_doi(raw)
        if not pmid:
            print(f"note: {doi} is not in PubMed, falling back to Crossref")
    else:
        raise SystemExit(f"'{args.id}' is not a PMID or a DOI")

    rec = from_pubmed(pmid) if pmid else None
    if rec is None:
        rec = from_crossref(doi) if doi else None
    if rec is None:
        raise SystemExit(f"could not resolve {args.id} at PubMed or Crossref")
    if doi and not rec["doi"]:
        rec["doi"] = doi

    # PubMed's journal names are its own house style -- "The lancet.
    # Psychiatry", "Eur Arch Psychiatry Clin Neurosci" -- while Crossref
    # carries the name the publisher uses, which is the one every existing
    # entry here is written in. Worth the extra request to not hand-correct
    # this every time.
    if rec["doi"]:
        cross = from_crossref(rec["doi"])
        if cross and cross["journal"]:
            rec["journal"] = cross["journal"]
        if cross and cross["authors"]:
            rec["authors"] = cross["authors"]
        # Take whichever date is more specific. Some PubMed records carry only
        # the year where Crossref has the month, and the entries here read
        # "July 2026" rather than "2026".
        if cross and cross["pubdate"]:
            has_month = " " in (rec["pubdate"] or "").strip()
            if not has_month and " " in cross["pubdate"].strip():
                rec["pubdate"] = cross["pubdate"]

    if args.pubdate:
        rec["pubdate"] = args.pubdate

    if args.tag and args.tag not in TAGS:
        raise SystemExit(f"unknown tag '{args.tag}'. Known tags: "
                         + ", ".join(TAGS))

    entries = json.load(open(SOURCE, encoding="utf-8"))
    entry = {
        "index": max(e["index"] for e in entries) + 1,
        "date": args.date or next_date(entries),
        "title": f"{TODO} title -- rewrite as the question a reader would "
                 f"search for. The paper calls it: {rec['paperTitle']}",
        "tag": args.tag or f"{TODO} tag -- one of: " + ", ".join(TAGS),
        "blurb": f"{TODO} blurb -- one or two sentences, the finding and the "
                 f"numbers behind it.",
        "summary": f"{TODO} summary -- written from the paper, not from the "
                   f"abstract below and not from a search result. Include what "
                   f"would make a reader doubt it.",
        "journal": rec["journal"],
        "authors": rec["authors"],
        "pubdate": rec["pubdate"],
        "pmid": rec["pmid"],
        "doi": rec["doi"],
        "url": (f"https://pubmed.ncbi.nlm.nih.gov/{rec['pmid']}/" if rec["pmid"]
                else f"https://doi.org/{rec['doi']}"),
        "instagram": args.instagram,
        "draft": True,
    }

    print()
    print(f"  index    {entry['index']}")
    print(f"  date     {entry['date']}  (draft, so it will not publish on it)")
    print(f"  paper    {rec['paperTitle']}")
    print(f"  journal  {rec['journal']}")
    print(f"  authors  {rec['authors']}")
    alt = [d for d in (rec.get("issueDate"), rec.get("onlineDate"))
           if d and d != rec["pubdate"]]
    print(f"  pubdate  {rec['pubdate']}"
          + (f"   <- chosen; PubMed also lists {' and '.join(alt)}"
             f" (--pubdate overrides)" if alt else ""))
    print(f"  pmid     {rec['pmid'] or '(none)'}")
    print(f"  doi      {rec['doi'] or '(none)'}")
    print(f"  url      {entry['url']}")
    if args.instagram:
        print(f"  post     {args.instagram}")

    if rec["pmid"]:
        text = abstract(rec["pmid"])
        if text:
            print("\n  The paper's abstract, to read -- not copied into the "
                  "entry, and not\n  a substitute for the paper:\n")
            for para in text.split("\n\n"):
                print(wrap(para))
                print()

    if args.dry_run:
        print("  --dry-run: nothing written\n")
        return 0

    entries.append(entry)
    with open(SOURCE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  Written to scripts/studies-source.json as entry "
          f"{entry['index']}.\n")
    print("  Still to write, by hand, from the paper:")
    print("    title    the question a reader would search for")
    if not args.tag:
        print("    tag      " + ", ".join(TAGS[:6]) + ", ...")
    print("    blurb    the finding and its numbers, one or two sentences")
    print("    summary  including the caveat that would make a reader doubt it")
    print()
    print('  Then delete the "draft": true line and run scripts/build.py.')
    print("  Until you do, the build skips it and says so.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
