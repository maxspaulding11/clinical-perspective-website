"""Rebuild the research archive, the study pages, data/posts.json and
sitemap.xml for The Clinical Perspective.

Add or edit an entry in scripts/studies-source.json, then run:

    python scripts/build.py

Everything under studies/ plus research.html, data/posts.json, data/studies.json
and sitemap.xml is regenerated from that one file, so never hand-edit those.
"""
import json
import os
import re
import html
from datetime import date

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = 'https://theclinicalperspective.org'
IG_PROFILE = 'https://www.instagram.com/the_clinical_perspective/'

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'studies-source.json')
with open(SOURCE, encoding='utf-8') as f:
    raw = json.load(f)
meta = {str(s['index']): s for s in raw}

STOP = {'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or', 'is', 'are'}


def slugify(text):
    text = text.lower()
    text = text.replace('’', '').replace("'", '')
    text = re.sub(r'[^a-z0-9]+', '-', text)
    words = [w for w in text.split('-') if w]
    trimmed = []
    for w in words:
        if len(trimmed) >= 8:
            break
        if w in STOP and not trimmed:
            continue
        trimmed.append(w)
    return '-'.join(trimmed) or 'study'


def fmt_date(iso):
    y, m, d = (int(x) for x in iso.split('-'))
    return date(y, m, d).strftime('%B %-d, %Y') if os.name != 'nt' else date(y, m, d).strftime('%B %d, %Y').replace(' 0', ' ')


def source_link(s):
    """Best canonical link to the original paper."""
    if s.get('doi'):
        return f"https://doi.org/{s['doi']}"
    if s.get('pmid'):
        return f"https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/"
    return s.get('url')


# Entries scaffolded by scripts/draft.py carry "draft": true until the writing
# is done. They are skipped whatever date they hold, so a half-written entry
# cannot go live just because the calendar caught up with it.
drafts = [s for s in raw if s.get('draft')]
raw = [s for s in raw if not s.get('draft')]

# And a belt to that brace: a placeholder must never reach a published page.
# The draft flag is a line someone deletes by hand, and the whole point of the
# marker is that it is the text a reader would have seen.
TODO_MARK = 'TODO'
WRITTEN = ('title', 'tag', 'blurb', 'summary')
unfinished = [(s['index'], f) for s in raw for f in WRITTEN
              if TODO_MARK in str(s.get(f, ''))]
if unfinished:
    print('Build stopped: an entry is published but still has placeholder text.')
    for idx, field in unfinished:
        print(f'  ! entry {idx}: {field} still says {TODO_MARK}')
    print('Finish it, or put back its "draft": true line.')
    raise SystemExit(1)

studies = []
seen = set()
for s in raw:
    m = meta[str(s['index'])]
    # An explicit slug pins the URL so a title can be rewritten without
    # breaking a page that is already published and indexed.
    slug = m.get('slug') or slugify(m['title'])
    while slug in seen:
        slug += '-2'
    seen.add(slug)
    studies.append({
        'slug': slug,
        'index': s['index'],
        'title': m['title'],
        'tag': m['tag'],
        'blurb': m['blurb'],
        'date': s['date'],
        'summary': s['summary'],
        'journal': s['journal'],
        'authors': s['authors'],
        'pubdate': s['pubdate'],
        'pmid': s['pmid'],
        'doi': s['doi'],
        'sourceUrl': source_link(s),
        'instagram': s.get('instagram') or '',
    })

studies.sort(key=lambda x: x['date'])

# Entries dated in the future are scheduled, not published: they're posted to
# Instagram on that date. Publishing them early would put unposted work on the
# site and in Google's index, so they're held back until their date arrives.
# Re-run this build (which you do each time you post) to release them.
TODAY = date.today().isoformat()
scheduled = [s for s in studies if s['date'] > TODAY]
studies = [s for s in studies if s['date'] <= TODAY]

if not studies:
    raise SystemExit(
        'Nothing to publish: every entry in studies-source.json is dated in the '
        f'future (today is {TODAY}). Check the dates before rebuilding.')

# ---------------------------------------------------------------- shared HTML

HEAD_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400'
    '&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">'
)


