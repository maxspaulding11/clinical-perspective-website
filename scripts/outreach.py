# -*- coding: utf-8 -*-
"""Fill the DCT outreach note once per program, from the tracker's own data.

    python scripts/outreach.py                  every program, grouped by status
    python scripts/outreach.py --status cohort   just the cohort inferences
    python scripts/outreach.py --limit 20        a sendable batch

The facts in these emails -- how many faculty we list, which page we read, the
date we read it, the anchor for their entry -- are the facts the email is
asking them to check, so none of them should be retyped by a human into an
email to the person best placed to notice a mistake. They come straight out of
data/programs.json.

What this does NOT do is look up names or email addresses. Those live on each
program's own page, and collecting a list of real people's contact details is
a judgement call for a person to make deliberately, not something to scrape in
a loop. Each draft leaves [LAST NAME] and [EMAIL] to fill in.

Writes to an Outreach folder beside the Website folder, not inside it: drafts
of emails to named academics have no business in the site's git history.
"""
import argparse
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
OUT = os.path.join(os.path.dirname(SITE), "Outreach", "drafts")
BASE = "https://theclinicalperspective.org"
TRACKER = f"{BASE}/tools/faculty-accepting-students.html"

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

# Short intro for version C: it needs the room for the actual point.
INTRO_SHORT = ("I run The Clinical Perspective, a small educational site that "
               "summarises mental health research. Alongside it I keep a free "
               "tracker of which clinical psychology faculty are accepting "
               "doctoral students.")


# No subject line carries the school name. Embedding it pushed the longest to
# 142 characters -- "Florida School of Professional Psychology at National
# Louis University - Tampa" -- where Gmail truncates around 70, and the
# recipient knows which program is theirs.


def posted(p, cycle):
    n = len(p.get("accepting") or [])
    return f"""Subject: Your {cycle} accepting-faculty list on an applicant tracker

Dear Dr [LAST NAME],

{INTRO}

Your program is listed here:
{TRACKER}#program-{p['id']}

As of {p.get('checked', '')} we have {n} faculty accepting for {cycle}, read
from this page:
{p.get('url', '')}

The sentence we took that from is quoted on the entry so applicants can judge
it themselves rather than taking our word for it.

If anything there is wrong or out of date, I would rather hear it from you than
have applicants act on it -- just reply and I will fix it the same day. No
reply needed if it looks right.

If you think it would save your applicants some time, you are welcome to share
or link it; no obligation either way."""


def pending(p, cycle):
    return f"""Subject: {cycle} accepting-faculty information for your program

Dear Dr [LAST NAME],

{INTRO}

Your program is listed here:
{TRACKER}#program-{p['id']}

We checked {p.get('url', '')} on {p.get('checked', '')} and could not find a
statement of which faculty are accepting for {cycle}, so the entry says exactly
that -- "not posted yet" -- rather than implying anything about your program. If
that information is published somewhere I have missed, please point me at it and
I will correct the entry today.

If you would rather the entry said something different while nothing is posted,
tell me and I will change it."""


def cohort(p, cycle):
    return f"""Subject: An assumption we have made about your admissions model

Dear Dr [LAST NAME],

{INTRO_SHORT}

Your program is listed here:
{TRACKER}#program-{p['id']}

I want to flag an assumption rather than leave it sitting there. We have marked
your program as admitting to the incoming class and assigning an advisor
afterwards, rather than admitting into a named faculty member's lab. The page we
read was:
{p.get('url', '')}

It does not state its model either way, so that is our inference, and the entry
says so in those words.

If it is wrong, please tell me and I will correct it today. If applicants should
be identifying a mentor before applying to you, I would much rather the page
said so."""


def rewrap(body, width=78):
    """Re-flow each paragraph of the message body.

    The templates carry line breaks that a long interpolated URL then ruins,
    and a person pastes these into a mail client, so ragged text would be the
    first thing they see.

    A URL always gets its own line. Left to the width rule it lands wherever
    it happens to fit, which reads as a mistake and makes the link harder to
    click. The signature is not passed through here at all -- its line breaks
    are the point.
    """
    out = []
    for para in body.split("\n\n"):
        built, line = [], ""
        for w in para.split():
            url = w.startswith("http")
            if line and (url or len(line) + 1 + len(w) > width):
                built.append(line)
                line = w
            else:
                line = f"{line} {w}" if line else w
            if url:                 # nothing follows a URL on its line
                built.append(line)
                line = ""
        if line:
            built.append(line)
        out.append("\n".join(built))
    return "\n\n".join(out)


TEMPLATES = {"posted": posted, "pending": pending, "cohort": cohort}
# "closed" and "unverified" are left out on purpose: for a closed program there
# is nothing to correct, and an unverified entry should be read properly before
# anyone emails its director about it.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", choices=sorted(TEMPLATES),
                    help="only this status")
    ap.add_argument("--limit", type=int,
                    help="stop after this many, for sending in batches")
    args = ap.parse_args()

    data = json.load(open(os.path.join(SITE, "data", "programs.json"),
                          encoding="utf-8"))
    cycle = data.get("cycle", "the coming cycle")
    programs = [p for p in data["programs"] if p["status"] in TEMPLATES]
    if args.status:
        programs = [p for p in programs if p["status"] == args.status]
    programs.sort(key=lambda p: (p["status"], p["school"].lower()))
    if args.limit:
        programs = programs[:args.limit]

    os.makedirs(OUT, exist_ok=True)
    counts = {}
    for p in programs:
        # Only the message body is re-flowed. The subject is one line by
        # definition -- wrapping it split "Adler University - Chicago's
        # admissions" across two -- and the signature's line breaks are the
        # point of it.
        subject, rest = TEMPLATES[p["status"]](p, cycle).split("\n\n", 1)
        body = f"{subject}\n\n{rewrap(rest)}\n\n{SIGNOFF}"
        path = os.path.join(OUT, f"{p['status']}--{p['id']}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"To: [EMAIL]   ({p['school']} - {p['program']})\n")
            f.write(f"Drafted: {date.today().isoformat()}\n")
            f.write("-" * 72 + "\n\n")
            f.write(body + "\n")
        counts[p["status"]] = counts.get(p["status"], 0) + 1

    print(f"{len(programs)} drafts written to {OUT}")
    for status, n in sorted(counts.items()):
        print(f"  {status:<10} {n}")
    print("\nEach needs a name and an address, from that program's own page.")
    print("Send in small batches -- fifty psychology departments receiving the "
          "same email\none morning looks like what it would look like.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
