# -*- coding: utf-8 -*-
"""Build a page per doctoral program, and per state, from data/programs.json.

The tracker answers one search well -- "clinical psychology programs accepting
students" -- and cannot answer the 257 narrower searches underneath it. Nobody
types the head term when they already know where they are applying. They type
"Penn State clinical psychology accepting students", and a single page holding
all 257 programs can never rank for that. These pages can, because each one is
about exactly one program.

This deliberately reverses the rule written into render_topics.py, that
accepting status is stated in exactly one place. It is now stated in two, and
the reason that is safe is narrow and worth stating: both the tracker and these
pages are generated from data/programs.json in the same build, so they cannot
disagree with each other. What they can do is go stale together if the build is
not run -- so every page here prints the date the program was last checked,
next to the program's own words, and links to the source. A reader is never
asked to take the status on trust.

The programs with no list posted yet get a page too, and that is not padding.
"Not posted yet, last checked 16 September" is the correct answer to
"is X accepting students", it is the answer almost nobody publishes, and a
page that says it honestly is worth more than no page at all. What such a page
must not do is imply a list exists, so the answer block leads with the absence.

State pages exist only where a state has at least MIN_STATE programs. Below
that, a state page is a near-duplicate of the one or two program pages it
links to, and thin near-duplicates are how a site teaches Google to distrust
it. The remaining states are listed on the index with their programs linked
directly, so nothing is unreachable.

Called from build.py. Every page is rewritten from scratch on every build.
"""
import confirmed
import html
import json
import os

import render_tracker

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROGRAMS = os.path.join(SITE, "data", "programs.json")
OUT_DIR = os.path.join(SITE, "programs")
STATE_DIR = os.path.join(OUT_DIR, "state")

# Below three programs, a state page says nothing its program pages do not.
MIN_STATE = 3

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DC": "Washington, D.C.", "DE": "Delaware", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine",
    "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri", "MS": "Mississippi",
    "MT": "Montana", "NC": "North Carolina", "ND": "North Dakota",
    "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "PR": "Puerto Rico", "RI": "Rhode Island", "SC": "South Carolina",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia",
    "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin",
    "WV": "West Virginia", "WY": "Wyoming",
}

STATUS_LABEL = render_tracker.STATUS_LABEL


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def state_slug(code):
    return STATE_NAMES.get(code, code).lower().replace(", ", "-").replace(
        ".", "").replace(" ", "-")


def facts(p):
    """How much this page actually has to say. Two programs sitewide come out
    under three; they are generated but kept out of the index rather than
    submitted as thin pages."""
    n = 2 if p.get("sourceQuote") else 0
    n += len(p.get("accepting") or []) + len(p.get("maybe") or [])
    n += len(p.get("notAccepting") or [])
    n += 1 if p.get("applicationDeadline") else 0
    n += 1 if p.get("applicationFee") is not None else 0
    n += 1 if p.get("greRequired") else 0
    n += len(p.get("otherRequirements") or [])
    return n


