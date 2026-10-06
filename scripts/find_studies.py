# -*- coding: utf-8 -*-
"""Find candidate studies for the next batch, and say how much queue is left.

Two jobs, and the first one matters more than it sounds. In October 2026 the
website's study feed was one day from running out and nobody noticed, because
the Instagram queue was the deadline being watched and the site runs two days
ahead of it. This reports both, from the files themselves.

The second job is the mechanical half of building a batch: query PubMed across
the topics this feed covers, drop anything already used, and write what is
left to a working file with enough of each abstract to judge it. Choosing
which 21 to run, and writing the summaries, is not automated and should not be
-- every claim on this feed traces to a paper somebody read.

    python scripts/find_studies.py              # report queue; search if low
    python scripts/find_studies.py --force      # search regardless
    python scripts/find_studies.py --days 10    # change the low-queue threshold
    python scripts/find_studies.py --since 45   # widen the publication window

Writes ../Posts/Content/Batch<N> Candidates.json, which is deliberately
outside this repo: it is working material for one batch, not something the
site serves.
"""
import argparse
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
POSTS = os.path.join(ROOT, "Posts")
SOURCE = os.path.join(HERE, "studies-source.json")
COVERS = os.path.join(POSTS, "covers.json")
LAY = os.path.join(POSTS, "lay_summaries.json")
OUTDIR = os.path.join(POSTS, "Content")

E = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# The topics this feed actually covers. Kept here rather than retyped each
# batch so successive batches are drawn from the same net, and so a topic that
# stops producing anything is visible as a zero rather than as an absence.
TOPICS = {
    "psychosis":   '("schizophrenia"[tiab] OR "first-episode psychosis"[tiab] OR "clozapine"[tiab])',
    "personality": '("personality disorder"[tiab] OR "borderline personality"[tiab])',
    "trauma":      '("PTSD"[tiab] OR "posttraumatic stress"[tiab] OR "moral injury"[tiab])',
    "forensic":    '("forensic psychiatry"[tiab] OR "forensic psychology"[tiab] OR "criminal responsibility"[tiab])',
    "addiction":   '("alcohol use disorder"[tiab] OR "opioid use disorder"[tiab] OR "gambling disorder"[tiab])',
    "treatment":   '("psychotherapy"[tiab] AND ("randomized"[tiab] OR "randomised"[tiab]))',
    "assessment":  '("diagnostic accuracy"[tiab] OR "psychometric"[tiab] OR "measurement invariance"[tiab])',
    "mood":        '("major depressive disorder"[tiab] OR "bipolar disorder"[tiab] OR "treatment-resistant depression"[tiab])',
    "neuro":       '("neuroimaging"[tiab] AND ("psychiatric"[tiab] OR "mental health"[tiab]))',
    "mythcheck":   '("replication"[tiab] OR "publication bias"[tiab] OR "overestimat*"[tiab]) AND ("psycholog*"[tiab] OR "psychiatr*"[tiab])',
}

# PubMed's topic filters are leaky: "diagnostic accuracy" alone pulls in
# oncology, endoscopy and orthopaedics, and the first run of this script
# ranked bone biopsies and biopsy needles near the top.
#
# Excluding by keyword alone does not work -- the list is endless and a
# missing plural lets "gynecologic tumors" through. So a candidate has to
# EARN its place by containing something unmistakably about mental health,
# and is then dropped if it is also plainly about an organ.
ON_TOPIC = re.compile(
    r"\b(psycholog\w*|psychiatr\w*|mental health|mental illness|depress\w*|"
    r"anxiet\w*|anxious|PTSD|post-?traumatic|trauma\w*|schizophren\w*|"
    r"psychosis|psychotic|bipolar|personality disorder|borderline|"
    r"addict\w*|alcohol use|opioid use|substance use|suicid\w*|self-?harm|"
    r"psychotherap\w*|cognitive behavi\w*|CBT|counsell?ing|antipsychotic\w*|"
    r"antidepress\w*|wellbeing|well-being|burnout|loneliness|ADHD|autis\w*|"
    r"eating disorder|insomnia|dementia|cognitive decline|forensic)\b", re.I)

OFF_TOPIC = re.compile(
    r"\b(cancers?|carcinomas?|tumou?rs?|melanomas?|oncolog\w*|hepat\w*|"
    r"gliomas?|myelo\w*|lupus|asthma|malaria|influenza|vaccin\w*|HIV|"
    r"fibrosis|glaucoma|cataracts?|dental|orthopaed\w*|orthoped\w*|"
    r"fractures?|arthroplast\w*|stents?|biops\w*|endoscop\w*|colonoscop\w*|"
    r"osteomyelitis|insemination|fertilit\w*|gynecolog\w*|gynaecolog\w*|"
    r"dermatolog\w*|nephrolog\w*|cardiac surgery)\b", re.I)


