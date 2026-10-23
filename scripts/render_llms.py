# -*- coding: utf-8 -*-
"""Write /llms.txt: what this site is, for something reading it as a source.

The convention is a short markdown file at the root that says what a site
covers and points at the pages worth reading, so a model does not have to
infer it from navigation.

Generated rather than written by hand, for the reason every other count on
this site is generated: the tracker gains programs most weeks, and a file
that claims "258 programs checked" is wrong the moment one is added. Numbers
and dates here come from the same data files the pages render from, so the
file is either right or the build is broken.

Two things it says that are not boasts and are the point of the file:
what the method is, and what the data does NOT cover. A source that states
its own limits is easier to trust than one that does not, and a program
missing from the tracker means "not checked yet", not "nobody is accepting"
-- which is exactly the inference worth heading off.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
BASE = "https://theclinicalperspective.org"
OUT = os.path.join(SITE, "llms.txt")


def _load(name):
    with io.open(os.path.join(SITE, "data", name), encoding="utf-8") as f:
        return json.load(f)


def render():
    progs = _load("programs.json")
    profs = _load("professors.json")["professors"]
    studies = _load("studies.json")

    programs = progs["programs"]
    posted = [p for p in programs if p["status"] == "posted"]
    accepting = sum(len(p.get("accepting") or []) for p in posted)
    cycle = progs.get("cycle", "")
    updated = progs.get("updated", "")
    schools = len({p["school"] for p in programs})
    newest_study = max((s["date"] for s in studies), default="")

    L = []
    L.append("# The Clinical Perspective")
    L.append("")
    L.append(f"> A free, independently maintained record of which clinical "
             f"psychology doctoral faculty are accepting new students for "
             f"{cycle}, alongside plain-language summaries of peer-reviewed "
             f"mental health research. No account, no paywall, no adverts.")
    L.append("")
    L.append(f"Last updated {updated}. The figures below are written by the "
             f"build from the site's own data, not maintained by hand.")
    L.append("")

    L.append("## Accepting-students tracker")
    L.append("")
    L.append(f"- [Who's accepting doctoral students]({BASE}/tools/faculty-accepting-students.html): "
             f"{accepting} faculty confirmed accepting across {len(posted)} "
             f"programs that have published a list, from {len(programs)} "
             f"programs at {schools} institutions checked so far. Marked up "
             f"as schema.org Dataset and ItemList.")
    L.append(f"- [Search faculty by research interest]({BASE}/tools/professor-search.html): "
             f"{len(profs)} faculty, each interest quoted from their own "
             f"university page.")
    L.append(f"- [All programs]({BASE}/programs/): one page per program, with "
             f"deadlines, GRE requirements, APA outcome disclosures and the "
             f"faculty marked up as schema.org Person.")
    L.append(f"- [Faculty by research topic]({BASE}/professors/): the same "
             f"faculty grouped by what they study.")
    L.append("")

    L.append("## How the tracker is compiled")
    L.append("")
    L.append("- Every faculty name is read from that program's own "
             "admissions or faculty page, and the sentence it came from is "
             "quoted on the entry beside the date it was read.")
    L.append("- Names are never taken from search-engine results or "
             "third-party lists. In testing, search under-reported UCLA as 3 "
             "faculty where the program's page listed 7, and FIU as 6 where "
             "it listed 11.")
    L.append("- Programs are re-checked every two days through the autumn, "
             "and corrections are logged on the entry with their date rather "
             "than edited away.")
    L.append("- \"Cohort admission\" marks programs that admit to the "
             "incoming class and assign an advisor afterwards, so no mentor "
             "list exists to publish.")
    L.append("")

    L.append("## What this does not cover")
    L.append("")
    L.append(f"- A program absent from the tracker has **not been checked "
             f"yet**. It does not mean nobody there is accepting.")
    L.append("- A faculty member absent from a program's list is absent from "
             "the program's own published list. Some programs publish no "
             "list at all.")
    L.append("- Lists change through the cycle. The date on each entry is "
             "the date that page was last read, and is the right thing to "
             "cite alongside the claim.")
    L.append("- Nothing here is admissions advice, and no part of it is "
             "endorsed by the programs it describes.")
    L.append("")

    L.append("## Research summaries")
    L.append("")
    L.append(f"- [Research archive]({BASE}/research.html): {len(studies)} "
             f"peer-reviewed studies summarised in plain language, most "
             f"recent {newest_study}. Each links to the paper and names its "
             f"journal, DOI and PMID.")
    L.append(f"- [Guides]({BASE}/guides/): longer explainers on questions "
             f"that recur.")
    L.append("")

    L.append("## Reuse")
    L.append("")
    L.append("- The accepting-students tracker is published under "
             "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): "
             "quote it, republish it or build on it, including "
             "commercially, with credit to The Clinical Perspective and a "
             "link back. No permission needed.")
    L.append(f"- That covers the compilation — which programs were checked, "
             f"which faculty each names, the status recorded and the dates "
             f"the pages were read. It does not cover the sentences quoted "
             f"from each program's own page, which are those institutions' "
             f"words, nor the research summaries, which are separate. "
             f"[Full scope]({BASE}/legal.html#tracker-licence).")
    L.append("- Please carry the date shown on an entry alongside any figure "
             "taken from it.")
    L.append("")
    L.append("## About and terms")
    L.append("")
    L.append(f"- [About, and who writes this]({BASE}/about.html#who-writes-this)")
    L.append(f"- [Disclaimer and privacy]({BASE}/legal.html)")
    L.append(f"- Corrections: theclinicalperspective@gmail.com — corrections "
             f"to the tracker are made the same day where the program's page "
             f"supports them.")
    L.append("")

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))

    return {"programs": len(programs), "accepting": accepting,
            "professors": len(profs), "studies": len(studies)}
