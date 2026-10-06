# -*- coding: utf-8 -*-
"""Check that every number in a drafted batch exists in the paper it cites.

This is the guard against the one failure that matters on this feed. Writing
a summary from an abstract is mostly reliable, and the way it goes wrong is
specific and hard to see: a figure from the wrong row, a subgroup's effect
quoted as the headline, a confidence interval remembered slightly wider than
it was. Every one of those is a number in the draft that is not in the source.

So: pull every number out of what was written, and look for it in the
abstract. A number that is not there has to be explained or removed.

Three kinds of miss, reported separately because they mean different things:

  MISSING   the number is nowhere in the paper. Usually an error.
  ROUNDED   the draft says 19, the paper says 19.1. Usually fine.
  DERIVED   the draft says a number the paper implies but does not print,
            like "one in 32" for 3.1%. Legitimate, but worth a look.

It cannot check whether a sentence characterises a result fairly -- that
needs a reader. It can prove that no figure was invented, which is the part
a script does better than a person.

    python scripts/verify_batch.py entries.json
    python scripts/verify_batch.py entries.json --candidates path/to/cands.json
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))

NUM = re.compile(r"\d+(?:\.\d+)?")

# Thousands are written three different ways across these sources: 11889 in a
# draft, 11,889 in prose, and "11 889" in PubMed, which uses a space (often a
# thin one). Unnormalised, the last tokenises as 11 and 889 and every large
# count in a batch is reported as fabricated. Both sides go through this.
_THOUSANDS = re.compile(r"(\d)[\s   ](\d{3})(?!\d)")


def normalise(s):
    s = s.replace(",", "")
    for _ in range(3):          # 1 234 567 needs more than one pass
        s = _THOUSANDS.sub(r"\1\2", s)
    return s

# Numbers that legitimately appear in a draft without being in the abstract.
# Years, and the small integers that show up in ordinary prose ("one in five",
# "two cohorts", "three things"). Keeping this list short on purpose: the
# whole value of the check is that it is strict.
def ignorable(tok):
    v = float(tok)
    if 1900 <= v <= 2100 and "." not in tok:   # a year
        return True
    if v <= 10 and "." not in tok:             # small prose integers
        return True
    return False


def match(tok, nums):
    """Compare numbers as numbers, never as substrings.

    The first version searched for the digits inside the abstract's text, and
    it let a fabricated figure straight through: a drafted 24.7% rounds to 25,
    and "25" is a substring of "December 2025", so the check passed on a
    number the paper never contained. Parse both sides into values and
    compare them.

    Rounding is accepted in both directions, because a lay summary rounds
    76.92% to 77% far more often than the reverse.
    """
    v = float(tok)
    if any(p == v for p in nums):
        return "exact"
    for p in nums:
        # Only call it rounding if one side really is the rounded form of the
        # other, which keeps 24.7 from matching an unrelated 25.
        if abs(p - v) < 0.5 and (round(p) == v or round(v) == p
                                 or round(p, 1) == v or round(v, 1) == p):
            return "rounded"
    return None


def derived(tok, nums):
    """A number the paper implies but does not print.

    Two cases, both legitimate and both found in real drafts: a percentage
    restated as a rate ("one in 32" for 3.1%), and a total the paper gives
    only as its parts (55 homicide plus 49 non-homicide is 104 patients).
    """
    v = float(tok)
    if v <= 0:
        return False
    for p in nums:
        if p <= 0:
            continue
        # "one in N" from a percentage, either direction
        if abs(100.0 / v - p) < max(0.6, p * 0.06):
            return True
        if abs(100.0 / p - v) < max(0.6, v * 0.06):
            return True
    # A total stated only as its parts -- but exactly, and only for counts.
    #
    # With a tolerance this was useless: an abstract holds twenty-odd numbers,
    # so two hundred pairs, and one lands near any target you like. It passed
    # a deliberately fabricated 24.7% because 22.7 + 2.04 = 24.74. Whole
    # numbers, summing exactly, or it does not count.
    if v != int(v):
        return False
    ints = [p for p in nums if p == int(p) and p >= 2]
    for i, a in enumerate(ints):
        for b in ints[i + 1:]:
            if a + b == v:
                return True
    return False


def check_entry(e, source):
    hay = normalise(source.get("title", "") + " " + source.get("abstract", ""))
    nums = [float(m.group()) for m in NUM.finditer(hay)]
    # Commas come off BOTH sides. Stripping them only from the abstract made
    # a written "3,974 incidents" tokenise as 3 and 974 against a source 3974,
    # so two correct entries were reported as fabricated.
    written = [
        e.get("ig", ""), e.get("summary", ""), e.get("blurb", ""),
        e.get("title", ""), e.get("head_accent", ""), e.get("head", ""),
        " ".join(e.get("blocks") or []),
        str((e.get("stat") or {}).get("value", "")),
        str((e.get("stat") or {}).get("label", "")),
    ]
    written = normalise(" ".join(written))
    hits = {"missing": [], "rounded": [], "derived": []}
    seen = set()
    for m in NUM.finditer(written):
        tok = m.group()
        if tok in seen or ignorable(tok):
            continue
        seen.add(tok)
        how = match(tok, nums)
        if how == "exact":
            continue
        if how == "rounded":
            hits["rounded"].append(tok)
            continue
        if derived(tok, nums):
            hits["derived"].append(tok)
            continue
        hits["missing"].append(tok)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entries")
    ap.add_argument("--candidates", default=None,
                    help="the candidates JSON holding the abstracts; defaults "
                         "to the newest 'Batch Candidates from Post*.json' "
                         "beside the entries file")
    args = ap.parse_args()

    entries = json.load(io.open(args.entries, encoding="utf-8"))
    d = os.path.dirname(os.path.abspath(args.entries))
    cand_path = args.candidates
    if not cand_path:
        found = [f for f in os.listdir(d) if f.startswith("Batch Candidates")]
        if not found:
            raise SystemExit("no candidates file found; pass --candidates")
        cand_path = os.path.join(d, sorted(found)[-1])
    cands = json.load(io.open(cand_path, encoding="utf-8"))
    by_pmid = {c["pmid"]: c for c in cands["candidates"]}

    print(f"checking {len(entries)} entries against {os.path.basename(cand_path)}\n")
    bad = 0
    for i, e in enumerate(entries):
        pmid = e.get("pmid")
        src = by_pmid.get(pmid)
        if not src:
            print(f"  entry {i} ({e.get('slug')}): PMID {pmid} is not in the "
                  f"candidates file -- cannot verify")
            bad += 1
            continue
        h = check_entry(e, src)
        label = f"  {e.get('slug', '?')[:30]:<30} PMID {pmid}"
        if h["missing"]:
            print(f"{label}  MISSING {', '.join(h['missing'])}")
            bad += 1
        elif h["derived"] or h["rounded"]:
            notes = []
            if h["rounded"]:
                notes.append("rounded " + ", ".join(h["rounded"]))
            if h["derived"]:
                notes.append("derived " + ", ".join(h["derived"]))
            print(f"{label}  ok ({'; '.join(notes)})")
        else:
            print(f"{label}  ok")

    print()
    if bad:
        print(f"{bad} of {len(entries)} entries have a number that is not in "
              f"their paper. Fix or remove those before building.")
        return 1
    print(f"all {len(entries)} entries check out: every figure appears in the "
          f"abstract it cites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