def header(prefix=''):
    return f'''<header class="site-header">
  <div class="container header-inner">
    <a href="{prefix}index.html" class="brand">
      <img class="brand-logo" src="{prefix}assets/logo.png" alt="The Clinical Perspective logo">
      <span class="brand-name">The Clinical<br>Perspective</span>
    </a>
    <nav class="main-nav" id="main-nav">
      <a href="{prefix}research.html">Research</a>
      <a href="{prefix}guides/index.html">Guides</a>
      <a href="{prefix}about.html">About</a>
      <a href="{prefix}queue.html">Reader Queue</a>
      <a href="{prefix}tools/index.html">Tools</a>
      <a href="{prefix}index.html#submit">Submit Research</a>
      <a href="https://spare.theclinicalperspective.org" target="_blank" rel="noopener" class="nav-spare-change">🪙 Spare Change</a>
      <span class="nav-account" id="nav-account"></span>
    </nav>
    <button class="nav-toggle" id="nav-toggle" aria-label="Toggle navigation" aria-expanded="false">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>'''


def footer(prefix=''):
    return f'''<footer class="site-footer">
  <div class="container footer-inner">
    <div class="footer-brand">
      <img class="brand-logo brand-logo-footer" src="{prefix}assets/logo.png" alt="The Clinical Perspective logo">
      <span>The Clinical Perspective</span>
    </div>
    <div class="footer-links">
      <a href="{IG_PROFILE}" target="_blank" rel="noopener">Instagram</a>
      <a href="{prefix}research.html">Research</a>
      <a href="{prefix}guides/index.html">Guides</a>
      <a href="{prefix}about.html">About</a>
      <a href="{prefix}tools/index.html">Tools</a>
      <a href="{prefix}index.html#submit">Submit Research</a>
      <a href="{prefix}legal.html">Disclaimer &amp; Privacy</a>
    </div>
    <p class="footer-note">&copy; <span id="year"></span> The Clinical Perspective. All summaries link back to original sources.</p>
  </div>
</footer>

<script>
  document.getElementById("year").textContent = new Date().getFullYear();
  const navToggle = document.getElementById("nav-toggle");
  const mainNav = document.getElementById("main-nav");
  navToggle.addEventListener("click", () => {{
    const isOpen = mainNav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  }});
</script>
<script src="{prefix}js/spare-change-config.js"></script>
<script src="{prefix}js/auth-status.js"></script>
<script src="{prefix}js/analytics-config.js"></script>
<script src="{prefix}js/analytics.js"></script>'''


def e(s):
    return html.escape(s or '', quote=True)


# ---------------------------------------------------------------- author
# Health content is held to a higher trust standard, and an anonymous
# summary is the weakest possible signal. Credentials are stated exactly:
# a research coordinator who runs trials and has been through peer review,
# and explicitly not a clinician.
AUTHOR_NAME = 'Maxamus Spaulding'
AUTHOR_SUFFIX = 'BA'
AUTHOR_ROLE = 'Clinical Research Coordinator'
AUTHOR_ORG = 'Dartmouth Hitchcock Medical Center'
AUTHOR_URL = f'{BASE_URL}/about.html#who-writes-this'

AUTHOR_JSONLD = {
    "@type": "Person",
    "name": AUTHOR_NAME,
    "jobTitle": AUTHOR_ROLE,
    "affiliation": {"@type": "Organization", "name": AUTHOR_ORG},
    "url": AUTHOR_URL,
}

BYLINE_HTML = (
    f'<p class="study-byline">By <a href="../about.html#who-writes-this">'
    f'{AUTHOR_NAME}, {AUTHOR_SUFFIX}</a></p>'
)

AUTHOR_BOX_HTML = f'''<aside class="study-author">
        <p><strong>{AUTHOR_NAME}, {AUTHOR_SUFFIX}</strong> is a {AUTHOR_ROLE.lower()} in
        Anesthesiology and Psychiatry at {AUTHOR_ORG}, where he coordinates
        NIH-, NIMH- and PCORI-funded clinical trials and has co-authored
        peer-reviewed research. He is <strong>not a licensed clinician</strong>.
        Every summary here is read from the original paper and links back to it.
        <a href="../about.html#who-writes-this">How these summaries are written &rarr;</a></p>
      </aside>'''

