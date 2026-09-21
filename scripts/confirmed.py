# -*- coding: utf-8 -*-
"""The "we asked the school and they answered" marker.

Two renderers draw this -- the tracker list and the individual program pages --
and they have to say the same thing, so the rule for what it says lives here
rather than twice.

The marker is not a quality stamp on the entry. It records one specific fact:
a person at that program answered a direct question about their own admissions
this cycle, on a date. That is the strongest source the tracker has, which is
exactly why it must not be shown where it would flatter a page that contradicts
it -- so when what they told us cuts against what the entry shows, it turns
amber and quotes them instead of claiming confirmation.

The person is never named. See survey_apply.py for why.
"""

ANSWER_WORDS = {
    "yes": "admitting",
    "no": "not admitting",
    "undecided": "not decided yet",
}

# A check inside a circle. Inline rather than an emoji so it renders the same
# on every platform and inherits the pill's colour.
_TICK = ('<svg class="fac-verified-icon" viewBox="0 0 16 16" aria-hidden="true" '
         'focusable="false"><circle cx="8" cy="8" r="7" fill="none" '
         'stroke="currentColor" stroke-width="1.6"/><path d="M4.8 8.3l2.1 2.1 '
         '4.3-4.5" fill="none" stroke="currentColor" stroke-width="1.8" '
         'stroke-linecap="round" stroke-linejoin="round"/></svg>')

_WARN = ('<svg class="fac-verified-icon" viewBox="0 0 16 16" aria-hidden="true" '
         'focusable="false"><path d="M8 1.8l6.2 11.4H1.8z" fill="none" '
         'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
         '<path d="M8 6.2v3.1" stroke="currentColor" stroke-width="1.6" '
         'stroke-linecap="round"/><circle cx="8" cy="11.3" r="0.9" '
         'fill="currentColor"/></svg>')


def contradicts(answer, program):
    """Does what they said cut against what the entry shows?

    "Admitting" against a pending entry is not a contradiction -- the list
    simply is not out yet -- so only these cases count.

    The awkward one is "not decided yet" against a posted page, because
    `posted` covers two different claims. A page saying three faculty "plan to
    admit" does contradict a director who says nothing is settled. A page
    saying two faculty "may be considering applications" does not: that IS
    "not decided yet", in the program's own words. So the test is whether the
    page actually names somebody as accepting, not merely whether a list
    exists. Three of the four programs flagged on 18 September turned out to
    be the second kind.

    A cohort program is the exception: it never names anyone, so its status is
    the whole of its claim and has to be taken at face value.

    survey_pull.verdict imports this so the console report and the web page
    cannot drift apart.
    """
    status = program.get("status", "")
    admitting = status in ("posted", "cohort")
    if answer == "yes":
        return status == "closed"
    if answer == "no":
        return admitting
    if answer == "undecided":
        if status == "cohort":
            return True
        return status == "posted" and bool(program.get("accepting"))
    return False


def pill(program, e, fmt_date=None):
    """The marker itself, or "" for a program that has not answered.

    `e` is the caller's HTML escaper; `fmt_date` its date formatter, if it has
    one. Both are passed in so this module needs no opinion about either.
    """
    c = program.get("confirmed")
    if not c or not c.get("answer"):
        return ""

    answer = c["answer"]
    words = ANSWER_WORDS.get(answer, answer)
    when = c.get("on") or ""
    shown = fmt_date(when) if (fmt_date and when) else when
    cycle = c.get("cycle") or program.get("cycle") or "this cycle"
    clash = contradicts(answer, program)

    if clash:
        title = (f"The program told us on {shown} that it is {words} for "
                 f"{cycle}. The entry below is what their own page said when "
                 f"we last read it. Both dates are shown so you can judge "
                 f"which is newer.")
        return (f'<span class="fac-verified is-conflict" title="{e(title)}">'
                f'{_WARN} The school says: {e(words)}</span>')

    how = ("in a reply to our email" if c.get("via") == "email"
           else "through our survey link")
    title = (f"Answered by the program itself on {shown}, {how}: {words} for "
             f"{cycle}. Not read off a web page — they told us directly.")
    # Green is reserved for "yes". A green tick beside a program that told us
    # it is NOT admitting reads as good news at a glance, and somebody
    # scanning a list of 257 entries reads exactly that much. So the marker
    # always says what they said, and only an opening carries the green.
    tone = "" if answer == "yes" else " is-neutral"
    said = {"yes": "The school confirms: admitting",
            "no": "The school confirms: not admitting",
            "undecided": "The school says: not decided yet"}.get(
                answer, f"The school says: {words}")
    return (f'<span class="fac-verified{tone}" title="{e(title)}">'
            f'{_TICK} {e(said)}</span>')


def sentence(program, e, fmt_date=None):
    """A full sentence for the program page, under the headline answer."""
    c = program.get("confirmed")
    if not c or not c.get("answer"):
        return ""

    answer = c["answer"]
    words = ANSWER_WORDS.get(answer, answer)
    when = c.get("on") or ""
    shown = fmt_date(when) if (fmt_date and when) else when
    cycle = e(c.get("cycle") or program.get("cycle") or "this cycle")
    clash = contradicts(answer, program)

    if clash:
        return (f'<p class="guide-answer-confirmed is-conflict">'
                f'{_WARN} <strong>The program and its own page disagree.</strong> '
                f'Someone at the program told us on {e(shown)} that it is '
                f'{e(words)} for {cycle}. Their page showed something else when '
                f'we last read it. Both are here, with their dates — the '
                f'program is the better source for what it intends, its page '
                f'the better record of what was published.</p>')

    # Opens with the answer itself, not with the fact of confirmation. This
    # paragraph now leads the page, and "Confirmed by the school." as an
    # opener makes a reader hunt for what was actually confirmed.
    verdicts = {"yes": "Yes", "no": "No", "undecided": "Not decided yet"}
    head = verdicts.get(answer, words.capitalize())
    return (f'<p class="guide-answer-confirmed">'
            f'{_TICK} <strong>{e(head)} — confirmed by the school.</strong> '
            f'Someone at the program answered directly on {e(shown)}: '
            f'{e(words)} for {cycle}.</p>')