def fetch(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def used_pmids():
    """Everything ever published, from both sequences."""
    used = set()
    for path, key in ((SOURCE, "pmid"), (LAY, "pmid")):
        if not os.path.exists(path):
            continue
        for e in json.load(io.open(path, encoding="utf-8")):
            if e.get(key):
                used.add(str(e[key]))
    return used


def queue_state():
    """How many days of content remain, on each sequence separately.

    They are separate on purpose and have drifted: Instagram runs two days
    behind the website for the same study, so one number cannot describe both.
    """
    today = datetime.date.today()
    out = {"today": today.isoformat()}

    src = json.load(io.open(SOURCE, encoding="utf-8"))
    web_last = max(datetime.date.fromisoformat(e["date"]) for e in src)
    out["website"] = {"lastDate": web_last.isoformat(),
                      "daysLeft": (web_last - today).days,
                      "lastIndex": max(e["index"] for e in src)}

    if os.path.exists(COVERS):
        cov = json.load(io.open(COVERS, encoding="utf-8"))
        ig_last = max(datetime.date.fromisoformat(c["date"]) for c in cov)
        out["instagram"] = {"lastDate": ig_last.isoformat(),
                            "daysLeft": (ig_last - today).days,
                            "lastPost": max(c["post"] for c in cov)}
    return out


def search(since_days, per_topic, used):
    start = (datetime.date.today()
             - datetime.timedelta(days=since_days)).strftime("%Y/%m/%d")
    date_q = f'("{start}"[PDAT] : "3000"[PDAT])'
    filt = "AND free full text[sb] AND humans[Filter] AND English[lang]"

    found, per_topic_counts = {}, {}
    for name, q in TOPICS.items():
        term = f"{q} AND {date_q} {filt}"
        url = E + "esearch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed", "term": term, "retmax": str(per_topic),
            "retmode": "json", "sort": "date"})
        try:
            ids = json.loads(fetch(url))["esearchresult"]["idlist"]
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: query failed ({e})")
            per_topic_counts[name] = 0
            continue
        new = [i for i in ids if i not in used]
        per_topic_counts[name] = len(new)
        for i in new:
            found.setdefault(i, []).append(name)
        print(f"  {name:<12} {len(ids):>3} hits, {len(new):>3} new")
        time.sleep(0.4)
    return found, per_topic_counts


