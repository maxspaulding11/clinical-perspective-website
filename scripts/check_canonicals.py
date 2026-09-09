# -*- coding: utf-8 -*-
"""Check that every page's canonical tag matches where that page actually is,
and that the sitemap and the canonicals agree with each other.

Three ways a canonical goes wrong, and this catches all three:

  * a page copied from another page keeps the original's canonical, which
    quietly tells Google the two are the same page;
  * a page exists and is linked but never reaches the sitemap;
  * the sitemap lists a URL whose file was renamed or deleted.

What it cannot see is the serving layer. If the host rewrites URLs -- Netlify's
"Pretty URLs" option strips .html from links as it serves them, without
touching the canonical tags in the HTML -- then every page here can pass this
check and still declare a canonical that does not match the URL a visitor is
on. That is a hosting setting, not something a build step can fix or detect
from the files, so it has to be verified once in the browser or in Search
Console after any change to how the site is served.

Run on its own for a report, or let build.py call it. Exits non-zero on a
mismatch so a broken build is loud.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
BASE_URL = "https://theclinicalperspective.org"

SKIP_DIRS = {".git", "node_modules", "assets", "css", "js", "data", "scripts",
             ".claude", "__pycache__"}
# 404.html is served for URLs that do not exist. It has no canonical URL of
# its own and should not claim one.
NOT_INDEXED = {"404.html"}

CANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.I)
SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>")


def expected(rel):
    """The URL a file serves at. index.html is the directory it sits in."""
    rel = rel.replace(os.sep, "/")
    if rel == "index.html":
        return BASE_URL + "/"
    if rel.endswith("/index.html"):
        return f"{BASE_URL}/{rel[:-len('index.html')]}"
    return f"{BASE_URL}/{rel}"


def pages():
    for root, dirs, files in os.walk(SITE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".html"):
                rel = os.path.relpath(os.path.join(root, f), SITE)
                rel = rel.replace(os.sep, "/")
                if rel not in NOT_INDEXED:
                    yield rel


def check():
    problems, canonicals = [], {}

    for rel in sorted(pages()):
        text = open(os.path.join(SITE, rel.replace("/", os.sep)), encoding="utf-8").read()
        m = CANON.search(text)
        want = expected(rel)
        if not m:
            problems.append(f"{rel}: no canonical tag (should be {want})")
            continue
        got = m.group(1)
        canonicals[got] = rel
        if got != want:
            problems.append(f"{rel}: canonical says {got}, page serves at {want}")

    sitemap_path = os.path.join(SITE, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        problems.append("sitemap.xml is missing")
        return problems, len(canonicals)

    listed = set(SITEMAP_LOC.findall(open(sitemap_path, encoding="utf-8").read()))
    for url in sorted(listed - set(canonicals)):
        problems.append(f"sitemap lists {url}, but no page declares it as canonical")

    # Not every page belongs in the sitemap -- saved.html is a per-visitor list
    # with nothing to index -- so a page missing from it is reported as a note,
    # not a failure.
    notes = [f"not in sitemap: {canonicals[u]}"
             for u in sorted(set(canonicals) - listed)]
    return problems, len(canonicals), notes


def main():
    problems, n, notes = check()
    print(f"canonical check: {n} pages")
    for note in notes:
        print(f"  - {note}")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print("  all canonicals match their served path, and agree with the sitemap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