# --------------------------------------------------- tracker cross-link
# The accepting-students tracker is the page most likely to be searched for
# by name, and until now the only route to it was the nav bar. Every study
# carries a link to it in body text instead, with the counts read from
# programs.json so the anchor text describes what is actually on the page.
_tracker = json.load(open(os.path.join(SITE, 'data', 'programs.json'), encoding='utf-8'))
_posted = [p for p in _tracker['programs'] if p['status'] == 'posted']
TRACKER_CYCLE = _tracker.get('cycle', 'the coming cycle')
TRACKER_FACULTY = sum(len(p.get('accepting') or []) for p in _posted)
TRACKER_PROGRAMS = len(_tracker['programs'])
TRACKER_HTML = f'''<aside class="study-tracker">
        <p><strong>Applying to clinical psychology doctoral programs?</strong>
        We keep a free tracker of which faculty are accepting students for
        {TRACKER_CYCLE} &mdash; {TRACKER_FACULTY} confirmed across
        {len(_posted)} programs, out of {TRACKER_PROGRAMS} checked. Every name
        was read from the program&rsquo;s own page and is dated.
        <a href="../tools/faculty-accepting-students.html">Open the accepting-students
        tracker &rarr;</a></p>
      </aside>'''


# ---------------------------------------------------------------- study pages

STUDY_DIR = os.path.join(SITE, 'studies')
os.makedirs(STUDY_DIR, exist_ok=True)

# Remove pages for studies that are no longer published — a renamed title, a
# deleted entry, or one that's been pushed back to a future date.
keep = {f"{s['slug']}.html" for s in studies}
removed = []
for existing in os.listdir(STUDY_DIR):
    if existing.endswith('.html') and existing not in keep:
        os.remove(os.path.join(STUDY_DIR, existing))
        removed.append(existing)

# ------------------------------------------------------------------- guides
# The standing guide pages are rendered before the study pages so each study
# knows which guides it appears in and can link back to them.
import hubs

_h = hubs.render(
    studies, base_url=BASE_URL, header=header, footer=footer,
    fmt_date=fmt_date, source_url=source_link, author_jsonld=AUTHOR_JSONLD,
    byline_html=BYLINE_HTML, updated=TODAY)
HUB_TITLE = {h['slug']: h['h1'] for h in _h['hubs']}


def guide_links(slug):
    """A study that a guide draws on links back to it. This is the internal
    link that makes a guide accumulate rather than sit orphaned off the nav."""
    in_guides = _h['membership'].get(slug) or []
    if not in_guides:
        return ''
    links = ' '.join(
        f'<a href="../guides/{g}.html">{e(HUB_TITLE[g])}</a>' for g in in_guides)
    label = 'guide' if len(in_guides) == 1 else 'guides'
    return (f'<p class="study-guides">This study is part of our {label}: '
            f'{links}</p>')


for i, s in enumerate(studies):
    prev_s = studies[i - 1] if i > 0 else None
    next_s = studies[i + 1] if i < len(studies) - 1 else None
    url = f"{BASE_URL}/studies/{s['slug']}.html"

    cite_bits = []
    if s['authors']:
        cite_bits.append(e(s['authors']))
    if s['journal']:
        cite_bits.append(f"<em>{e(s['journal'])}</em>")
    if s['pubdate']:
        cite_bits.append(e(s['pubdate']))
    citation = ', '.join(cite_bits)

    ids = []
    if s['doi']:
        ids.append(f'<a href="https://doi.org/{e(s["doi"])}" target="_blank" rel="noopener">DOI: {e(s["doi"])}</a>')
    if s['pmid']:
        ids.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{e(s["pmid"])}/" target="_blank" rel="noopener">PMID: {e(s["pmid"])}</a>')
    ids_html = ' &middot; '.join(ids)

    read_btn = ''
    if s['sourceUrl']:
        read_btn = f'<a class="btn btn-primary" href="{e(s["sourceUrl"])}" target="_blank" rel="noopener">Read the original study &rarr;</a>'

    jsonld = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": s['title'],
        "description": s['blurb'],
        "datePublished": s['date'],
        "url": url,
        "author": AUTHOR_JSONLD,
        "publisher": {
            "@type": "Organization",
            "name": "The Clinical Perspective",
            "url": BASE_URL,
        },
        "about": s['tag'],
    }
    if s['sourceUrl']:
        jsonld['citation'] = s['sourceUrl']

    prev_next = []
    if prev_s:
        prev_next.append(f'<a class="study-nav-link" href="{prev_s["slug"]}.html">&larr; {e(prev_s["title"])}</a>')
    else:
        prev_next.append('<span></span>')
    if next_s:
        prev_next.append(f'<a class="study-nav-link study-nav-next" href="{next_s["slug"]}.html">{e(next_s["title"])} &rarr;</a>')
    else:
        prev_next.append('<span></span>')

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(s['title'])} — The Clinical Perspective</title>
<meta name="description" content="{e(s['blurb'])}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="{e(s['title'])}">
<meta property="og:description" content="{e(s['blurb'])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE_URL}/assets/logo.png">
<meta name="twitter:card" content="summary">
{HEAD_FONTS}
<link rel="icon" type="image/png" href="../assets/logo.png">
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">
{json.dumps(jsonld, indent=2, ensure_ascii=False)}
</script>
</head>
<body>

