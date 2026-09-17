# -*- coding: utf-8 -*-
"""Draft the accepting-students survey, one email per program, with signed links.

    python scripts/survey_email.py --template     make the contacts spreadsheet
    python scripts/survey_email.py --limit 20     one day's batch
    python scripts/survey_email.py --status pending --limit 20
    python scripts/survey_email.py                everyone not yet drafted
    python scripts/survey_email.py --redraft --limit 20   do a batch again

Two steps because the addresses do not exist yet and cannot be invented.

Step one, --template, writes Outreach/survey-contacts.csv with a row per
program: id, school, program, status and the department URL already filled in,
and name and email left blank. Fill those two columns in by hand, from each
program's own page. Nothing here scrapes them -- collecting a list of named
academics' contact details is a decision a person makes deliberately, the same
reason scripts/outreach.py leaves [EMAIL] alone.

Step two drafts only for the rows where you have filled the address in, and
says how many are still blank.

It then writes today's date into that row's "drafted" column and skips it next
time, so "--limit 20" run daily walks forward through the list instead of
handing back the same twenty every morning. Nothing here sends anything, so
"drafted" means drafted; if you draft a batch and do not send it, clear the
dates or pass --redraft.

Why the email address has to be known before the draft exists: the one-click
answer is carried by a link signed over the program *and the address it was
sent to*, so an answer can be traced back to a person who can be asked about
it. There is no way to mint that link for an unknown recipient, and a survey
whose answers cannot be attributed would be worse than no survey -- the entries
it changed could not be defended.

Needs SURVEY_SECRET, in the environment or Website/.env, matching the value on
the Spare Change deployment. Without it this refuses rather than writing
hundreds of links that will not verify.

Writes to Outreach/survey/ beside the Website folder, not inside it: drafts of
emails to named academics have no business in the site's git history.
"""
import argparse
import base64
import csv
import hashlib
import hmac
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
CONTACTS = os.path.join(ROOT, "Outreach", "survey-contacts.csv")
OUT = os.path.join(ROOT, "Outreach", "survey")

BASE = "https://theclinicalperspective.org"
TRACKER = f"{BASE}/tools/faculty-accepting-students.html"
APP = "https://spare.theclinicalperspective.org"

# Same exclusions as the DCT note, for the same reasons: a closed program has
# nothing to confirm, and an unverified entry should be read properly by a
# person before anyone emails its director about it.
ASKABLE = ("posted", "pending", "cohort")

ANSWERS = (("yes", "Yes"), ("no", "No"), ("undecided", "Not decided yet"))

# The last column is the one that makes this usable twenty a day for a
# fortnight. Without it --limit 20 sorts the whole list and hands back the same
# first twenty every morning, which is worse than useless: it looks like
# progress. A date in "drafted" takes that row out of the pool.
COLUMNS = ["program_id", "school", "program", "status", "department_url",
           "name", "email", "drafted"]

SIGNOFF = """Thank you for your time,

Maxamus Spaulding
Founder & Editor
The Clinical Perspective
theclinicalperspective@gmail.com
theclinicalperspective.org"""

INTRO = ("I run The Clinical Perspective, a small educational site that "
         "summarises mental health research. Alongside it I keep a free "
         "tracker of which clinical psychology faculty are accepting doctoral "
         "students, for applicants trying to work out where to apply.")


