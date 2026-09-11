# -*- coding: utf-8 -*-
"""Build a page per research topic from data/professors.json.

An applicant does not search for a professor they have never heard of. They
search for the subject -- "PTSD labs clinical psychology PhD", "who studies
eating disorders" -- and then find the people. The professor list answers the
name query; these pages answer the subject query, which is the larger of the
two and had nothing behind it.

The accuracy rule, which is the whole design:

  A professor appears on a topic page only because a phrase they wrote on
  their own faculty or lab page matched that topic's pattern, and the page
  prints that phrase verbatim beside their name. Nothing here paraphrases
  someone's research into a category, and nothing asserts a topic on their
  behalf. If a match is wrong, the quoted phrase is sitting there to be
  judged, the same way every study summary sits next to its DOI.

  Nor do these pages say anyone is accepting students. That changes weekly and
  is stated in exactly one place, the tracker, which every school heading
  links to.

Grouped by school rather than listed flat, because a school is the unit an
applicant actually decides about: you apply to a program, not to a person.

Called from build.py. Each page is written from scratch every build.
"""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
TOPICS = os.path.join(SITE, "data", "topics.json")
PROFESSORS = os.path.join(SITE, "data", "professors.json")
PROGRAMS = os.path.join(SITE, "data", "programs.json")
OUT_DIR = os.path.join(SITE, "professors")


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


PREFIX = "Clinical psychology professors researching "


def short(h1):
    """The topic on its own, for a link label. Falls back to the full heading
    rather than slicing blind, so renaming a topic cannot truncate it.

    Only the first character is touched: .capitalize() lowercases everything
    after it, which turns PTSD, ADHD and LGBTQ into ptsd, adhd and lgbtq."""
    s = h1[len(PREFIX):] if h1.startswith(PREFIX) else h1
    return s[:1].upper() + s[1:]


def head(title, description, slug, base_url, extra_jsonld=""):
    canonical = f"{base_url}/professors/{slug}"
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
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
<link rel="icon" type="image/png" href="../assets/logo.png">
<link rel="stylesheet" href="../css/style.css">
{extra_jsonld}'''


def person_entry(p, matched):
    """One professor. The matched phrases are their own words, quoted."""
    quotes = "".join(f'<li>{e(m)}</li>' for m in matched)
    return (
        '<li class="topic-person">'
        f'<p class="topic-person-name">{e(p["name"])}</p>'
        f'<ul class="topic-person-interests">{quotes}</ul>'
        '<p class="topic-person-links">'
        f'<a href="{e(p.get("url"))}" target="_blank" rel="noopener">'
        'University page &nearr;</a>'
        f'<a href="../tools/professor-search.html#prof-{e(p["id"])}">'
        'All their interests &rarr;</a>'
        '</p></li>'
    )


def school_block(school, rows, program_ids):
    """rows: [(professor, [matched phrases])] for one school."""
    programs = sorted({p["program"] for p, _ in rows})
    ids = [program_ids.get((school, prog)) for prog in programs]
    ids = [i for i in ids if i]
    status = (f'<a class="topic-school-tracker" '
              f'href="../tools/faculty-accepting-students.html#program-{e(ids[0])}">'
              f'Who is accepting here &rarr;</a>' if len(ids) == 1 else
              f'<a class="topic-school-tracker" '
              f'href="../tools/faculty-accepting-students.html">'
              f'Accepting-students tracker &rarr;</a>')
    people = "".join(person_entry(p, m)
                     for p, m in sorted(rows, key=lambda r: r[0]["name"].lower()))
    return (
        '<section class="topic-school">'
        '<div class="topic-school-head">'
        f'<h3>{e(school)}</h3>'
        f'<p class="topic-school-sub">{e(" &middot; ".join(programs))}</p>'
        f'</div>{status}'
        f'<ul class="topic-people">{people}</ul>'
        '</section>'
    )


def render(*, base_url, header, footer, fmt_date, hub_titles):
    cfg = json.load(open(TOPICS, encoding="utf-8"))
    pdata = json.load(open(PROFESSORS, encoding="utf-8"))
    professors = pdata["professors"]
    updated = pdata.get("updated", "")

    programs = json.load(open(PROGRAMS, encoding="utf-8"))["programs"]
    program_ids = {(p["school"], p["program"]): p["id"] for p in programs}

    os.makedirs(OUT_DIR, exist_ok=True)
    topics, summary = cfg["topics"], []

    for topic in topics:
        rx = re.compile(topic["pattern"], re.I)
        by_school = {}
        people = 0
        for p in professors:
            matched = [i for i in (p.get("interests") or []) if rx.search(i)]
            if not matched:
                continue
            by_school.setdefault(p["school"], []).append((p, matched))
            people += 1

        blocks = "".join(
            school_block(school, rows, program_ids)
            for school, rows in sorted(by_school.items(), key=lambda kv: kv[0].lower()))

        related = "".join(
            f'<li><a href="{e(t["slug"])}.html">{e(short(t["h1"]))}</a></li>'
            for t in topics if t["slug"] != topic["slug"])
        guides = "".join(
            f'<li><a href="../guides/{e(g)}.html">{e(hub_titles[g])}</a></li>'
            for g in topic.get("guides", []) if g in hub_titles)
        guides_html = (f'<section class="topic-guides"><h2>What the research says</h2>'
                       f'<p>Our standing guides on this subject, written from the '
                       f'studies themselves:</p><ul>{guides}</ul></section>'
                       if guides else "")

        description = (f"{people} clinical psychology faculty across "
                       f"{len(by_school)} schools who name this among their research "
                       f"interests, quoted from their own pages. {topic['blurb']}")[:300]

        jsonld = json.dumps({
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "CollectionPage",
                 "name": topic["title"],
                 "description": topic["blurb"],
                 "url": f"{base_url}/professors/{topic['slug']}.html",
                 "isPartOf": {"@id": f"{base_url}/#website"},
                 "publisher": {"@id": f"{base_url}/#organization"},
                 "dateModified": updated},
                {"@type": "BreadcrumbList", "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home",
                     "item": base_url + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Professors by topic",
                     "item": f"{base_url}/professors/"},
                    {"@type": "ListItem", "position": 3, "name": topic["h1"],
                     "item": f"{base_url}/professors/{topic['slug']}.html"}]},
            ]}, indent=2)

        page = f'''<!DOCTYPE html>
