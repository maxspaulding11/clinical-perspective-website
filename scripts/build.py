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


studies = []
seen = set()
for s in raw:
    m = meta[str(s['index'])]
    slug = slugify(m['title'])
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
      <a href="{prefix}about.html">About</a>
      <a href="{prefix}queue.html">Reader Queue</a>
      <a href="{prefix}tools/index.html">Tools</a>
      <a href="{prefix}index.html#submit">Submit Research</a>
      <a href="https://spare.theclinicalperspective.org" target="_blank" rel="noopener" class="nav-spare-change">🪙 Spare Change</a>
      <a href="{IG_PROFILE}" target="_blank" rel="noopener" class="nav-ig" aria-label="Instagram"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 2.2c3.2 0 3.6 0 4.9.07 1.2.06 2 .25 2.4.42.6.24 1 .53 1.5 1s.76.9 1 1.5c.17.4.36 1.2.42 2.4.06 1.3.07 1.7.07 4.9s0 3.6-.07 4.9c-.06 1.2-.25 2-.42 2.4-.24.6-.53 1-1 1.5s-.9.76-1.5 1c-.4.17-1.2.36-2.4.42-1.3.06-1.7.07-4.9.07s-3.6 0-4.9-.07c-1.2-.06-2-.25-2.4-.42-.6-.24-1-.53-1.5-1s-.76-.9-1-1.5c-.17-.4-.36-1.2-.42-2.4C2.2 15.6 2.2 15.2 2.2 12s0-3.6.07-4.9c.06-1.2.25-2 .42-2.4.24-.6.53-1 1-1.5s.9-.76 1.5-1c.4-.17 1.2-.36 2.4-.42C8.4 2.2 8.8 2.2 12 2.2zm0 1.8c-3.14 0-3.5 0-4.75.07-1 .05-1.5.2-1.86.34-.47.18-.8.4-1.15.75s-.57.68-.75 1.15c-.14.36-.29.87-.34 1.86C3.1 8.5 3.1 8.86 3.1 12s0 3.5.07 4.75c.05 1 .2 1.5.34 1.86.18.47.4.8.75 1.15s.68.57 1.15.75c.36.14.87.29 1.86.34 1.25.07 1.61.07 4.75.07s3.5 0 4.75-.07c1-.05 1.5-.2 1.86-.34.47-.18.8-.4 1.15-.75s.57-.68.75-1.15c.14-.36.29-.87.34-1.86.07-1.25.07-1.61.07-4.75s0-3.5-.07-4.75c-.05-1-.2-1.5-.34-1.86a3.1 3.1 0 0 0-.75-1.15a3.1 3.1 0 0 0-1.15-.75c-.36-.14-.87-.29-1.86-.34C15.5 4 15.14 4 12 4zm0 3.3a4.7 4.7 0 1 1 0 9.4a4.7 4.7 0 0 1 0-9.4zm0 1.8a2.9 2.9 0 1 0 0 5.8a2.9 2.9 0 0 0 0-5.8zm5-2.5a1.1 1.1 0 1 1-2.2 0a1.1 1.1 0 0 1 2.2 0z"/></svg></a>
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
        "author": {"@type": "Organization", "name": "The Clinical Perspective"},
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

      <p class="study-disclaimer">
        This is an educational summary, not medical or psychological advice, and
        it is not a substitute for consultation with a qualified professional.
        Read the full <a href="../legal.html">disclaimer</a>.
      </p>

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
    (f'{BASE_URL}/legal.html', '0.3'),
]
for s in newest_first:
    urls.append((f"{BASE_URL}/studies/{s['slug']}.html", '0.8'))

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, pri in urls:
    lines.append('  <url>')
    lines.append(f'    <loc>{loc}</loc>')
    lines.append(f'    <priority>{pri}</priority>')
    lines.append('  </url>')
lines.append('</urlset>')
with open(os.path.join(SITE, 'sitemap.xml'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f'Published {len(studies)} studies (through {studies[-1]["date"]}).')
if removed:
    print(f'Removed {len(removed)} page(s) no longer published.')
if scheduled:
    nxt = scheduled[0]
    print(f'Holding back {len(scheduled)} scheduled studies dated after {TODAY}.')
    print(f'  Next up: {nxt["date"]} — {nxt["title"]}')
    print('  They go live automatically the next time you build on or after that date.')
print('Tags:', ', '.join(f'{k} ({len(v)})' for k, v in sorted(by_tag.items())))