def head(title, description, path, base_url, prefix, extra_jsonld="",
         noindex=False):
    canonical = f"{base_url}/{path}"
    robots = '\n<meta name="robots" content="noindex, follow">' if noindex else ""
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">{robots}
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{base_url}/assets/logo.png">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="{prefix}assets/logo.png">
<link rel="stylesheet" href="{prefix}css/style.css">
{extra_jsonld}'''


def answer(p, fmt_date):
    """The direct answer, first thing on the page, in the words the tracker
    uses. Anything other than a posted list leads with the absence, so the
    page cannot be skimmed as though a list existed."""
    cycle = e(p.get("cycle") or "this cycle")
    checked = f" as of {e(fmt_date(p['checked']))}" if p.get("checked") else ""
    n = len(p.get("accepting") or [])
    m = len(p.get("maybe") or [])
    if p["status"] == "posted" and n:
        txt = (f"<strong>Yes.</strong> {n} faculty "
               f"{'is' if n == 1 else 'are'} listed as accepting new doctoral "
               f"students for {cycle}{checked}, taken from the program's own "
               f"page and quoted below.")
        if m:
            txt += (f" A further {m} {'is' if m == 1 else 'are'} undecided and "
                    f"ask to be contacted directly.")
    elif p["status"] == "posted" and m:
        # A list of maybes is not an empty list. Several programs publish
        # only "may be considering applications" and nothing firmer, and
        # reporting that as "no faculty are accepting" tells an applicant to
        # skip a program that is in fact reading applications.
        txt = (f"<strong>Maybe.</strong> The program has published its "
               f"{cycle} list{checked}. Nobody on it is confirmed as "
               f"accepting, but {m} {'is' if m == 1 else 'are'} listed as "
               f"considering applications and ask to be contacted directly.")
    elif p["status"] == "posted":
        txt = (f"The program has published its {cycle} list{checked}, and no "
               f"faculty on it are accepting new students.")
    elif p["status"] == "pending":
        txt = (f"<strong>Not yet announced.</strong> As of{checked.replace(' as of', '')}"
               f" this program had not published which faculty are accepting "
               f"students for {cycle}. We re-check it through the season.")
    elif p["status"] == "cohort":
        # How a program admits is not a fact that has an "as of" -- hanging
        # the check date off the end of it reads as though cohort admission
        # were this season's policy. It gets its own sentence.
        when = (f" Checked {e(fmt_date(p['checked']))}."
                if p.get("checked") else "")
        txt = (f"<strong>There is no list to publish.</strong> This program "
               f"admits to a cohort rather than to an individual advisor, so "
               f"applicants are not matched to a single faculty member at the "
               f"point of application.{when}")
    elif p["status"] == "closed":
        txt = (f"<strong>Not accepting.</strong> This program is not taking "
               f"applications for {cycle}{checked}.")
    else:
        txt = (f"We have not checked this program for {cycle} yet.")
    # When the program has answered us, that goes first and the line derived
    # from their web page becomes supporting detail. The page is the weaker
    # source and usually the older one; leading with it buries the better
    # answer under a heading a reader takes as the verdict.
    lead = confirmed.sentence(p, e, fmt_date)
    if lead:
        body = (lead
                + f'<p class="guide-answer-page">'
                  f'<span class="guide-answer-page-label">What their own page '
                  f'showed</span>{txt}</p>')
    else:
        body = f'<p>{txt}</p>'
    return (f'<div class="guide-answer">'
            f'<p class="guide-answer-label">Accepting students for {cycle}?</p>'
            f'{body}</div>')


def program_jsonld(p, base_url, fmt_date):
    url = f"{base_url}/programs/{p['id']}.html"
    prog = {
        "@type": "EducationalOccupationalProgram",
        "name": f"{p['school']} — {p['program']}",
        "url": url,
        "programType": p.get("degree") or "",
        "educationalCredentialAwarded": p.get("degree") or "",
        "occupationalCategory": "Clinical Psychologist",
        "provider": {"@type": "CollegeOrUniversity", "name": p["school"],
                     "url": p.get("url") or ""},
    }
    if p.get("applicationDeadline"):
        prog["applicationDeadline"] = p["applicationDeadline"]
    q = []
    cycle = p.get("cycle") or "this cycle"
    n = len(p.get("accepting") or [])
    if p["status"] == "posted":
        m = len(p.get("maybe") or [])
        if n:
            a = (f"{n} faculty are listed as accepting new doctoral students "
                 f"for {cycle}.")
        elif m:
            a = (f"No faculty are confirmed as accepting for {cycle}, but {m} "
                 f"are listed as considering applications.")
        else:
            a = (f"The {cycle} list is published and no faculty on it are "
                 f"accepting.")
    elif p["status"] == "pending":
        a = (f"The program has not yet published which faculty are accepting "
             f"students for {cycle}.")
    elif p["status"] == "cohort":
        a = ("This program admits to a cohort rather than to an individual "
             "advisor, so there is no mentor list.")
    elif p["status"] == "closed":
        a = f"This program is not accepting applications for {cycle}."
    else:
        a = "We have not checked this program for this cycle yet."
    if p.get("checked"):
        a += f" Last checked {fmt_date(p['checked'])}."
    q.append({"@type": "Question",
              "name": f"Is {p['school']} {p['program']} accepting students "
                      f"for {cycle}?",
              "acceptedAnswer": {"@type": "Answer", "text": a}})
    if p.get("applicationDeadline"):
        q.append({"@type": "Question",
                  "name": f"What is the application deadline for "
                          f"{p['school']} {p['program']}?",
                  "acceptedAnswer": {
                      "@type": "Answer",
                      "text": f"{p['applicationDeadline']}"
                              + (f" ({p['deadlineCycle']})"
                                 if p.get("deadlineCycle") else "")}})
    graph = [prog, {"@type": "FAQPage", "mainEntity": q},
             {"@type": "BreadcrumbList", "itemListElement": [
                 {"@type": "ListItem", "position": 1, "name": "Home",
                  "item": base_url + "/"},
                 {"@type": "ListItem", "position": 2, "name": "Programs",
                  "item": f"{base_url}/programs/"},
                 {"@type": "ListItem", "position": 3,
                  "name": f"{p['school']} — {p['program']}", "item": url}]}]
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      indent=2)


def program_page(p, siblings, base_url, header, footer, fmt_date, has_state):
    cycle = p.get("cycle") or "this cycle"
    title = (f"{p['school']} {p['program']} — Accepting Students for {cycle}?")
    n = len(p.get("accepting") or [])
    if p["status"] == "posted" and n:
        desc = (f"{n} faculty in {p['school']}'s {p['program']} are accepting "
                f"doctoral students for {cycle}, quoted from the program's own "
                f"page. Deadline, fee and requirements included.")
    else:
        desc = (f"Whether {p['school']}'s {p['program']} is accepting doctoral "
                f"students for {cycle} — {STATUS_LABEL.get(p['status'], '').lower()}"
                f". Deadline, fee and requirements included.")

    quote = (f'<figure class="prog-quote"><blockquote class="fac-quote">'
             f'&ldquo;{e(p["sourceQuote"])}&rdquo;</blockquote>'
             f'<figcaption>The program\'s own wording, quoted from its '
             f'faculty page.</figcaption></figure>'
             if p.get("sourceQuote") else "")

    names = (render_tracker.name_list(p.get("accepting"), "yes",
                                     "Accepting students")
             + render_tracker.name_list(p.get("maybe"), "maybe",
                                        "Undecided — contact directly")
             + render_tracker.name_list(p.get("notAccepting"), "no",
                                        "Not accepting this cycle"))
    names_html = (f'<section class="guide-section"><h2>Faculty</h2>{names}'
                  f'{quote}</section>' if names or quote else "")

    app = render_tracker.app_info(p)
    app_html = ""
    if app.strip() and app != '<div class="fac-appinfo"></div>':
        src = ""
        if p.get("appInfoSourceUrl"):
            when = (f" Checked {e(fmt_date(p['appInfoChecked']))}."
                    if p.get("appInfoChecked") else "")
            src = (f'<p class="prog-src"><a href="{e(p["appInfoSourceUrl"])}" '
                   f'target="_blank" rel="noopener">Where these came from '
                   f'&nearr;</a>{when}</p>')
        app_html = (f'<section class="guide-section"><h2>Applying</h2>'
                    f'{app}{src}</section>')

    sib = "".join(
        f'<li><a href="{e(s["id"])}.html">{e(s["school"])}</a> '
        f'<span>{e(s["program"])}</span></li>' for s in siblings[:12])
    state_name = STATE_NAMES.get(p.get("state"), p.get("state") or "")
    sib_html = ""
    if sib:
        more = (f'<p><a href="state/{e(state_slug(p["state"]))}.html">'
                f'All programs in {e(state_name)} &rarr;</a></p>'
                if has_state else "")
        sib_html = (f'<section class="guide-related"><h2>Other programs in '
                    f'{e(state_name)}</h2><ul class="prog-siblings">{sib}</ul>'
                    f'{more}</section>')

    badge = (f'<span class="fac-badge posted">{n} accepting</span>'
             if p["status"] == "posted" and n else
             f'<span class="fac-badge {e(p["status"])}">'
             f'{e(STATUS_LABEL.get(p["status"], ""))}</span>')
    pcsas = (' &middot; <span class="fac-pcsas" title="Accredited by the '
             'Psychological Clinical Science Accreditation System">PCSAS '
             'accredited</span>' if p.get("pcsas") else "")
    checked = (f'<span class="fac-checked">Checked '
               f'{e(fmt_date(p["checked"]))}</span>' if p.get("checked") else "")
    verified = confirmed.pill(p, e, fmt_date)

    crumb_state = (f'<a href="state/{e(state_slug(p["state"]))}.html">'
                   f'{e(state_name)}</a> <span>&rsaquo;</span>'
                   if has_state else "")

    jsonld = program_jsonld(p, base_url, fmt_date)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
{head(title, desc[:300], f"programs/{p['id']}.html", base_url, "../",
      f'<script type="application/ld+json">{chr(10)}{jsonld}{chr(10)}</script>',
      noindex=facts(p) < 3)}
</head>
<body>

{header("../")}

<main>
  <section class="page">
    <div class="container prog">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../index.html">Home</a> <span>&rsaquo;</span>
        <a href="index.html">Programs</a> <span>&rsaquo;</span>
        {crumb_state}
        <span aria-current="page">{e(p["school"])}</span>
      </nav>

      <div class="prog-head">
        <div>
          <h1>{e(p["school"])}</h1>
          <p class="prog-sub">{e(p["program"])}{pcsas}</p>
        </div>
        <div class="prog-head-right">{verified}{badge}</div>
      </div>

      {answer(p, fmt_date)}
      {names_html}
      {app_html}

      <div class="fac-foot prog-foot">
        <a href="{e(p.get("url"))}" target="_blank" rel="noopener">Check the
          program&rsquo;s own page &rarr;</a>{checked}
      </div>

      <p class="prog-note">Status and faculty names on this page are read from
        the program&rsquo;s own website and re-checked through the admissions
        season. Where the program publishes a sentence announcing who is
        accepting, that sentence is quoted above rather than summarised. The
        date beside each section is when we last read it &mdash; if you are
        deciding where to apply, confirm against the program page before you
        rely on it.</p>

      <p class="prog-tracker"><a href="../tools/faculty-accepting-students.html#program-{e(p["id"])}">
        See this program in the full tracker &rarr;</a></p>

      {sib_html}

    </div>
  </section>
</main>

{footer("../")}
</body>
</html>
'''


