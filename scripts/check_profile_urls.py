# -*- coding: utf-8 -*-
"""Find which faculty profile links are actually dead, and remember the answer.

A per-professor page whose only outbound link 404s is worse than no page: it
sends a reader to a dead end and tells a crawler this site links to nothing.
So the pages are only generated where the profile link resolves.

Only 404 and 410 count as dead. This is the lesson scripts/outcomes.py
learned expensively: university sites block automated requests constantly, and
403, 429, timeouts and 5xx all mean "not answering us", not "not there". In a
150-URL sample, 137 returned 200, six returned 403 and two returned 404 --
treating the 403s as broken would have deleted six perfectly good pages.

The result is cached here rather than re-checked on every build, because the
daily build must not fetch 2,600 university pages every morning. Re-run this
by hand every few months, or when the dead count looks wrong:

    python scripts/check_profile_urls.py
    python scripts/check_profile_urls.py --only-unknown   # skip cached ones

Writes scripts/profile-urls.json, which render_faculty.py reads. A professor
missing from that file is given the benefit of the doubt and gets a page: a
check that has not run is not evidence of a broken link.
"""
import argparse
import collections
import concurrent.futures as cf
import datetime
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
PROFS = os.path.join(SITE, "data", "professors.json")
OUT = os.path.join(HERE, "profile-urls.json")

# Identifies the crawler and says where to complain, which is the least a
# script making a few thousand requests to other people's servers can do.
UA = ("Mozilla/5.0 (compatible; TCPBot/1.0; +https://theclinicalperspective.org"
      "/about.html) theclinicalperspective@gmail.com")

DEAD = (404, 410)


def status(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        # Some servers reject HEAD but serve GET. Worth one retry before
        # calling a page dead, because this decides whether it gets a page.
        if e.code in DEAD or e.code == 405:
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.status
            except urllib.error.HTTPError as e2:
                return e2.code
            except Exception as ex:
                return type(ex).__name__
        return e.code
    except Exception as e:
        return type(e).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-unknown", action="store_true",
                    help="skip URLs already in the cache")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    profs = json.load(io.open(PROFS, encoding="utf-8"))["professors"]
    cache = {}
    if os.path.exists(OUT):
        cache = json.load(io.open(OUT, encoding="utf-8")).get("urls", {})

    urls = sorted({p["url"] for p in profs
                   if (p.get("url") or "").startswith(("http://", "https://"))})
    todo = [u for u in urls if not (args.only_unknown and u in cache)]
    print(f"{len(urls)} distinct profile URLs, checking {len(todo)}")

    done = 0
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for url, st in zip(todo, ex.map(status, todo)):
            cache[url] = st
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(todo)}")

    counts = collections.Counter(cache.values())
    dead = [u for u, s in cache.items() if s in DEAD]
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"_readme": ("Written by scripts/check_profile_urls.py. "
                               "Only 404/410 are treated as dead; 403 and "
                               "timeouts mean the server refused us, not that "
                               "the page is gone."),
                   "checked": datetime.date.today().isoformat(),
                   "dead": sorted(dead),
                   "urls": dict(sorted(cache.items()))}, f, indent=1)
        f.write("\n")

    print(f"\nwrote {os.path.relpath(OUT, SITE)}")
    for k, v in counts.most_common(8):
        print(f"  {str(k):<22} {v}")
    print(f"\n{len(dead)} dead (404/410) of {len(cache)} — these get no page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