{header('../')}

<main>
  <article class="page study">
    <div class="container page-inner">

      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="../research.html">Research</a> <span aria-hidden="true">/</span> <span>{e(s['tag'])}</span>
      </nav>

      <div class="section-heading study-heading">
        <p class="eyebrow">{e(s['tag'])}</p>
        <h1>{e(s['title'])}</h1>
        <p class="study-date">Covered {fmt_date(s['date'])}</p>
        {BYLINE_HTML}
      </div>

      <div class="prose">
        <p class="study-lede">{e(s['blurb'])}</p>
        <p>{e(s['summary'])}</p>
      </div>

      <aside class="study-source">
        <p class="queue-eyebrow">The study</p>
        <p class="study-citation">{citation}</p>
        {f'<p class="study-ids">{ids_html}</p>' if ids_html else ''}
        <div class="page-actions">
          {read_btn}
          <a class="btn btn-secondary" href="{IG_PROFILE}" target="_blank" rel="noopener">See it on Instagram</a>
        </div>
      </aside>

      {AUTHOR_BOX_HTML}

      <p class="study-disclaimer">
        This is an educational summary, not medical or psychological advice, and
        it is not a substitute for consultation with a qualified professional.
        Read the full <a href="../legal.html">disclaimer</a>.
      </p>

      {guide_links(s['slug'])}

      {TRACKER_HTML}

      <nav class="study-nav" aria-label="More studies">
        {prev_next[0]}
        {prev_next[1]}
      </nav>

      <div class="page-actions">
        <a class="btn btn-secondary" href="../research.html">&larr; All research</a>
      </div>

    </div>
  </article>
</main>

{footer('../')}
</body>
</html>
'''
    with open(os.path.join(SITE, 'studies', f"{s['slug']}.html"), 'w', encoding='utf-8') as f:
        f.write(page)

# ---------------------------------------------------------------- archive page

by_tag = {}
for s in studies:
    by_tag.setdefault(s['tag'], []).append(s)

newest_first = sorted(studies, key=lambda x: x['date'], reverse=True)

tag_buttons = ['<button class="tag-filter is-active" data-tag="all" type="button">All</button>']
for tag in sorted(by_tag):
    tag_buttons.append(f'<button class="tag-filter" data-tag="{e(tag)}" type="button">{e(tag)} <span>{len(by_tag[tag])}</span></button>')

rows = []
for s in newest_first:
    rows.append(f'''        <li class="study-row" data-tag="{e(s['tag'])}">
          <a class="study-row-link" href="studies/{s['slug']}.html">
            <span class="post-tag">{e(s['tag'])}</span>
            <h3>{e(s['title'])}</h3>
            <p>{e(s['blurb'])}</p>
            <span class="study-row-meta">{fmt_date(s['date'])}{f" &middot; {e(s['journal'])}" if s['journal'] else ''}</span>
          </a>
        </li>''')

# A reader on the archive is browsing rather than searching, which is exactly
# who a guide is for. Linking them from the body of the page, not only the nav,
# is what lets the guides accumulate.
ARCHIVE_GUIDES = (
    '<div class="archive-guides">'
    '<p class="archive-guides-label">Start with a question</p>'
    '<ul>'
    + ''.join(f'<li><a href="guides/{h["slug"]}.html">{e(h["h1"])}</a></li>'
              for h in _h['hubs'])
    + '</ul>'
    '<p class="archive-guides-foot">'
    '<a href="guides/index.html">All guides &rarr;</a></p>'
    '</div>')

# The archive lists every summary in the served HTML already. This tells a
# crawler what the list is, and in what order, rather than leaving it to infer.
ARCHIVE_JSONLD = json.dumps({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Research Archive",
    "description": f"Every study covered by The Clinical Perspective: "
                   f"{len(studies)} plain-English summaries, each linked to its "
                   f"original source.",
    "url": f"{BASE_URL}/research.html",
    "isPartOf": {"@id": f"{BASE_URL}/#website"},
    "publisher": {"@id": f"{BASE_URL}/#organization"},
    "mainEntity": {
        "@type": "ItemList",
        "numberOfItems": len(studies),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": s["title"],
             "url": f"{BASE_URL}/studies/{s['slug']}.html"}
            for i, s in enumerate(newest_first)
        ],
    },
}, indent=2)

archive = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Research Archive — The Clinical Perspective</title>
<meta name="description" content="Every study covered by The Clinical Perspective — {len(studies)} plain-English summaries of clinical psychology and mental health research, each linked to its original source.">
<link rel="canonical" href="{BASE_URL}/research.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Clinical Perspective">
<meta property="og:title" content="Research Archive — The Clinical Perspective">
<meta property="og:description" content="Every study covered — {len(studies)} plain-English summaries of clinical psychology and mental health research.">
<meta property="og:url" content="{BASE_URL}/research.html">
<meta property="og:image" content="{BASE_URL}/assets/logo.png">
<meta name="twitter:card" content="summary">
{HEAD_FONTS}
<link rel="icon" type="image/png" href="assets/logo.png">
<link rel="stylesheet" href="css/style.css">
<script type="application/ld+json">
{ARCHIVE_JSONLD}
</script>
</head>
<body>

{header()}

<main>
  <section class="page">
    <div class="container">

      <div class="section-heading">
        <p class="eyebrow">Archive</p>
        <h1>All Research</h1>
        <p>
          Every study covered so far — {len(studies)} summaries, newest first.
          Each one links back to the original paper so you can verify it yourself.
        </p>
      </div>

      {ARCHIVE_GUIDES}

      <div class="tag-filters">
        {chr(10).join('        ' + b for b in tag_buttons)}
      </div>

      <ol class="study-list">
{chr(10).join(rows)}
      </ol>

    </div>
  </section>
</main>

{footer()}

<script>
  const filters = document.querySelectorAll(".tag-filter");
  const rows = document.querySelectorAll(".study-row");
  filters.forEach((btn) => {{
    btn.addEventListener("click", () => {{
      const tag = btn.dataset.tag;
      filters.forEach((b) => b.classList.toggle("is-active", b === btn));
      rows.forEach((row) => {{
        row.hidden = tag !== "all" && row.dataset.tag !== tag;
      }});
    }});
  }});
</script>
</body>
</html>
'''
with open(os.path.join(SITE, 'research.html'), 'w', encoding='utf-8') as f:
    f.write(archive)