def state_page(code, rows, base_url, header, footer, fmt_date, updated):
    name = STATE_NAMES.get(code, code)
    slug = state_slug(code)
    posted = [p for p in rows if p["status"] == "posted" and p.get("accepting")]
    people = sum(len(p.get("accepting") or []) for p in rows)
    title = f"Clinical Psychology Doctoral Programs in {name} — Fall 2027 Admissions"
    desc = (f"All {len(rows)} clinical psychology PhD and PsyD programs in "
            f"{name}, with who is accepting doctoral students for Fall 2027, "
            f"application deadlines and requirements.")

    items = ""
    for p in sorted(rows, key=lambda r: r["school"].lower()):
        n = len(p.get("accepting") or [])
        badge = (f'<span class="fac-badge posted">{n} accepting</span>'
                 if p["status"] == "posted" and n else
                 f'<span class="fac-badge {e(p["status"])}">'
                 f'{e(STATUS_LABEL.get(p["status"], ""))}</span>')
        dl = (f'<span class="prog-row-dl">Deadline {e(p["applicationDeadline"])}</span>'
              if p.get("applicationDeadline") else "")
        items += (f'<li class="prog-row">'
                  f'<a class="prog-row-link" href="../{e(p["id"])}.html">'
                  f'<span class="prog-row-school">{e(p["school"])}</span>'
                  f'<span class="prog-row-prog">{e(p["program"])}</span></a>'
                  f'<span class="prog-row-meta">{badge}{dl}</span></li>')

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage",
             "name": title,
             "description": desc,
             "url": f"{base_url}/programs/state/{slug}.html",
             "isPartOf": {"@id": f"{base_url}/#website"},
             "publisher": {"@id": f"{base_url}/#organization"},
             "dateModified": updated},
            {"@type": "ItemList",
             "numberOfItems": len(rows),
             "itemListElement": [
                 {"@type": "ListItem", "position": i,
                  "name": f"{p['school']} — {p['program']}",
                  "url": f"{base_url}/programs/{p['id']}.html"}
                 for i, p in enumerate(
                     sorted(rows, key=lambda r: r["school"].lower()), 1)]},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home",
                 "item": base_url + "/"},
                {"@type": "ListItem", "position": 2, "name": "Programs",
                 "item": f"{base_url}/programs/"},
                {"@type": "ListItem", "position": 3, "name": name,
                 "item": f"{base_url}/programs/state/{slug}.html"}]},
        ]}, indent=2)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
{head(title, desc[:300], f"programs/state/{slug}.html", base_url, "../../",
      f'<script type="application/ld+json">{chr(10)}{jsonld}{chr(10)}</script>')}
