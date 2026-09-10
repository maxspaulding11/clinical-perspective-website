# -*- coding: utf-8 -*-
"""Check every entry's first author against PubMed.

    python scripts/check_authors.py

Written after comparing scripts/draft.py's output against entries that had been
filled in by hand, which turned up five studies attributed to a slightly wrong
name -- Dylan M. Horton for David M Horton, Ryan Gabriel A. Peji for Ron
Gabriel A Peji, Yi-Ting Lee for Yun-Tse Lee, and two more. Each was close
enough to read as correct and wrong enough to misattribute someone's paper on a
page that links to it. Nothing about the site would have surfaced them.

Two name styles are in use here -- "Surname XY" and "Given M. Surname" -- so
initials are stripped before comparing, and the forename is only checked when
the entry actually carries one. Style is left alone; this is about whether the
name is right.

PubMed is the reference because it is the publisher-deposited record. Anything
it flags is worth confirming against Crossref before editing: two sources
agreeing is what made the five above safe to correct.

Exits non-zero if anything is flagged, so it can gate a build if you ever want
it to. It is not wired into build.py: it makes a network call per entry, which
is not something to put in the path of every rebuild.
"""
import json
import os
import re
import sys
import time
from xml.etree import ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "studies-source.json")

sys.path.insert(0, HERE)
import draft  # noqa: E402  -- reuses its PubMed calls and rate-limit backoff

INITIAL = re.compile(r"^[A-Z]{1,3}\.?$")


def name_tokens(s):
    """Drop "et al." and any initials, leaving the parts that are real names."""
    s = re.sub(r",?\s*et\.?\s+al\.?$", "", s or "", flags=re.I).strip().rstrip(",")
    return [t.rstrip(".,") for t in s.split() if not INITIAL.match(t)]


def first_authors(pmids):
    """Batch the lookups: 20 ids per request rather than one request per study."""
    out = {}
    for i in range(0, len(pmids), 20):
        xml = ElementTree.fromstring(
            draft.eutils("efetch.fcgi", db="pubmed",
                         id=",".join(pmids[i:i + 20]), retmode="xml"))
        for art in xml.iter("PubmedArticle"):
            author = art.find(".//AuthorList/Author")
            if author is None:
                continue
            out[art.findtext(".//PMID")] = (
                (author.findtext("ForeName") or "").strip(),
                (author.findtext("LastName") or "").strip())
        time.sleep(0.5)
    return out


def main():
    entries = json.load(open(SOURCE, encoding="utf-8"))

    resolved = []
    for e in entries:
        if e.get("draft"):
            continue
        pmid = e.get("pmid")
        if not pmid and e.get("doi"):
            try:
                pmid = draft.pmid_from_doi(e["doi"])
                time.sleep(0.35)
            except Exception:
                pmid = None
        if pmid:
            resolved.append((e, str(pmid)))

    truth = first_authors([p for _, p in resolved])
    problems = []

    for e, pmid in resolved:
        if pmid not in truth or not e.get("authors"):
            continue
        fore, last = truth[pmid]
        site = [t.lower() for t in name_tokens(e["authors"])]
        if not site or not last:
            continue

        if last.lower() not in site:
            problems.append((e, pmid, fore, last, "surname"))
        elif site[-1] == last.lower() and len(site) > 1 and fore:
            # "Given ... Surname" style, so the forename is checkable too.
            # Initials are already gone, so only compare spelled-out names.
            theirs, ours = fore.split()[0].lower(), site[0]
            if len(ours) > 2 and len(theirs) > 2 and ours != theirs:
                problems.append((e, pmid, fore, last, "forename"))

    print(f"checked {len(resolved)} entries against PubMed")
    if not problems:
        print("every first author matches")
        return 0

    print(f"\n{len(problems)} to look at:\n")
    for e, pmid, fore, last, kind in problems:
        print(f"  [{kind}] entry {e['index']}: {e['title'][:56]}")
        print(f"      here   : {e['authors']}")
        print(f"      PubMed : {fore} {last}")
        print(f"      https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        print()
    print("Confirm against Crossref before editing. Where the two agree, the "
          "entry is wrong.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