def secret():
    """The environment first, then a .env beside the repo root.

    Same arrangement as scripts/watch_notify.py, and the same refusal if it is
    missing: links signed with a guessed key would all fail verification, and
    they would fail silently, in other people's inboxes, days later."""
    from_env = os.environ.get("SURVEY_SECRET")
    if from_env:
        return from_env
    path = os.path.join(SITE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, _, value = line.partition("=")
            if key.strip() == "SURVEY_SECRET":
                return value.strip().strip('"').strip("'")
    return None


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def mint(key, program, cycle, name, email, issued):
    """One signed token.

    The payload is signed as the exact string that travels in the URL, and the
    verifier recomputes the MAC over what it received rather than
    re-serialising. So the two sides cannot drift apart over key order or
    spacing -- which would show up as a handful of directors' links not
    working, with nothing in common between them."""
    payload = {
        "p": program["id"],
        "c": cycle,
        "e": email,
        "n": name,
        "s": program["school"],
        "g": program["program"],
        "i": issued,
    }
    body = b64(json.dumps(payload, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8"))
    sig = b64(hmac.new(key.encode("utf-8"), body.encode("ascii"),
                       hashlib.sha256).digest())
    return f"{body}.{sig}"


def links(key, program, cycle, name, email):
    issued = int(time.time())
    token = mint(key, program, cycle, name, email, issued)
    return [(label, f"{APP}/survey/respond?t={token}&a={value}")
            for value, label in ANSWERS]


def context(p, cycle):
    """The one line that differs by what the tracker currently claims.

    A survey that ignored what the entry already says would be asking these
    people to confirm something in the dark, and the ones whose entry is wrong
    are exactly the ones worth hearing from."""
    n = len(p.get("accepting") or [])
    checked = p.get("checked", "")
    url = p.get("url", "")
    if p["status"] == "posted":
        return (f"For context, as of {checked} we list {n} faculty accepting "
                f"for {cycle}, read from this page: {url} If that has changed, "
                f"replying is the fastest way to get it fixed.")
    if p["status"] == "pending":
        return (f"For context, we checked {url} on {checked} and could not "
                f"find a {cycle} statement, so your entry says exactly that "
                f"-- \"not posted yet\" -- rather than implying anything about "
                f"your program.")
    return (f"For context, we have your program marked as admitting to the "
            f"incoming class and assigning an advisor afterwards, rather than "
            f"into a named faculty member's lab. That is our inference from "
            f"{url}, and the entry says so in those words.")


def subject(cycle):
    # No school name in the subject, for the reason recorded in outreach.py:
    # the longest ran to 142 characters where Gmail truncates around 70, and
    # the recipient already knows which program is theirs.
    return f"{cycle} admissions -- one question about your program"


def body_lines(p, cycle, name, answer_links):
    """The message as a list of paragraphs, before wrapping or HTML."""
    greeting = f"Dear {name}," if name else "Dear Director of Clinical Training,"
    return [
        greeting,
        INTRO,
        f"Your program is listed here: {TRACKER}#program-{p['id']}",
        (f"I am asking every program the same single question this year, "
         f"because asking is better than inferring from a department page: "
         f"is your program admitting doctoral students for {cycle}?"),
        None,  # the answer links get placed here
        ("Each one opens a page that shows what it is about to record and asks "
         "you to confirm, so a mis-click costs nothing. There is no account "
         "and nothing to fill in."),
        ("If you answer yes, that page also lists the faculty we have for your "
         "program, in case you want to mark which of them are taking students. "
         "That part is entirely optional -- leaving it blank records nothing "
         "about anyone, and your answer above is saved either way."),
        context(p, cycle),
        ("A person reads every answer before anything changes on the site, so "
         "nothing you click appears anywhere automatically. If your entry "
         "needs more than a yes or no, just reply and I will fix it the same "
         "day."),
        "This is a one-off. You will not get a follow-up from me.",
    ]


def rewrap(text, width=78):
    """Re-flow a paragraph, keeping every URL alone on its line.

    Lifted from scripts/outreach.py for the same reason it exists there: a
    person pastes these into a mail client, and a signed link is long enough
    that leaving it to the width rule puts a line break through the middle of
    a token. A broken token is a link that lands on "we can't read that link".
    """
    built, line = [], ""
    for w in text.split():
        url = w.startswith("http")
        if line and (url or len(line) + 1 + len(w) > width):
            built.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
        if url:
            built.append(line)
            line = ""
    if line:
        built.append(line)
    return "\n".join(built)


def as_text(p, cycle, name, answer_links):
    out = []
    for para in body_lines(p, cycle, name, answer_links):
        if para is None:
            for label, href in answer_links:
                out.append(f"{label}:\n{href}")
            continue
        out.append(rewrap(para))
    return "\n\n".join(out) + "\n\n" + SIGNOFF


def as_html(p, cycle, name, answer_links):
    """The version to actually send.

    Paste this into Gmail and the three answers arrive as three short clickable
    words. The plain-text version beside it carries the same links as bare
    URLs, which is correct but reads like a ransom note and invites the
    recipient to wonder which of three 300-character strings they want.
    """
    paras = []
    for para in body_lines(p, cycle, name, answer_links):
        if para is None:
            rows = "".join(
                f'<tr><td style="padding:4px 0"><a href="{html.escape(href, quote=True)}"'
                f' style="display:inline-block;padding:8px 18px;border:1px solid #c9bda8;'
                f'border-radius:5px;color:#2b3f63;text-decoration:none;font-weight:600">'
                f"{html.escape(label)}</a></td></tr>"
                for label, href in answer_links
            )
            paras.append(f'<table role="presentation" style="margin:6px 0 18px">{rows}</table>')
            continue
        # Turn the bare URLs inside a paragraph into links, then escape the rest.
        words = []
        for w in para.split():
            if w.startswith("http"):
                clean = w.rstrip(".,")
                words.append(f'<a href="{html.escape(clean, quote=True)}"'
                             f' style="color:#2b3f63">{html.escape(clean)}</a>'
                             + html.escape(w[len(clean):]))
            else:
                words.append(html.escape(w))
        paras.append(f'<p style="margin:0 0 14px">{" ".join(words)}</p>')

    sign = "<br>".join(html.escape(l) for l in SIGNOFF.split("\n"))
    return (
        '<div style="font-family:-apple-system,\'Segoe UI\',sans-serif;'
        'font-size:15px;line-height:1.6;color:#2b2118;max-width:600px">'
        + "".join(paras)
        + f'<p style="margin:18px 0 0;color:#4a4238">{sign}</p></div>'
    )


def write_template(programs):
    os.makedirs(os.path.dirname(CONTACTS), exist_ok=True)
    if os.path.exists(CONTACTS):
        print(f"{CONTACTS} already exists.")
        print("Not overwriting it -- it has addresses in it that took work to "
              "find.\nDelete it yourself if you really want a fresh one.")
        return 1
    with open(CONTACTS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for p in programs:
            w.writerow([p["id"], p["school"], p["program"], p["status"],
                        p.get("url", ""), "", "", ""])
    print(f"Wrote {len(programs)} rows: {CONTACTS}")
    print("\nFill in the last two columns from each program's own page:")
    print("  name   how to address them, e.g. \"Dr Ramirez\" (used as "
          "\"Dear Dr Ramirez,\")")
    print("  email  the director of clinical training's address")
    print("\nRows with either column blank are skipped, so you can fill in "
          "twenty and draft twenty.")
    return 0


def read_contacts():
    if not os.path.exists(CONTACTS):
        print(f"No contacts file at {CONTACTS}")
        print("Run:  python scripts/survey_email.py --template")
        return None
    with open(CONTACTS, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def notify_secret():
    """NOTIFY_SECRET, which authenticates the test-send relay on the app."""
    from_env = os.environ.get("NOTIFY_SECRET")
    if from_env:
        return from_env
    path = os.path.join(SITE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.partition("=")
            if k.strip() == "NOTIFY_SECRET":
                return v.strip().strip('"').strip("'")
    return None


def send_test(to, subj, body_html, body_text):
    """Post one built draft to the app, which holds the Resend key.

    The message is composed here and only posted there, so there is exactly
    one copy of the survey wording -- see the comment in the route. The links
    inside are real: clicking one records against whichever program was used
    to build the sample, which is why the caller says which that was."""
    key = notify_secret()
    if not key:
        raise SystemExit("NOTIFY_SECRET is not set, in the environment or "
                         "Website/.env. Cannot reach the send relay.")
    payload = json.dumps({"to": to, "subject": subj,
                          "html": body_html, "text": body_text}).encode("utf-8")
    req = urllib.request.Request(
        APP + "/api/survey/test", data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"{APP}/api/survey/test returned {err.code}: "
                         f"{err.read().decode('utf-8', 'replace')[:300]}")


def stamp_drafted(ids, today):
    """Write today's date into the "drafted" column for the rows just drafted.

    Every other column is written back exactly as it was read, because this
    file is a spreadsheet a person is part-way through filling in by hand and
    losing an afternoon of it would be unforgivable. The column is added if an
    older template did not have it.

    Excel holds an exclusive lock on an open file, and the likeliest moment to
    run this is right after editing. So a failure here says what to do and does
    not pretend the drafts failed -- they are already written."""
    try:
        with open(CONTACTS, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or COLUMNS)
            rows = list(reader)
    except OSError as err:
        return f"could not re-read the spreadsheet: {err}"

    if "drafted" not in fields:
        fields.append("drafted")
    for r in rows:
        if (r.get("program_id") or "").strip() in ids:
            r["drafted"] = today

    tmp = CONTACTS + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, CONTACTS)
    except OSError as err:
        if os.path.exists(tmp):
            os.remove(tmp)
        return (f"the drafts are written, but the spreadsheet could not be "
                f"marked: {err}\n  Close it in Excel and run the same command "
                f"again -- already-drafted rows will simply redraft.")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", action="store_true",
                    help="write the contacts spreadsheet and stop")
    ap.add_argument("--status", choices=ASKABLE, help="only this status")
    ap.add_argument("--limit", type=int,
                    help="stop after this many, for sending in batches")
    ap.add_argument("--redraft", action="store_true",
                    help="include rows already drafted (they are skipped by "
                         "default, so --limit walks forward each day)")
    ap.add_argument("--test-email", metavar="ADDRESS",
                    help="mail one sample draft to this address and stop: no "
                         "row is marked drafted, the spreadsheet is untouched, "
                         "and the links in it are real and clickable")
    args = ap.parse_args()

    data = json.load(open(os.path.join(SITE, "data", "programs.json"),
                          encoding="utf-8"))
    cycle = data.get("cycle", "the coming cycle")
    programs = {p["id"]: p for p in data["programs"] if p["status"] in ASKABLE}

    if args.template:
        ordered = sorted(programs.values(),
                         key=lambda p: (p["status"], p["school"].lower()))
        return write_template(ordered)

    key = secret()
    if not key:
        raise SystemExit(
            "SURVEY_SECRET is not set, in the environment or Website/.env.\n"
            "Refusing to write links that will not verify.")

    # A test needs no contacts file and marks nothing. It exists so the email
    # can be read in a real inbox while it is still incapable of reaching a
    # program director, so it returns before anything is read or written.
    if args.test_email:
        p = sorted((x for x in programs.values()
                    if x["status"] == (args.status or "pending")),
                   key=lambda x: x["school"].lower())[0]
        answer_links = links(key, p, cycle, "Dr Spaulding", args.test_email)
        result = send_test(args.test_email, subject(cycle),
                           as_html(p, cycle, "Dr Spaulding", answer_links),
                           as_text(p, cycle, "Dr Spaulding", answer_links))
        print(f"Sent to {result.get('to')} from {result.get('from')}")
        print(f"Sample built from: {p['school']} — {p['program']} "
              f"({p['status']})")
        print("\nThe three links work. Clicking one records a real answer "
              f"against\n{p['id']}, attributed to {args.test_email}. Tell me "
              "and I will delete it.")
        print("\nNothing was marked drafted and the spreadsheet is untouched.")
        return 0

    rows = read_contacts()
    if rows is None:
        return 1

    ready, blank, unknown, done = [], 0, [], 0
    for r in rows:
        pid = (r.get("program_id") or "").strip()
        name = (r.get("name") or "").strip()
        email = (r.get("email") or "").strip()
        if not pid:
            continue
        if pid not in programs:
            unknown.append(pid)
            continue
        if not email:
            blank += 1
            continue
        if (r.get("drafted") or "").strip() and not args.redraft:
            done += 1
            continue
        if args.status and programs[pid]["status"] != args.status:
            continue
        ready.append((programs[pid], name, email))

    ready.sort(key=lambda t: (t[0]["status"], t[0]["school"].lower()))
    if args.limit:
        ready = ready[:args.limit]

    if not ready:
        print("Nothing to draft.")
        if done:
            print(f"  {done} row(s) are already drafted "
                  f"(--redraft to do them again).")
        if blank:
            print(f"  {blank} row(s) still have no email address: {CONTACTS}")
        if not done and not blank:
            print(f"  Nothing in the spreadsheet matches: {CONTACTS}")
        return 0

    os.makedirs(OUT, exist_ok=True)
    for p, name, email in ready:
        answer_links = links(key, p, cycle, name, email)
        stem = os.path.join(OUT, f"{p['status']}--{p['id']}")
        header = (f"To: {email}   ({p['school']} - {p['program']})\n"
                  f"Subject: {subject(cycle)}\n"
                  f"Drafted: {date.today().isoformat()}\n"
                  + "-" * 72 + "\n\n")
        with open(stem + ".txt", "w", encoding="utf-8") as f:
            f.write(header + as_text(p, cycle, name, answer_links) + "\n")
        with open(stem + ".html", "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><meta charset=utf-8>\n"
                    f"<title>{html.escape(p['school'])}</title>\n"
                    f"<!-- To: {html.escape(email)} | Subject: "
                    f"{html.escape(subject(cycle))} -->\n"
                    + as_html(p, cycle, name, answer_links) + "\n")

    today = date.today().isoformat()
    problem = stamp_drafted({p["id"] for p, _, _ in ready}, today)

    print(f"Drafted {len(ready)} email(s) into {OUT}")
    print(f"Subject line: {subject(cycle)}")
    for p, _, email in ready:
        print(f"  {p['status']}--{p['id']}.html   -> {email}")
    if problem:
        print(f"\nWarning: {problem}")
    else:
        print(f"\nMarked those {len(ready)} row(s) drafted {today}, so the "
              f"next run moves on\nto the next batch.")
    if blank:
        print(f"\n{blank} program(s) still have no address in the spreadsheet.")
    if done:
        print(f"{done} were drafted on an earlier run and skipped.")
    if unknown:
        print(f"\n{len(unknown)} row(s) name a program that is not askable "
              f"(closed, unverified, or renamed): {', '.join(unknown[:5])}"
              + (" ..." if len(unknown) > 5 else ""))
    print("\nOpen the .html file, select all, copy, paste into Gmail. The "
          "three answers\narrive as three clickable words. The .txt beside it "
          "is the same message with\nbare URLs, if you would rather send plain "
          "text.")
    print("\nTwenty a day from your own address, not two hundred at once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