</head>
<body>

{header("../../")}

<main>
  <section class="page">
    <div class="container prog">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../../index.html">Home</a> <span>&rsaquo;</span>
        <a href="../index.html">Programs</a> <span>&rsaquo;</span>
        <span aria-current="page">{e(name)}</span>
      </nav>

      <h1>Clinical psychology doctoral programs in {e(name)}</h1>
      <p class="prog-lede">{len(rows)} PhD and PsyD programs, with whether each
        has said who is accepting doctoral students for Fall 2027.</p>

      <p class="topic-stats"><strong>{len(posted)}</strong> of
        <strong>{len(rows)}</strong> have posted a list &middot;
        <strong>{people}</strong> faculty named as accepting &middot; last
        re-checked {e(fmt_date(updated))}</p>

      <ul class="prog-rows">{items}</ul>

      <p class="prog-tracker"><a href="../../tools/faculty-accepting-students.html">
        Search every program in the tracker &rarr;</a></p>

    </div>
  </section>
</main>

{footer("../../")}
</body>
</html>
'''


def index_page(by_state, state_pages, base_url, header, footer, fmt_date,
               updated, total, posted, people):
    title = ("Clinical Psychology Doctoral Programs — Who Is Accepting "
             "Students for Fall 2027")
    desc = (f"Every one of the {total} clinical psychology PhD and PsyD "
            f"programs we track, by state, with who is accepting doctoral "
            f"students for Fall 2027 and each program's deadline.")

    cards = ""
    for code in sorted(state_pages, key=lambda c: STATE_NAMES.get(c, c)):
        rows = by_state[code]
        n = sum(len(p.get("accepting") or []) for p in rows)
        cards += (f'<li class="topic-index-card">'
                  f'<a href="state/{e(state_slug(code))}.html">'
                  f'<h3>{e(STATE_NAMES.get(code, code))}</h3>'
                  f'<p class="topic-index-count">{len(rows)} programs'
                  + (f' &middot; {n} faculty accepting' if n else '')
                  + '</p></a></li>')

    rest = sorted(set(by_state) - set(state_pages),
                  key=lambda c: STATE_NAMES.get(c, c))
    rest_html = ""
    if rest:
        blocks = ""
        for code in rest:
            links = " ".join(
                f'<a href="{e(p["id"])}.html">{e(p["school"])}</a>'
                for p in sorted(by_state[code], key=lambda r: r["school"].lower()))
            blocks += (f'<li><span class="prog-rest-state">'
                       f'{e(STATE_NAMES.get(code, code))}</span>{links}</li>')
        rest_html = (
            f'<section class="guide-related"><h2>States with one or two '
            f'programs</h2><p>These have no state page of their own &mdash; '
            f'with one or two programs it would only repeat what the program '
            f'pages already say &mdash; so they are listed here.</p>'
            f'<ul class="prog-rest">{blocks}</ul></section>')

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "name": title, "description": desc,
             "url": f"{base_url}/programs/",
             "isPartOf": {"@id": f"{base_url}/#website"},
             "publisher": {"@id": f"{base_url}/#organization"},
             "dateModified": updated},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home",
                 "item": base_url + "/"},
                {"@type": "ListItem", "position": 2, "name": "Programs",
                 "item": f"{base_url}/programs/"}]},
        ]}, indent=2)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
{head(title, desc[:300], "programs/", base_url, "../",
      f'<script type="application/ld+json">{chr(10)}{jsonld}{chr(10)}</script>')}
</head>
<body>

{header("../")}

<main>
  <section class="page">
    <div class="container prog">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../index.html">Home</a> <span>&rsaquo;</span>
        <span aria-current="page">Programs</span>
      </nav>

      <h1>Clinical psychology doctoral programs</h1>
      <p class="prog-lede">One page per program, covering whether it has said
        who is accepting doctoral students for Fall 2027, its deadline, fee and
        requirements &mdash; each read from the program&rsquo;s own website and
        dated.</p>

      <p class="topic-stats"><strong>{total}</strong> programs &middot;
        <strong>{posted}</strong> have posted a list &middot;
        <strong>{people}</strong> faculty named as accepting &middot; last
        re-checked {e(fmt_date(updated))}</p>

      <ul class="topic-index">{cards}</ul>

      {rest_html}

      <p class="prog-tracker"><a href="../tools/faculty-accepting-students.html">
        Search and filter every program in the tracker &rarr;</a></p>

    </div>
  </section>
</main>

{footer("../")}
</body>
</html>
'''


