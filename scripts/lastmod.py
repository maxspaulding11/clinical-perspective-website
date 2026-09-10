# -*- coding: utf-8 -*-
"""Work out when each page last actually changed, for sitemap <lastmod>.

Google has said for years that it largely ignores <priority>, but it does use
<lastmod> to decide what is worth re-crawling. The tracker changes most days
through the autumn while a study from July has not moved since it was
published, and without lastmod nothing in the sitemap distinguishes them.

The date comes from git rather than the filesystem, because build.py rewrites
every generated page on every run: file mtimes would say all 77 pages changed
today, every day, which is both false and exactly the signal that teaches a
crawler to stop believing the sitemap. Git knows when a file's content last
genuinely changed, and a fresh clone gets the same answer as this machine.

Uncommitted files are dated today -- they have changed, they are just not
recorded yet.

One `git log` walk builds the whole map, rather than a subprocess per file.
"""
import os
import subprocess
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)


def _git(*args):
    return subprocess.run(("git",) + args, cwd=SITE, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def build_map():
    """{repo-relative path: YYYY-MM-DD of the commit that last touched it}."""
    # %cs is the committer date as a bare YYYY-MM-DD. --name-only prints the
    # files in each commit, newest commit first, so the first time a path
    # appears is the last time it changed.
    out = _git("log", "--pretty=format:%cs", "--name-only")
    if out.returncode != 0:
        return {}

    seen, current = {}, None
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 10 and line[4] == "-" and line[7] == "-":
            current = line
        elif current and line not in seen:
            seen[line] = current

    # Anything modified, staged or untracked has changed since its last commit.
    today = date.today().isoformat()
    status = _git("status", "--porcelain")
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            path = line[3:].strip().strip('"')
            if " -> " in path:          # a rename: date the destination
                path = path.split(" -> ", 1)[1]
            if path:
                seen[path] = today
    return seen


def rel_for(url, base_url):
    """The file behind a sitemap URL -- the inverse of the canonical rule."""
    path = url[len(base_url):].lstrip("/")
    if path == "" or path.endswith("/"):
        return path + "index.html"
    return path


class Lookup:
    def __init__(self, base_url):
        self.base_url = base_url
        self.map = build_map()
        self.fallback = date.today().isoformat()
        self.misses = []

    def for_url(self, url):
        rel = rel_for(url, self.base_url)
        found = self.map.get(rel)
        if found is None:
            # Not in git history and not reported as changed: possible in a
            # checkout with no history. Today is the honest answer, since all
            # we know is that the file is here now.
            self.misses.append(rel)
            return self.fallback
        return found
