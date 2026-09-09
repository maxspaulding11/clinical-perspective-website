# -*- coding: utf-8 -*-
"""Recheck every program page and report what actually changed.

Earlier sweeps re-read all 250-odd pages from scratch every time, which meant
the same 100 unchanged pages were re-scanned on every pass and a real update
could hide among them. This keeps a snapshot of each page's visible text
outside the repo, so a sweep can say "these six pages changed since last time"
and the reading effort goes where it belongs.

  python scripts/sweep.py                 recheck pending + posted (the default)
  python scripts/sweep.py --all           recheck every program, cohort included
  python scripts/sweep.py --status posted only that status
  python scripts/sweep.py --no-save       report without updating the snapshot
  python scripts/sweep.py --no-chrome     skip the browser fallback

Snapshots live in "Tracker Snapshots" beside the Website folder, not inside it:
third-party page text has no business in the site's git history.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, shutil, subprocess, sys
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
SNAP = os.path.join(os.path.dirname(SITE), "Tracker Snapshots")
PAGES = os.path.join(SNAP, "pages")
MANIFEST = os.path.join(SNAP, "manifest.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Verbs seen in the wild. "considering" is here because leaving it out is how
# Wisconsin's full Fall 2027 list went unnoticed on an earlier pass.
VERB = re.compile(
    r"(considering|accepting|recruiting|admitting|reviewing|taking on|seeking|"
    r"welcoming|open to|plan(?:ning)? to (?:take|admit|recruit)|will admit|"
    r"interested in (?:taking|admitting|recruiting))", re.I)
FACULTY = re.compile(r"facult|mentor|advisor|adviser|professor|\blab\b", re.I)


def cycle_re(year):
    return re.compile(
        rf"(fall\s*'?\s*{year}|fall\s*{year % 100}\b|{year}\s*[-–]\s*{(year + 1) % 100}|"
        rf"{year}\s+(?:admissions?|cohort|entry|matriculation))", re.I)


def visible_text(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&#160;", " ")
          .replace("&amp;", "&").replace("&#8217;", "'"))
    return re.sub(r"\s+", " ", t).strip()


GDOC = re.compile(r"docs\.google\.com/document/d/([A-Za-z0-9_-]+)")


def fetch(url):
    # A Google Doc never finishes rendering inside a headless timeout, but it
    # will hand over plain text directly. Stony Brook publishes its list this way.
    m = GDOC.search(url)
    if m:
        url = f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
BLOCK_PAGE = re.compile(
    r"access denied|forbidden|are you a robot|verify you are human|just a moment|"
    r"enable javascript|checking your browser", re.I)


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("google-chrome")


def chrome_fetch(chrome, url, profile, timeout=60):
    """Render a page in headless Chrome and return its DOM.

    A dozen university sites answer plain HTTP requests with 403 because the
    request doesn't look like a browser. Chrome carries a real TLS fingerprint
    and runs the page's JavaScript, which clears most of them -- and it is how
    Michigan's posted list was eventually found after weeks of 403s.
    """
    out = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-blink-features=AutomationControlled",
         f"--user-agent={UA}", "--window-size=1280,900",
         "--virtual-time-budget=9000", f"--user-data-dir={profile}",
         "--dump-dom", url],
        capture_output=True, timeout=timeout)
    return out.stdout.decode("utf-8", "replace")


def scan(text, year):
    """Return the first window where a target-year mention, a recruiting verb
    and a faculty word all appear together."""
    cy = cycle_re(year)
    for m in cy.finditer(text):
        w = text[max(0, m.start() - 300): m.end() + 300]
        if VERB.search(w) and FACULTY.search(w):
            return w.strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="include cohort and closed")
    ap.add_argument("--status", help="restrict to one status")
    ap.add_argument("--year", type=int, default=2027, help="cycle year to look for")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--no-chrome", action="store_true",
                    help="skip the browser fallback for blocked pages")
    args = ap.parse_args()

    data = json.load(open(os.path.join(SITE, "data", "programs.json"), encoding="utf-8"))
    progs = data["programs"]
    if args.status:
        progs = [p for p in progs if p["status"] == args.status]
    elif not args.all:
        progs = [p for p in progs if p["status"] in ("pending", "posted")]
    progs = [p for p in progs if p.get("url")]

    os.makedirs(PAGES, exist_ok=True)
    old = {}
    if os.path.exists(MANIFEST):
        old = json.load(open(MANIFEST, encoding="utf-8")).get("pages", {})

    print(f"rechecking {len(progs)} programs "
          f"({'no snapshot yet - this run seeds it' if not old else 'against last snapshot'})\n")

    results = {}

    def work(p):
        try:
            text = visible_text(fetch(p["url"]))
            return p["id"], text, None
        except Exception as e:
            return p["id"], None, f"{type(e).__name__}: {e}"[:90]

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for pid, text, err in ex.map(work, progs):
            results[pid] = (text, err)

    by_id = {p["id"]: p for p in progs}
    via_browser = []

    # Second pass: anything that failed, or came back looking like a block
    # page, gets retried in a real browser engine.
    if not args.no_chrome:
        chrome = find_chrome()
        retry = [pid for pid, (t, e) in results.items()
                 if e or not t or len(t) < 500 or BLOCK_PAGE.search(t[:400])]
        if retry and not chrome:
            print("chrome not found - skipping browser fallback "
                  f"({len(retry)} pages left unread)\n")
        elif retry:
            profile = os.path.join(SNAP, ".chrome-profile")
            print(f"browser fallback: retrying {len(retry)} page(s)")
            for pid in retry:
                try:
                    text = visible_text(chrome_fetch(chrome, by_id[pid]["url"], profile))
                except Exception as e:
                    print(f"    ! {by_id[pid]['school']} - chrome: {type(e).__name__}")
                    continue
                if len(text) >= 500 and not BLOCK_PAGE.search(text[:400]):
                    results[pid] = (text, None)
                    via_browser.append(pid)
                    print(f"    + {by_id[pid]['school']} recovered ({len(text)} chars)")
            print()
    changed, new, failed, flagged = [], [], [], []
    manifest = dict(old)

    for pid, (text, err) in results.items():
        if err or not text or len(text) < 500:
            failed.append((pid, err or f"page too thin ({len(text or '')} chars)"))
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        prev = old.get(pid)
        if prev is None:
            new.append(pid)
        elif prev["hash"] != digest:
            changed.append(pid)
        manifest[pid] = {"hash": digest, "len": len(text),
                         "checked": date.today().isoformat(),
                         "via": "browser" if pid in via_browser else "http"}

        hit = scan(text, args.year)
        if hit:
            flagged.append((pid, hit))
        if not args.no_save:
            with open(os.path.join(PAGES, pid + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)

    def name(pid):
        p = by_id[pid]
        return f"{p['school']} ({p['status']})"

    print(f"changed since last snapshot : {len(changed)}")
    for pid in sorted(changed):
        print(f"    * {name(pid)}")
    if new:
        print(f"\nno previous snapshot        : {len(new)}")
    print(f"\nfetch failed                : {len(failed)}")
    for pid, why in sorted(failed):
        print(f"    ! {name(pid)} - {why}")

    print(f"\nmentions Fall {args.year} near a recruiting verb: {len(flagged)}")
    for pid, hit in sorted(flagged):
        star = "CHANGED " if pid in changed else ""
        print(f"\n  {star}== {name(pid)}")
        print(f"     {hit[:300]}")

    if not args.no_save:
        json.dump({"updated": date.today().isoformat(), "pages": manifest},
                  open(MANIFEST, "w", encoding="utf-8"), indent=1)
        print(f"\nsnapshot saved: {SNAP}")
    else:
        print("\n--no-save: snapshot left untouched")

    print("\nRead the CHANGED ones first - a page that moved is where a new "
          "list usually appears.")


if __name__ == "__main__":
    sys.exit(main())
