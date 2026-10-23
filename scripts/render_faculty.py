# -*- coding: utf-8 -*-
"""One page per faculty member, at /faculty/<id>.html.

Everything on this site could be cited as "their professor search page". None
of it could be cited as "their page about Dr X", because no such page existed
-- 2,681 faculty lived as cards inside one 670KB document, which is the right
shape for a reader filtering and the wrong shape for anything trying to
reference one person.

Not every professor gets one. The bar, set by Max on 23 October 2026, is two
real research interests and a profile link that actually resolves:

  Fewer than two interests and there is nothing on the page but a name and a
  school, which is a thin page in the precise sense Google penalises, and it
  would be generated 2,681 times.

  A dead profile link makes the page worse than nothing: it sends a reader to
  a 404 and tells a crawler this site links to things that are not there.
  scripts/check_profile_urls.py decides that, and only 404 and 410 count --
  403s are universities blocking robots, not missing pages. A professor
  absent from that cache gets a page, because a check that has not run is not
  evidence of a broken link.

The pages that fail the bar are not generated at all, rather than generated
and left out of the sitemap the way programs/ handles its two thin entries.
There is no reason to serve a page nobody should land on.

Called from build.py, which puts the returned ids in the sitemap.
"""
import html
import io
import json
import os

import ldjson
import render_professors

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROFESSORS = os.path.join(SITE, "data", "professors.json")
PROGRAMS = os.path.join(SITE, "data", "programs.json")
STARMAP = os.path.join(SITE, "data", "star-map.json")
URLCACHE = os.path.join(HERE, "profile-urls.json")
OUT_DIR = os.path.join(SITE, "faculty")

MIN_INTERESTS = 2
DEAD = (404, 410)

# What the tracker says, in words a page can put in a sentence.
SAYS = {
    "accepting": "is listed as accepting new doctoral students",
    "maybe": "is listed as possibly considering applications",
    "not-accepting": "is listed as not accepting new doctoral students",
}


def e(s):
    return html.escape(str(s or ""), quote=True)


def eligible(p, dead_urls):
    """The bar, in one place so the count and the pages cannot disagree."""
    if len(p.get("interests") or []) < MIN_INTERESTS:
        return False
    url = p.get("url") or ""
    if not url.startswith(("http://", "https://")):
        return False
    return url not in dead_urls


def person_jsonld(p, prog, status, base_url):
    """The Person, with their interests as knowsAbout.

    sameAs is the university's own page for them, which is the claim that
    matters: this record and that one are the same human being. url is this
    page, so the two are not confused.
    """
    node = {
        "@type": "Person",
        "name": p["name"],
        "url": f"{base_url}/faculty/{p['id']}.html",
        "affiliation": {
            "@type": "CollegeOrUniversity",
            "name": p["school"],
            **({"url": prog["url"]} if prog and prog.get("url") else {}),
        },
        "knowsAbout": list(p.get("interests") or []),
        "jobTitle": "Faculty member",
    }
    if p.get("url"):
        node["sameAs"] = p["url"]
    if status and prog:
        cycle = prog.get("cycle") or "this cycle"
        desc = f"{p['name']} {SAYS[status]} for {cycle} at {p['school']}."
        if prog.get("checked"):
            desc += f" Read from the program's own page on {prog['checked']}."
        node["description"] = desc
    return {"@context": "https://schema.org",
            "@graph": [node, {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home",
                     "item": base_url + "/"},
                    {"@type": "ListItem", "position": 2,
                     "name": "Clinical psychology faculty",
                     "item": f"{base_url}/tools/professor-search.html"},
                    {"@type": "ListItem", "position": 3, "name": p["name"],
                     "item": f"{base_url}/faculty/{p['id']}.html"}]}]}


def status_block(p, prog, status, program_id):
    """What the tracker currently says, or an honest admission that it does
    not say anything yet. Never silence: a page about a professor that says
    nothing about the one question this site exists to answer is a page that
    looks broken."""
    if status and prog:
        cycle = e(prog.get("cycle") or "this cycle")
        label = {"accepting": "Accepting students",
                 "maybe": "Undecided — contact directly",
                 "not-accepting": "Not accepting this cycle"}[status]
        checked = (f' Read from the program&rsquo;s own page on '
                   f'{e(prog["checked"])}.' if prog.get("checked") else "")
        return (f'<p class="fac-page-status is-{e(status)}">'
                f'<strong>{label}</strong> for {cycle}.{checked}</p>')
    reason = ("That program has not published its list for this cycle yet"
              if prog and prog.get("status") == "pending" else
              "That program admits to a cohort rather than to an individual "
              "advisor, so there is no mentor list"
              if prog and prog.get("status") == "cohort" else
              "We have not checked that program for this cycle yet")
    link = (f' <a href="../tools/faculty-accepting-students.html#program-'
            f'{e(program_id)}">See the program entry &rarr;</a>'
            if program_id else "")
    return (f'<p class="fac-page-status is-unknown">{reason}, so there is '
            f'nothing to report for {e(p["name"])}.{link}</p>')


