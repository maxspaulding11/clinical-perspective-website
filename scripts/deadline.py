# -*- coding: utf-8 -*-
"""Say which year an application deadline falls in.

Most programs write their deadline the way a department writes it for people
who already know the cycle -- "December 1" -- and 134 of the 212 deadlines on
this tracker were captured exactly that way. On their own page that is clear
enough. On a page that lists 257 programs across two calendar years it is not:
a reader looking at "December 1" in September 2026 has no way to tell whether
that means this coming December or the one after, and picking wrong costs them
the application.

The year is not a guess. The entry states which intake it describes, and an
intake fixes the year: for Fall 2027 entry, an autumn deadline is 2026 and a
January-to-July one is 2027, because nobody takes applications after the class
starts. So the year is derived here rather than written into the data -- the
data keeps what the program actually published, and this adds the part the
program left implicit.

A string naming two deadlines gets both dated, since each month fixes its own
year by the same rule: "Priority: November 1; Final: April 1" is November 2026
and April 2027, and saying so is the whole point of the exercise. What such a
string does not get is an ISO date for schema.org, because there is no single
date to give and inventing one would be worse than leaving the field out.
"Rolling admissions" and "TBD" name no month and are passed through untouched.
"""
import re

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_N = {m: i + 1 for i, m in enumerate(MONTHS)}

_MONTH_RE = re.compile(r"\b(%s)\b" % "|".join(MONTHS), re.I)
# "December 1", "December 1 (11:59 PM EST)", "November 1, 5:00 pm CST"
_SIMPLE = re.compile(r"^\s*(%s)\s+(\d{1,2})\b" % "|".join(MONTHS), re.I)
_HAS_YEAR = re.compile(r"\b(19|20)\d\d\b")
_CYCLE_YEAR = re.compile(r"\b(20\d\d)\b")
# Every "Month D" in a string, for the two-deadline case.
_ANY_DATE = re.compile(r"\b(%s)\s+(\d{1,2})\b" % "|".join(MONTHS), re.I)


def entry_year(program):
    """The year the class starts, from the entry's cycle. None if unstated."""
    m = _CYCLE_YEAR.search(str(program.get("cycle") or ""))
    return int(m.group(1)) if m else None


def year_for(month_name, start_year):
    """Which calendar year a deadline in `month_name` falls in.

    An application closes before the class starts, so autumn belongs to the
    year before the intake and the new year's months to the intake year
    itself. August is the boundary: a deadline that late in the year is for
    the following autumn, not the one a few weeks away.
    """
    n = MONTH_N[month_name.capitalize()]
    return start_year - 1 if n >= 8 else start_year


def resolve(program):
    """(display text, ISO date or None) for this program's deadline.

    The ISO date is only returned when the string names exactly one date, so
    it is safe to hand to schema.org. Everything else gets None and the
    caller leaves the field out rather than publishing something invalid.
    """
    raw = (program.get("applicationDeadline") or "").strip()
    if not raw:
        return "", None

    start = entry_year(program)
    months = _MONTH_RE.findall(raw)
    simple = _SIMPLE.match(raw)

    if _HAS_YEAR.search(raw) or start is None:
        iso = None
        if simple and _HAS_YEAR.search(raw) and len(months) == 1:
            y = _HAS_YEAR.search(raw)
            iso = "%s-%02d-%02d" % (y.group(), MONTH_N[simple.group(1).capitalize()],
                                    int(simple.group(2)))
        return raw, iso

    # Two deadlines in one string -- a priority date and a final one, usually.
    # Each month still fixes its own year by the same rule, so both can be
    # dated; what cannot be done is pick one of them for schema.org, so the
    # ISO date stays None and the field is left out rather than guessed.
    if len(months) > 1:
        def stamp(m):
            y = year_for(m.group(1), start)
            return "%s %s, %d" % (m.group(1), m.group(2), y)
        return _ANY_DATE.sub(stamp, raw), None

    # One date, but the string does not open with it. Still datable -- it is
    # just a sentence rather than a bare deadline -- but not a firm deadline,
    # so no ISO date goes to schema.org.
    if not simple:
        return _ANY_DATE.sub(
            lambda m: "%s %s, %d" % (m.group(1), m.group(2),
                                     year_for(m.group(1), start)), raw), None

    month, day = simple.group(1), int(simple.group(2))
    y = year_for(month, start)
    shown = "%s%s" % (raw[:simple.end()], ", %d" % y)
    shown += raw[simple.end():]
    return shown, "%d-%02d-%02d" % (y, MONTH_N[month.capitalize()], day)