<html lang="en">
<head>
{head(topic["title"], description, topic["slug"] + ".html", base_url,
      f'<script type="application/ld+json">{chr(10)}{jsonld}{chr(10)}</script>')}
</head>
<body>

{header("../")}

<main>
  <h1 class="visually-hidden">{e(topic["h1"])}</h1>
  <section class="page">
    <div class="container topic">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../index.html">Home</a> <span>&rsaquo;</span>
        <a href="index.html">Professors by topic</a>
      </nav>

      <div class="section-heading">
        <p class="eyebrow">Professors by topic</p>
        <h2>{e(topic["h1"])}</h2>
        <p>{e(topic["blurb"])}</p>
      </div>

      <p class="topic-stats"><strong>{people}</strong> faculty across
      <strong>{len(by_school)}</strong> schools &middot; interests last read
      {e(updated)}</p>

      <div class="topic-method">
        <p><strong>How to read this page.</strong> Everyone below appears
        because a phrase they wrote on their own faculty or lab page matched
        this topic, and that phrase is printed beside their name. We have not
        paraphrased anyone&rsquo;s research into a category, and where a match
        looks wrong the quoted words are there to judge it by.</p>
        <p>This page does <strong>not</strong> say who is accepting students.
        That changes through the autumn and is stated in one place only &mdash;
        the <a href="../tools/faculty-accepting-students.html">accepting-students
        tracker</a>, linked from every school below. Always confirm with the
        program before you apply.</p>
      </div>

      {blocks}

      {guides_html}

      <section class="topic-related">
        <h2>Other topics</h2>
        <ul class="topic-related-list">{related}</ul>
      </section>

      <div class="page-actions">
        <a class="btn btn-secondary" href="index.html">&larr; All topics</a>
        <a class="btn btn-secondary" href="../tools/professor-search.html">Search all professors</a>
      </div>

    </div>
  </section>
</main>

{footer("../")}
</body>
</html>
'''
        with open(os.path.join(OUT_DIR, topic["slug"] + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)
        summary.append({"slug": topic["slug"], "h1": topic["h1"],
                        "blurb": topic["blurb"], "people": people,
                        "schools": len(by_school)})

    _write_index(summary, base_url, header, footer, updated, len(professors))
    return {"topics": summary, "updated": updated}


def _write_index(summary, base_url, header, footer, updated, total):
    cards = "".join(
        f'<li class="topic-index-card">'
        f'<h3><a href="{e(t["slug"])}.html">{e(short(t["h1"]))}</a></h3>'
        f'<p>{e(t["blurb"])}</p>'
        f'<p class="topic-index-count">{t["people"]} faculty &middot; '
        f'{t["schools"]} schools</p>'
        "</li>"
        for t in sorted(summary, key=lambda x: -x["people"]))

    description = (f"Clinical psychology doctoral faculty grouped by what they "
                   f"research, drawn from {total} faculty whose interests were read "
                   f"from their own pages.")
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Clinical psychology professors by research topic",
        "description": description,
        "url": f"{base_url}/professors/",
        "isPartOf": {"@id": f"{base_url}/#website"},
        "publisher": {"@id": f"{base_url}/#organization"},
        "dateModified": updated,
    }, indent=2)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
{head("Clinical Psychology Professors by Research Topic", description, "",
      base_url, f'<script type="application/ld+json">{chr(10)}{jsonld}{chr(10)}</script>')}
</head>
<body>

{header("../")}

<main>
  <h1 class="visually-hidden">Clinical psychology professors by research topic</h1>
  <section class="page">
    <div class="container topic">
      <div class="section-heading">
        <p class="eyebrow">Professors by topic</p>
        <h2>Find a lab by what it studies</h2>
        <p>
          {total} clinical psychology doctoral faculty, with their research
          interests read from their own faculty and lab pages, grouped by
          subject. Every entry quotes the person&rsquo;s own wording, so you can
          see why they are on a list rather than taking our word for it.
          Interests last read {e(updated)}.
        </p>
      </div>
      <ul class="topic-index">{cards}</ul>
      <div class="page-actions">
        <a class="btn btn-secondary" href="../tools/professor-search.html">Search all professors</a>
        <a class="btn btn-secondary" href="../tools/faculty-accepting-students.html">Who is accepting students</a>
      </div>
    </div>
  </section>
</main>

{footer("../")}
</body>
</html>
'''
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