# ---------------------------------------------------------------- data files

posts = [{
    'slug': s['slug'],
    'url': f"studies/{s['slug']}.html",
    'instagram': s['instagram'],
    'tag': s['tag'],
    'title': s['title'],
    'date': s['date'],
    'blurb': s['blurb'],
} for s in studies]

with open(os.path.join(SITE, 'data', 'posts.json'), 'w', encoding='utf-8') as f:
    json.dump(posts, f, indent=2, ensure_ascii=False)
    f.write('\n')

with open(os.path.join(SITE, 'data', 'studies.json'), 'w', encoding='utf-8') as f:
    json.dump(studies, f, indent=2, ensure_ascii=False)
    f.write('\n')

# ---------------------------------------------------------------- sitemap

urls = [
    (f'{BASE_URL}/', '1.0'),
    (f'{BASE_URL}/research.html', '0.9'),
    (f'{BASE_URL}/about.html', '0.6'),
    (f'{BASE_URL}/queue.html', '0.6'),
    (f'{BASE_URL}/tools/', '0.7'),
    (f'{BASE_URL}/tools/citations.html', '0.7'),
    (f'{BASE_URL}/tools/applying-to-clinical-psychology-phd-programs.html', '0.8'),
    (f'{BASE_URL}/tools/faculty-accepting-students.html', '0.8'),
    (f'{BASE_URL}/tools/professor-search.html', '0.8'),
    (f'{BASE_URL}/tools/measures.html', '0.8'),
    (f'{BASE_URL}/legal.html', '0.3'),
    (f'{BASE_URL}/guides/', '0.8'),
]
for s in newest_first:
    urls.append((f"{BASE_URL}/studies/{s['slug']}.html", '0.8'))
for h in _h['hubs']:
    urls.append((f"{BASE_URL}/guides/{h['slug']}.html", '0.9'))

# <lastmod> is the part of a sitemap Google actually acts on: it decides what
# is worth re-crawling. Dates come from git, not file mtimes -- this script
# rewrites every page on every run, so mtimes would claim all 77 changed today,
# every day, which teaches a crawler to ignore the field.
import lastmod