def render(*, base_url, header, footer, fmt_date):
    programs = json.load(open(PROGRAMS, encoding="utf-8"))["programs"]
    updated = max((p.get("checked") or "") for p in programs)

    by_state = {}
    for p in programs:
        by_state.setdefault(p.get("state") or "", []).append(p)
    state_pages = sorted(c for c, rows in by_state.items()
                         if c and len(rows) >= MIN_STATE)

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)

    thin = []
    for p in programs:
        # Programs that have actually posted a list come first. Straight
        # alphabetical order opens California with nine Alliant campuses,
        # which tells a reader nothing about the state and buries the
        # programs that have news. The state page has the full list in order.
        sibs = sorted(
            (s for s in by_state.get(p.get("state") or "", [])
             if s["id"] != p["id"]),
            key=lambda r: (not (r["status"] == "posted" and r.get("accepting")),
                           r["school"].lower()))
        page = program_page(p, sibs, base_url, header, footer, fmt_date,
                            p.get("state") in state_pages)
        with open(os.path.join(OUT_DIR, p["id"] + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        if facts(p) < 3:
            thin.append(p["id"])

    for code in state_pages:
        with open(os.path.join(STATE_DIR, state_slug(code) + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(state_page(code, by_state[code], base_url, header, footer,
                               fmt_date, updated))

    posted = sum(1 for p in programs
                 if p["status"] == "posted" and p.get("accepting"))
    people = sum(len(p.get("accepting") or []) for p in programs)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(by_state, state_pages, base_url, header, footer,
                           fmt_date, updated, len(programs), posted, people))

    return {"programs": [p["id"] for p in programs],
            "states": [state_slug(c) for c in state_pages],
            "state_codes": state_pages,
            "thin": thin, "updated": updated,
            "posted": posted, "people": people}


if __name__ == "__main__":
    print("Run scripts/build.py -- this needs the shared header and footer.")
