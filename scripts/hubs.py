# -*- coding: utf-8 -*-
"""Render the standing guide pages from data/hubs.json.

Individual study posts spike when they are published and then decay. A page
that answers one question and keeps every relevant study under it accumulates
instead, which is the point of these.

The important design rule is in the file it reads: no study finding is retyped
in hubs.json. Each study card is built from that study's own entry in
data/studies.json -- the blurb written from the paper, the journal, and the
DOI -- so a guide page cannot drift away from what the summaries actually say,
and every claim on it is still one click from the original paper. The prose in
hubs.json is framing and navigation, and it has to be supported by the studies
listed beneath it.

Called from build.py, which passes in the pieces of the page shell (header,
footer, date formatting) so the guides match every other page on the site.
Safe to re-run: each guide file is written from scratch every build.
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
HUBS = os.path.join(SITE, "data", "hubs.json")
OUT_DIR = os.path.join(SITE, "guides")


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def study_card(s, source_url):
    """One study, rendered from its own record. Nothing here is hand-written."""
    meta = []
    if s.get("journal"):
        meta.append(e(s["journal"]))
    if s.get("pubdate"):
        meta.append(e(s["pubdate"]))
    src = source_url(s)
    doi = (f'<a class="guide-doi" href="{e(src)}" target="_blank" rel="noopener">'
           f'{e("DOI " + s["doi"]) if s.get("doi") else "Original paper"} &nearr;</a>'
           if src else "")
    return (
        '<li class="guide-study">'
        f'<h3><a href="../studies/{e(s["slug"])}.html">{e(s["title"])}</a></h3>'
        + (f'<p class="guide-study-meta">{" &middot; ".join(meta)}</p>' if meta else "")
        + f'<p class="guide-study-blurb">{e(s["blurb"])}</p>'
        '<p class="guide-study-links">'
        f'<a href="../studies/{e(s["slug"])}.html">Read our summary &rarr;</a>{doi}</p>'
        "</li>"
    )


def faq_jsonld(hub):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in hub["faq"]
        ],
    }


def page_jsonld(hub, base_url, updated, author_jsonld):
    url = f"{base_url}/guides/{hub['slug']}.html"
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": url + "#article",
                "headline": hub["title"],
                "description": hub["description"],
                "url": url,
                "dateModified": updated,
                "author": author_jsonld,
                "publisher": {"@id": base_url + "/#organization"},
                "mainEntityOfPage": url,
                "isAccessibleForFree": True,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": base_url + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Guides",
                     "item": base_url + "/guides/"},
                    {"@type": "ListItem", "position": 3, "name": hub["h1"], "item": url},
                ],
            },
        ],
    }


def render(studies, *, base_url, header, footer, fmt_date, source_url,
           author_jsonld, byline_html, updated):
    """Write every guide page plus the guides index. Returns the hub records so
    build.py can put them in the sitemap and cross-link them from studies."""
    data = json.load(open(HUBS, encoding="utf-8"))
    hubs = data["hubs"]
    by_slug = {s["slug"]: s for s in studies}
    titles = {h["slug"]: h for h in hubs}
    os.makedirs(OUT_DIR, exist_ok=True)

    # Which guides each study belongs to, so build.py can link back from the
    # study page. A study earns its place in a guide by being listed there;
    # this is derived rather than maintained separately.
    membership = {}

    for hub in hubs:
        sections = []
        for sec in hub["sections"]:
            cards = []
            for slug in sec["studies"]:
                s = by_slug.get(slug)
                if s is None:
                    raise SystemExit(
                        f"hubs: {hub['slug']} lists a study that does not exist: {slug}")
                membership.setdefault(slug, []).append(hub["slug"])
                cards.append(study_card(s, source_url))
            sections.append(
                f'<section class="guide-section">'
                f'<h2>{e(sec["heading"])}</h2>'
                f'<p class="guide-section-intro">{e(sec["intro"])}</p>'
                f'<ul class="guide-studies">{"".join(cards)}</ul>'
                "</section>"
            )

        answer = "".join(f"<p>{e(p)}</p>" for p in hub["answer"])
        faq = "".join(
            f'<div class="guide-faq-item"><h3>{e(f["q"])}</h3><p>{e(f["a"])}</p></div>'
            for f in hub["faq"])
        related = "".join(
            f'<li><a href="{e(r)}.html">{e(titles[r]["h1"])}</a></li>'
            for r in hub.get("related", []) if r in titles)
        related_html = (f'<section class="guide-related"><h2>Related guides</h2>'
                        f'<ul>{related}</ul></section>' if related else "")

        page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(hub["title"])}</title>
<meta name="description" content="{e(hub["description"])}">
<link rel="canonical" href="{base_url}/guides/{e(hub["slug"])}.html">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="{e(hub["title"])}">
<meta property="og:description" content="{e(hub["description"])}">
<meta property="og:url" content="{base_url}/guides/{e(hub["slug"])}.html">
<meta property="og:image" content="{base_url}/assets/logo.png">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="../assets/logo.png">
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">
{json.dumps(page_jsonld(hub, base_url, updated, author_jsonld), indent=2)}
</script>
<script type="application/ld+json">
{json.dumps(faq_jsonld(hub), indent=2)}
</script>
</head>
<body>

{header("../")}

<main>
  <article class="page">
    <div class="container guide">

      <nav class="guide-crumbs" aria-label="Breadcrumb">
        <a href="../index.html">Home</a> <span>&rsaquo;</span>
        <a href="index.html">Guides</a>
      </nav>

      <p class="eyebrow">Guide</p>
      <h1>{e(hub["h1"])}</h1>
      {byline_html}
      <p class="guide-updated">Updated {fmt_date(updated)} &middot; kept current as we cover new studies</p>

      <div class="guide-answer">
        <p class="guide-answer-label">The short answer</p>
        {answer}
      </div>

      <p class="guide-scope"><strong>What this page covers.</strong> {e(hub["scope"])}
      Every claim above is drawn from the studies below, and each of those links to
      the original paper.</p>

      {"".join(sections)}

      <section class="guide-faq">
        <h2>Common questions</h2>
        {faq}
      </section>

      {related_html}

      <p class="study-disclaimer">
        This is an educational summary, not medical or psychological advice, and
        it is not a substitute for consultation with a qualified professional.
        Read the full <a href="../legal.html">disclaimer</a>.
      </p>

      <div class="page-actions">
        <a class="btn btn-secondary" href="../research.html">&larr; All research</a>
        <a class="btn btn-secondary" href="index.html">All guides</a>
      </div>

    </div>
  </article>
</main>

{footer("../")}
</body>
</html>
'''
        with open(os.path.join(OUT_DIR, hub["slug"] + ".html"), "w",
                  encoding="utf-8") as f:
            f.write(page)

    _write_index(hubs, base_url, header, footer, fmt_date, updated)
    return {"hubs": hubs, "membership": membership}


def _write_index(hubs, base_url, header, footer, fmt_date, updated):
    cards = "".join(
        f'<li class="guide-index-card">'
        f'<h2><a href="{e(h["slug"])}.html">{e(h["h1"])}</a></h2>'
        f'<p>{e(h["description"])}</p>'
        f'<p class="guide-index-count">'
        f'{sum(len(s["studies"]) for s in h["sections"])} studies covered</p>'
        "</li>"
        for h in hubs)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Guides &mdash; The Clinical Perspective</title>
<meta name="description" content="Standing guides to the questions readers ask most, each answering one question directly and gathering every study we have covered that bears on it.">
<link rel="canonical" href="{base_url}/guides/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="Guides">
<meta property="og:description" content="One question per page, answered from the studies we have summarised.">
<meta property="og:url" content="{base_url}/guides/">
<meta property="og:image" content="{base_url}/assets/logo.png">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="../assets/logo.png">
<link rel="stylesheet" href="../css/style.css">
</head>
<body>

{header("../")}

<main>
  <h1 class="visually-hidden">Guides to clinical psychology and mental health research</h1>
  <section class="page">
    <div class="container guide">
      <div class="section-heading">
        <p class="eyebrow">Guides</p>
        <h2>One question per page</h2>
        <p>
          A study summary answers what one paper found. These pages answer the
          question people actually arrive with, and gather every study we have
          covered that bears on it. They are updated as we publish more, and they
          say plainly where the evidence runs out.
        </p>
      </div>
      <ul class="guide-index">{cards}</ul>
      <p class="guide-updated">Updated {fmt_date(updated)}</p>
      <div class="page-actions">
        <a class="btn btn-secondary" href="../research.html">&larr; All research</a>
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