def head(p, description, base_url, jsonld):
    canonical = f"{base_url}/faculty/{p['id']}.html"
    title = f"{p['name']} — {p['school']} — Research Interests"
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{base_url}/assets/logo.png">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="../assets/logo.png">
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">
{jsonld}
</script>'''


def render(*, base_url, header, footer):
    profs = json.load(io.open(PROFESSORS, encoding="utf-8"))["professors"]
    pdata = json.load(io.open(PROGRAMS, encoding="utf-8"))
    programs = pdata["programs"]
    star_map = json.load(io.open(STARMAP, encoding="utf-8"))["map"]

    dead_urls = set()
    checked_on = ""
    if os.path.exists(URLCACHE):
        cache = json.load(io.open(URLCACHE, encoding="utf-8"))
        checked_on = cache.get("checked", "")
        dead_urls = {u for u, s in cache.get("urls", {}).items() if s in DEAD}

    status_of = render_professors.status_index(programs, star_map)
    prog_by_key = {(x["school"], x["program"]): x for x in programs}

    os.makedirs(OUT_DIR, exist_ok=True)
    written, skipped = [], {"interests": 0, "dead_link": 0}

    for p in profs:
        if len(p.get("interests") or []) < MIN_INTERESTS:
            skipped["interests"] += 1
            continue
        if not eligible(p, dead_urls):
            skipped["dead_link"] += 1
            continue

        prog = prog_by_key.get((p["school"], p["program"]))
        program_id = prog["id"] if prog else ""
        status = status_of.get(p["id"])
        interests = list(p.get("interests") or [])

        description = (f"{p['name']} researches "
                       f"{'; '.join(interests[:3])} at {p['school']}. "
                       f"Research interests quoted from their own "
                       f"university page.")[:300]

        items = "".join(f"<li>{e(i)}</li>" for i in interests)
        # No arrow here: it is followed by the state, and "PhD → · NY"
        # reads as though the arrow points at New York.
        prog_link = (f'<a href="../programs/{e(program_id)}.html">'
                     f'{e(p["school"])} &mdash; {e(p["program"])}</a>'
                     if program_id else e(p["school"]))

        page = f'''<!DOCTYPE html>
<html lang="en">
<head>
{head(p, description, base_url,
      ldjson.dumps(person_jsonld(p, prog, status, base_url)))}
</head>
<body>

{header("../")}

<main>
  <section class="page">
    <div class="container fac-page">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../index.html">Home</a> <span>&rsaquo;</span>
        <a href="../tools/professor-search.html">Faculty</a>
      </nav>

      <div class="section-heading">
        <p class="eyebrow">Clinical psychology faculty</p>
        <h1>{e(p["name"])}</h1>
        <p>{prog_link}{f' &middot; {e(p["state"])}' if p.get("state") else ''}</p>
      </div>

      {status_block(p, prog, status, program_id)}

      <h2>Research interests</h2>
      <p class="fac-page-note">Quoted or closely paraphrased from
      {e(p["name"])}&rsquo;s own university page{f', read {e(p["checked"])}' if p.get("checked") else ''}.
      Never inferred from a publication list and never taken from search
      results.</p>
      <ul class="fac-page-interests">{items}</ul>

      <h2>Check it yourself</h2>
      <p class="fac-page-note">This page is a record of what
      {e(p["school"])} published. Their page is the authority, and it is
      the one to read before you write to anybody.</p>
      <p class="fac-page-links">
        <a href="{e(p.get("url"))}" target="_blank" rel="noopener">Their university page &nearr;</a>
        {f'<a href="../tools/faculty-accepting-students.html#program-{e(program_id)}">Accepting-students entry &rarr;</a>' if program_id else ''}
        <a href="../tools/professor-search.html#prof-{e(p["id"])}">Find similar faculty &rarr;</a>
      </p>

    </div>
  </section>
</main>

{footer("../")}
</body>
</html>
'''
        with io.open(os.path.join(OUT_DIR, p["id"] + ".html"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(page)
        written.append(p["id"])

    # Pages for professors who have since dropped below the bar, or left the
    # data, would otherwise sit there for ever being served and sitemapped.
    keep = {i + ".html" for i in written}
    removed = 0
    for fn in os.listdir(OUT_DIR):
        if fn.endswith(".html") and fn not in keep:
            os.remove(os.path.join(OUT_DIR, fn))
            removed += 1

    return {"written": written, "skipped": skipped, "removed": removed,
            "urls_checked": checked_on, "dead": len(dead_urls)}