_lm = lastmod.Lookup(BASE_URL)

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, pri in urls:
    lines.append('  <url>')
    lines.append(f'    <loc>{loc}</loc>')
    lines.append(f'    <lastmod>{_lm.for_url(loc)}</lastmod>')
    lines.append(f'    <priority>{pri}</priority>')
    lines.append('  </url>')
lines.append('</urlset>')
with open(os.path.join(SITE, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

# ------------------------------------------------------------- homepage cards
# The homepage listed its latest studies only after JavaScript fetched
# posts.json, so the served HTML said "Loading latest posts...". The same
# cards are written in here; main.js clears the grid and rebuilds it with
# the Instagram embeds attached, so nothing changes for a reader.
HOME_START = '<!-- home:posts start (generated by scripts/build.py) -->'
HOME_END = '<!-- home:posts end -->'
HOME_LIMIT = 9

home_cards = []
for post in newest_first[:HOME_LIMIT]:
    tag = f'<span class="post-tag">{e(post["tag"])}</span>' if post['tag'] else ''
    date_html = f'<span class="post-date">{fmt_date(post["date"])}</span>' if post['date'] else ''
    blurb = f'<p class="post-blurb">{e(post["blurb"])}</p>' if post['blurb'] else ''
    home_cards.append(
        f'<article class="post-card reveal visible">'
        f'<a class="post-card-link" href="studies/{post["slug"]}.html">'
        f'<div class="post-card-meta">{tag}<h3>{e(post["title"])}</h3>{date_html}</div>'
        f'{blurb}</a></article>'
    )
home_html = '\n' + '\n'.join(home_cards) + '\n'

index_path = os.path.join(SITE, 'index.html')
index_html = open(index_path, encoding='utf-8').read()
if HOME_START in index_html and HOME_END in index_html:
    pre = index_html.split(HOME_START)[0]
    post_ = index_html.split(HOME_END, 1)[1]
    index_html = pre + HOME_START + home_html + HOME_END + post_
else:
    placeholder = '<p class="posts-loading">Loading latest posts&hellip;</p>'
    if placeholder not in index_html:
        placeholder = '<p class="posts-loading">Loading latest posts…</p>'
    if placeholder not in index_html:
        raise SystemExit('build: could not find the homepage posts placeholder')
    index_html = index_html.replace(placeholder, HOME_START + home_html + HOME_END, 1)
open(index_path, 'w', encoding='utf-8').write(index_html)

# ------------------------------------------------- accepting-students tracker
# The tracker's programs and faculty names are written into its HTML here.
# Without this the page ships as an empty shell and none of the names are
# visible to search engines.
import render_tracker

_t = render_tracker.render()

print(f'Published {len(studies)} studies (through {studies[-1]["date"]}).')
if removed:
    print(f'Removed {len(removed)} page(s) no longer published.')
if scheduled:
    nxt = scheduled[0]
    print(f'Holding back {len(scheduled)} scheduled studies dated after {TODAY}.')
    print(f'  Next up: {nxt["date"]} — {nxt["title"]}')
    print('  They go live automatically the next time you build on or after that date.')
if drafts:
    print(f'Skipping {len(drafts)} draft entr{"y" if len(drafts) == 1 else "ies"} '
          f'(index {", ".join(str(d["index"]) for d in drafts)}) - '
          f'still being written.')
print(f'Guides: {len(_h["hubs"])} pages in guides/, linked from {len(_h["membership"])} studies.')
print(f'Homepage: {len(home_cards)} latest studies written into index.html.')
print(f'Tracker: {_t["faculty"]} faculty across {_t["posted"]} posted programs written into tools/faculty-accepting-students.html ({_t["programs"]} programs total).')
# ---------------------------------------------------------- redirect rules
# Extensionless URLs still resolve on Netlify even with Pretty URLs off, so
# every page answers at two addresses. These rules send the duplicate to the
# canonical one. Generated from the same page list the canonical check walks.
import render_redirects

_r = render_redirects.render()
print(f'Redirects: {_r} extensionless rules written into _redirects.')

# --------------------------------------------------- canonical/sitemap check
# Runs last, once every page exists, so a page whose canonical does not match
# where it actually serves fails the build instead of shipping.
import check_canonicals

_problems, _n, _notes = check_canonicals.check()
if _problems:
    print()
    print(f'Canonical check FAILED on {len(_problems)} page(s):')
    for _p in _problems:
        print(f'  ! {_p}')
    raise SystemExit(1)
print(f'Canonicals: {_n} pages checked, all matching their served path and the sitemap.')
print('Tags:', ', '.join(f'{k} ({len(v)})' for k, v in sorted(by_tag.items())))
