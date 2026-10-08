# -*- coding: utf-8 -*-
"""Read a program's APA "Student Admissions, Outcomes, and Other Data" table.

    python scripts/outcomes.py --find            locate the disclosures
    python scripts/outcomes.py --read            read the ones located
    python scripts/outcomes.py --read --only ID  just one program
    python scripts/outcomes.py --report          what we have and what is missing

Every APA-accredited program is required to publish this table, and it answers
the question the rest of the tracker cannot: not "is anyone taking students"
but "what are the odds here, and do people finish". Four numbers matter --
acceptance rate, internship match rate, time to degree, attrition -- and the
match rate is the one that bites. A program where nearly everyone matches is
healthy; one at sixty per cent is one where students finish the coursework and
then cannot get the placement they need to graduate.

Why this is a reader and not a scraper. The content is standardised, because
the APA mandates the rows. The delivery is not: of 180 PhD programs, 78 link
the table from the page we already hold, split 45 web pages to 33 PDFs, and of
the web ones only twenty have real table markup. Naive extraction gets about a
tenth of them. So this does what it can automatically, records exactly what it
read and from where, and leaves the rest to be read by a person -- which is
affordable because these numbers change once a year, not once a sweep.

Nothing is inferred. A row that cannot be found is absent rather than zero, and
a rate is only computed when both of its numbers were actually read.
"""
import argparse
import html as html_mod
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROGRAMS = os.path.join(SITE, "data", "programs.json")
OUTCOMES = os.path.join(SITE, "data", "outcomes.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# How programs label the link. The table has one name in the standard and
# several in practice.
# Programs label this link a dozen ways. The standard calls it "Student
# Admissions, Outcomes, and Other Data"; in the wild it is also "Program
# Outcome Data", "Admissions and Outcomes", "Student Outcome Data", the APA
# form number, or just "Program Data". Matching only the official name found
# 78 of 180; these variants are the difference between a partial table and
# none at all.
LINK = re.compile(
    r"(student admissions[,\s]*outcomes?"
    r"|admissions,?\s*(and\s*)?outcomes?"
    r"|outcomes?,?\s*(and|&)\s*other data"
    r"|student[- ]outcomes?[- ]data"
    r"|program[- ]outcomes?[- ]data"
    r"|outcome[- ]data"
    r"|disclosure of education"
    # The APA form code, which turns up in filenames far more often than in
    # link text -- Biola's disclosure is "Download the PDF Report" pointing at
    # RosemeadPhD_IRC26D_2026.pdf. This alternative was dead: the file held
    # literal backspace bytes where its word boundaries should have been, so
    # it could never match anything, and nobody could see why by reading it.
    r"|(?<![A-Za-z])(?:IR)?C-?2[0-9][a-z]?(?![A-Za-z0-9])"
    r"|admissions?[- ]outcomes?"
    r"|program[- ]data[- ]and[- ]outcomes?"
    r"|student[- ]admissions[- ]data"
    r"|admissions?[- ]statistics)", re.I)

# Where the disclosure hides when the program page does not link it directly.
# Adelphi, Biola and DePaul all keep it one click behind a link labelled some
# variant of "Accreditation", which is why looking at a single page found two
# thirds of these and no more.
HOP = re.compile(
    r"(accreditation|student[- ]outcomes|outcomes\b|student[- ]data"
    r"|program[- ]data|admissions[- ]data|disclosure"
    r"|program[- ]information)", re.I)

# The row labels are the APA template's own, which is what makes this possible
# at all: the wording is the same at every accredited program even though the
# file format is not.
ROWS = {
    "applicants": r"Number of applicants",
    "offers": r"Number offered admission|Number of students offered admission",
    "matriculated": r"Number matriculated|Number of students matriculated",
    "accredited_internships": r"Students who obtained APA/CPA[- ]accredited internships",
    "any_internship": r"Students who obtained any internship",
    "sought_internship": r"Students who sought or applied for internships?"
                         r"(?:[^.]{0,60})?",
    "median_years": r"Median number of years to complete the program",
    "still_enrolled": r"Students still enrolled in program",
}


def fetch(url, timeout=30, tries=3):
    """Fetch, and retry a failure before believing it.

    The first run of the deeper finder reported 147 of 258 pages unfetchable
    and it was almost entirely our own fault: ten workers each making up to
    five requests is a burst of a thousand-odd, and university sites throttle
    that. Retried one at a time, seven of the first eight came back fine.

    So: fewer workers, a pause between attempts, and a retry before a page is
    written off. A genuine block -- American University returns 403 however
    politely you ask -- still fails, which is the distinction that matters.
    """
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            # A refusal is a refusal; retrying it just wastes everyone's time.
            if e.code in (401, 403, 404, 410):
                raise
            last = e
        except Exception as e:  # noqa: BLE001 - timeouts, resets, DNS
            last = e
        if attempt < tries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise last


def visible(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html,
                  flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", txt)


def pdf_text(raw):
    try:
        import pypdf
    except ImportError:
        return ""
    try:
        rd = pypdf.PdfReader(io.BytesIO(raw))
        txt = "\n".join((p.extract_text() or "") for p in rd.pages)
    except Exception:
        return ""
    # The "ti" ligature comes out of many of these as an open bracket, which
    # turns "institution" into "ins(tu(on" and breaks every label match.
    return re.sub(r"\((?=[a-z])", "ti", txt)


def numbers_after(text, label_pattern, count_hint=None):
    """The run of numbers that follows a row label, or None.

    Returns them in document order, which for these tables is oldest year
    first. A label that appears but is followed by no numbers returns an empty
    list, which is different from not finding the label at all -- the caller
    needs to be able to tell "the program does not publish this" from "the
    extraction lost it".
    """
    m = re.search(label_pattern, text, re.I)
    if not m:
        return None
    tail = text[m.end():m.end() + 900]
    # Stop at the next thing that looks like a label rather than a value.
    stop = re.search(r"[A-Za-z]{4,}", tail)
    run = tail[:stop.start()] if stop else tail
    vals = re.findall(r"-?\d+(?:\.\d+)?", run)
    return [float(v) if "." in v else int(v) for v in vals]


def read_disclosure(url):
    """Everything readable from one disclosure, with no inference."""
    out = {"source": url, "rows": {}, "shape": None, "note": None}
    try:
        raw = fetch(url)
    except Exception as e:
        out["note"] = "fetch failed: %s" % str(e)[:60]
        return out

    is_pdf = url.lower().split("?")[0].endswith(".pdf") or raw[:5] == b"%PDF-"
    text = pdf_text(raw) if is_pdf else visible(raw.decode("utf-8", "replace"))
    out["shape"] = "pdf" if is_pdf else "web"
    if len(text.strip()) < 300:
        out["note"] = "no usable text (likely a scan)"
        return out

    for key, pat in ROWS.items():
        vals = numbers_after(text, pat)
        if vals:
            out["rows"][key] = vals
    if not out["rows"]:
        out["note"] = "table labels not found in the text"
    return out


def sane(s):
    """Reject anything that cannot be true, and say why.

    Extraction from these tables produces plausible-looking wrong numbers, not
    obvious garbage: one program came out with a median time to degree of
    76666677766 years because digits from ten columns ran together, another
    with 112.8 applicants because a row of averages was read as a row of
    counts. Both would have published without a second look. A number that is
    merely surprising is kept -- programs really do offer ten places out of
    three hundred -- but a number that is impossible is dropped, because the
    whole value of this table is that somebody can trust it.
    """
    bad = []
    a, o = s.get("applicants"), s.get("offers")
    if a is not None and (a != int(a) or a < 10 or a > 5000):
        bad.append("applicants")
    if o is not None and (o != int(o) or o < 1 or o > 500):
        bad.append("offers")
    if a and o and o > a:
        bad.append("offers")
    r = s.get("acceptanceRate")
    if r is not None and not (0.2 <= r <= 60):
        bad.append("acceptanceRate")
    m = s.get("medianYears")
    if m is not None and not (3 <= m <= 12):
        bad.append("medianYears")
    pct = s.get("internshipMatchedPct")
    if pct is not None and not (0 <= pct <= 100):
        bad.append("internshipMatchedPct")
    for k in set(bad):
        s.pop(k, None)
    if "applicants" in bad or "offers" in bad:
        s.pop("acceptanceRate", None)
        s.pop("applicants", None)
        s.pop("offers", None)
    if bad:
        s["dropped"] = sorted(set(bad))
    return s


def summarise(rows):
    """The four numbers, from the most recent year that actually has them.

    Internship rows alternate count and percentage, so the last pair is the
    latest year. Admissions rows are one value per year. Where a program has
    not filled a year in, the value is simply absent and no rate is computed
    from it -- an acceptance rate invented from a missing denominator would be
    worse than no acceptance rate.
    """
    s = {}
    app = rows.get("applicants") or []
    off = rows.get("offers") or []
    if app and off:
        a, o = app[-1], off[-1]
        if a and a > 0 and o is not None:
            s["applicants"] = a
            s["offers"] = o
            s["acceptanceRate"] = round(100.0 * o / a, 1)

    # Internship rows are (count, percent) per year, and getting this wrong is
    # the most damaging thing this script can do. Three traps, all hit in the
    # first run:
    #
    #   A program with no data for a year writes a dash where the percentage
    #   goes. The dashes vanish from a numbers-only read, the pairs shift, and
    #   Carlos Albizu came out as "0% matched" -- which reads as a program
    #   whose students cannot get placed, when the next row shows most of them
    #   obtaining APPIC internships that simply are not APA-accredited.
    #
    #   A percentage off a denominator of one or two is not a statistic. One
    #   program showed 25% from a single student. Published beside a
    #   university's name that is not a finding, it is an accusation.
    #
    #   "Accredited" is narrower than "placed". A program can be low on the
    #   first and fine on the second, so the second is carried alongside and
    #   the page has to say which it is showing.
    acc = rows.get("accredited_internships") or []
    sought = rows.get("sought_internship") or []
    anyint = rows.get("any_internship") or []
    if len(acc) >= 2 and len(acc) % 2 == 0:
        matched_n, pct = acc[-2], acc[-1]
        denom = sought[-1] if sought else None
        # Trust the pair only if the percentage it implies is the percentage
        # printed. A dash-shifted row fails this and is dropped.
        consistent = True
        if denom:
            implied = round(100.0 * matched_n / denom) if denom else None
            consistent = implied is not None and abs(implied - pct) <= 6
        if consistent and (denom is None or denom >= 4):
            s["internshipMatchedPct"] = pct
            s["internshipMatchedN"] = matched_n
            if denom:
                s["internshipSought"] = denom
        elif denom is not None and denom < 4:
            s["internshipTooFew"] = denom
    if len(anyint) >= 2 and len(anyint) % 2 == 0:
        s["anyInternshipPct"] = anyint[-1]

    med = rows.get("median_years") or []
    if med:
        s["medianYears"] = med[-1]
    return sane(s)


def load(path, default):
    if not os.path.exists(path):
        return default
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def anchors(html, base):
    """Every link on the page, with its label decoded.

    Labels are decoded before matching. Georgia State's link reads "Student
    Admissions, Outcome, &amp; Other Data" in the source, and matching the raw
    HTML meant the ampersand never lined up."""
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        label = html_mod.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        label = re.sub(r"\s+", " ", label).strip()
        out.append((urllib.parse.urljoin(base, m.group(1)), label))
    return out


def find_links(programs, workers=4, deep=True):
    """Look on the program's page, then one hop further.

    One page found 123 of 257. The rest are not missing a disclosure -- APA
    requires it -- they keep it behind an accreditation page, or label it
    something the pattern did not know. Following a single hop is worth it;
    following two would be a crawler.
    """
    def one(p):
        try:
            html = fetch(p["url"], timeout=22).decode("utf-8", "replace")
        except Exception:
            return p["id"], None, "fetch failed"
        links = anchors(html, p["url"])
        for href, label in links:
            if LINK.search(label) or LINK.search(href):
                return p["id"], href, "direct"
        if not deep:
            return p["id"], None, "no link on the page"

        # One hop. Try the most promising candidates only -- an accreditation
        # page is far likelier than a generic "about".
        hops, seen = [], set()
        for href, label in links:
            if (HOP.search(label) or HOP.search(href)) and href not in seen:
                seen.add(href)
                hops.append((href, label))
        for href, label in hops[:4]:
            try:
                sub = fetch(href, timeout=20).decode("utf-8", "replace")
            except Exception:
                continue
            for href2, label2 in anchors(sub, href):
                if LINK.search(label2) or LINK.search(href2):
                    return p["id"], href2, f"via '{label[:30]}'"

        # Walk up the path.
        #
        # programs.json holds the URL the accepting-students tracker needs --
        # whichever page lists admitting faculty. That is the right page for
        # the tracker and the wrong one for this: USC's is /psyc/clinical-
        # faculty/, Duke's is /graduate/apply/admitting-faculty, Emory's is a
        # faculty document. The disclosure sits on the program's own page or
        # its accreditation page, which is usually a level or two above.
        parts = urllib.parse.urlsplit(p["url"])
        segs = [s for s in parts.path.split("/") if s]
        for up in range(1, 4):
            if len(segs) - up < 0:
                break
            parent = urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc,
                 "/" + "/".join(segs[:len(segs) - up]) + "/", "", ""))
            try:
                html2 = fetch(parent, timeout=20).decode("utf-8", "replace")
            except Exception:
                continue
            for href2, label2 in anchors(html2, parent):
                if LINK.search(label2) or LINK.search(href2):
                    return p["id"], href2, f"via parent -{up}"
        return p["id"], None, f"nothing, {len(hops[:4])} hop(s) and 3 parents"

    found, why = {}, {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for pid, url, how in ex.map(one, programs):
            why[pid] = how
            if url:
                found[pid] = url
    return found, why


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--find", action="store_true", help="locate disclosure links")
    ap.add_argument("--read", action="store_true", help="read located disclosures")
    ap.add_argument("--report", action="store_true", help="coverage so far")
    ap.add_argument("--shallow", action="store_true",
                    help="only the program page, no hop")
    ap.add_argument("--only", help="one program id")
    ap.add_argument("--degree", default="PhD", help="PhD, PsyD or all")
    args = ap.parse_args()

    data = load(PROGRAMS, {"programs": []})
    store = load(OUTCOMES, {"note": "APA Student Admissions, Outcomes and Other "
                                    "Data, read per program. See scripts/outcomes.py.",
                            "programs": {}})
    progs = [p for p in data["programs"]
             if args.degree == "all" or p["degree"] == args.degree]
    if args.only:
        progs = [p for p in progs if p["id"] == args.only]

    if args.find:
        before = sum(1 for p in progs
                     if store["programs"].get(p["id"], {}).get("source"))
        links, why = find_links(progs, deep=not args.shallow)
        for pid, url in links.items():
            store["programs"].setdefault(pid, {})["source"] = url
        save(OUTCOMES, store)
        after = sum(1 for p in progs
                    if store["programs"].get(p["id"], {}).get("source"))
        print("located %d of %d programs (%+d on this run)"
              % (after, len(progs), after - before))
        # How each one was found, or why it was not. Worth printing: it is
        # the only way to tell a program that hides its disclosure from one
        # that blocks the fetch, and they need different fixes.
        tally = {}
        for pid, how in why.items():
            key = how if how in ("direct", "fetch failed") else (
                "via a hop" if how.startswith("via") else "not found")
            tally[key] = tally.get(key, 0) + 1
        for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
            print("  %-14s %d" % (k, v))
        return 0

    if args.read:
        todo = [(p["id"], store["programs"][p["id"]]["source"])
                for p in progs
                if p["id"] in store["programs"] and store["programs"][p["id"]].get("source")]
        print("reading %d disclosures" % len(todo))
        ok = 0
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            for pid, res in zip([t[0] for t in todo],
                                ex.map(lambda t: read_disclosure(t[1]), todo)):
                rec = store["programs"].setdefault(pid, {})
                rec["source"] = res["source"]
                rec["shape"] = res["shape"]
                rec["read"] = "2026-09-26"
                if res["rows"]:
                    # Clear last run's summary first. update() adds and
                    # overwrites but never removes, so a value the validator
                    # rejects this time would otherwise survive from the run
                    # before it -- which is how a median of 76666677766 years
                    # stayed in the file after being correctly thrown out.
                    for k in ("applicants", "offers", "acceptanceRate",
                              "internshipMatchedPct", "internshipMatchedN",
                              "internshipSought", "internshipTooFew",
                              "anyInternshipPct", "medianYears", "dropped"):
                        rec.pop(k, None)
                    rec["rows"] = res["rows"]
                    rec.update(summarise(res["rows"]))
                    rec.pop("note", None)
                    ok += 1
                else:
                    rec["note"] = res["note"]
        save(OUTCOMES, store)
        print("  usable rows from %d of %d" % (ok, len(todo)))
        return 0

    # default: report
    have = store.get("programs", {})
    withrate = [k for k, v in have.items() if v.get("acceptanceRate") is not None]
    withmatch = [k for k, v in have.items() if v.get("internshipMatchedPct") is not None]
    print("programs with a disclosure located : %d" % len(have))
    print("  with an acceptance rate          : %d" % len(withrate))
    print("  with an internship match rate    : %d" % len(withmatch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