def details(pmids):
    """Title, journal, type and abstract for each candidate."""
    out = {}
    for i in range(0, len(pmids), 40):
        chunk = pmids[i:i + 40]
        url = E + "efetch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
        xml = fetch(url)
        for a in re.findall(r"<PubmedArticle>.*?</PubmedArticle>", xml, re.S):
            pmid = re.search(r"<PMID[^>]*>(\d+)</PMID>", a).group(1)
            def clean(s):
                s = re.sub(r"<[^>]+>", "", s)
                s = re.sub(r"&#x([0-9a-fA-F]+);",
                           lambda m: chr(int(m.group(1), 16)), s)
                for x, y in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                             ("&quot;", '"'), ("&apos;", "'")):
                    s = s.replace(x, y)
                return re.sub(r"\s+", " ", s).strip()
            tm = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", a, re.S)
            jm = re.search(r"<Journal>.*?<Title>(.*?)</Title>", a, re.S)
            abst = " ".join(
                clean(t) for _, t in re.findall(
                    r'<AbstractText(?:\s+Label="([^"]*)")?[^>]*>(.*?)</AbstractText>',
                    a, re.S))
            # Citation fields, captured here because this is the only place
            # the record is fetched. Retyping a DOI by hand is how a wrong one
            # gets published.
            dm = re.search(r'<ArticleId IdType="doi">(.*?)</ArticleId>', a)
            names = re.findall(
                r"<Author[^>]*>.*?<LastName>(.*?)</LastName>.*?<ForeName>(.*?)</ForeName>",
                a, re.S)
            authors = (f"{clean(names[0][1])} {clean(names[0][0])}, et al."
                       if names else "")
            y = re.search(r"<PubDate>.*?<Year>(\d{4})</Year>"
                          r"(?:.*?<Month>(\w+)</Month>)?", a, re.S)
            MN = {"Jan": "January", "Feb": "February", "Mar": "March",
                  "Apr": "April", "May": "May", "Jun": "June", "Jul": "July",
                  "Aug": "August", "Sep": "September", "Oct": "October",
                  "Nov": "November", "Dec": "December"}
            NUM = {str(i): m for i, m in enumerate(
                ["", "January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November",
                 "December"])}
            if y and y.group(2):
                mon = MN.get(y.group(2), NUM.get(y.group(2).lstrip("0"), y.group(2)))
                pubdate = f"{mon} {y.group(1)}"
            else:
                pubdate = y.group(1) if y else ""
            out[pmid] = {
                "title": clean(tm.group(1)) if tm else "",
                "journal": clean(jm.group(1)) if jm else "",
                "types": re.findall(r"<PublicationType[^>]*>(.*?)</PublicationType>", a),
                "abstract": abst,
                "authors": authors,
                "pubdate": pubdate,
                "doi": clean(dm.group(1)) if dm else "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        time.sleep(0.4)
    return out


def interesting(rec):
    """A crude score, used only to order the file a human then reads.

    It rewards the things this feed is actually built on -- a number worth
    quoting, a design worth trusting, and a result that undercuts its own
    headline -- and it is not a substitute for reading the abstract. Nothing
    is excluded by score.
    """
    text = (rec["title"] + " " + rec["abstract"]).lower()
    score = 0
    if re.search(r"\b\d{1,3}(\.\d)?%", text):       score += 2
    if re.search(r"\bn\s*=\s*\d{3,}", text):        score += 2
    if any("Randomized Controlled Trial" in t or "Meta-Analysis" in t
           or "Systematic Review" in t for t in rec["types"]):  score += 3
    for phrase in ("did not", "no significant", "not associated",
                   "no evidence", "failed to", "contrary to",
                   "not reach", "very low certainty", "small sample",
                   "underpowered", "cannot be"):
        if phrase in text: score += 2
    if len(rec["abstract"]) < 400:                  score -= 3
    return score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=12,
                    help="search when fewer than this many days remain")
    ap.add_argument("--since", type=int, default=60,
                    help="only papers published in the last N days")
    ap.add_argument("--per-topic", type=int, default=25)
    ap.add_argument("--force", action="store_true",
                    help="search even when the queue is healthy")
    args = ap.parse_args()

    q = queue_state()
    print("QUEUE")
    print(f"  today            {q['today']}")
    w = q["website"]
    print(f"  website feed     through {w['lastDate']}  "
          f"({w['daysLeft']} days, last index {w['lastIndex']})")
    if "instagram" in q:
        i = q["instagram"]
        print(f"  instagram reels  through {i['lastDate']}  "
              f"({i['daysLeft']} days, last Post{i['lastPost']})")
    shortest = min([w["daysLeft"]] + ([q["instagram"]["daysLeft"]]
                                      if "instagram" in q else []))
    print(f"  shortest         {shortest} days")

    if shortest > args.days and not args.force:
        print(f"\nQueue is healthy (> {args.days} days). Nothing to do.")
        return 0

    print(f"\nSearching PubMed (published in the last {args.since} days)")
    used = used_pmids()
    print(f"  excluding {len(used)} PMIDs already used")
    found, counts = search(args.since, args.per_topic, used)
    if not found:
        print("\nNo new candidates. Widen --since, or add a topic.")
        return 1

    print(f"\n{len(found)} distinct new PMIDs; fetching abstracts")
    recs = details(sorted(found))

    rows, dropped = [], {"off_topic": 0, "not_psych": 0}
    for pmid, rec in recs.items():
        blob = rec["title"] + " " + rec["abstract"]
        if not ON_TOPIC.search(blob):
            dropped["not_psych"] += 1
            continue
        if OFF_TOPIC.search(rec["title"]):
            dropped["off_topic"] += 1
            continue
        rows.append({"pmid": pmid, "topics": found.get(pmid, []),
                     "score": interesting(rec), **rec})
    rows.sort(key=lambda r: -r["score"])
    print(f"  dropped {dropped['not_psych']} with no mental-health content, "
          f"{dropped['off_topic']} plainly about an organ")

    nxt = (q["instagram"]["lastPost"] + 1) if "instagram" in q else w["lastIndex"] + 1
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"Batch Candidates from Post{nxt}.json")
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump({"_readme": ("Generated by Website/scripts/find_studies.py. "
                               "Candidates only -- nothing here has been read "
                               "or chosen. Ordered by a crude score that "
                               "favours a quotable number, a trustworthy "
                               "design and a result weaker than its headline."),
                   "generatedOn": q["today"], "queue": q,
                   "nextPost": nxt, "topicCounts": counts,
                   "candidates": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # The citation half, in the shape add_batch.py reads, written beside the
    # candidates so a batch built from this file cannot cite a paper that was
    # never fetched.
    cits = os.path.join(OUTDIR, "batch-citations.json")
    with io.open(cits, "w", encoding="utf-8") as f:
        json.dump({r["pmid"]: {k: r[k] for k in
                               ("title", "journal", "authors", "pubdate",
                                "doi", "url")}
                   for r in rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")

    missing_doi = [r["pmid"] for r in rows if not r["doi"]]
    if missing_doi:
        print(f"  note: {len(missing_doi)} candidates have no DOI; "
              f"do not pick those")

    print(f"\n{len(rows)} candidates written to")
    print(f"  {os.path.relpath(out, ROOT)}")
    print(f"  {os.path.relpath(cits, ROOT)}")
    print(f"  next post would be Post{nxt}")
    print("\nTop of the list:")
    for r in rows[:8]:
        print(f"  [{r['score']:>2}] {r['pmid']}  {','.join(r['topics'])[:16]:<16} "
              f"{r['title'][:72]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
