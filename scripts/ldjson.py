# -*- coding: utf-8 -*-
"""Serialise JSON-LD for embedding inside a <script> tag.

json.dumps does not escape "<". That is correct JSON and wrong HTML: the
browser ends a <script> block at the first literal "</script>" in the byte
stream, whether or not it sits inside a JSON string. So a value containing
"</script>" closes the block early and everything after it is parsed as
markup -- stored XSS, written by whoever supplied that value.

Nothing in this site can reach that today. Every value embedded as JSON-LD
is author-written except the citation line on a study page, which is built
from a DOI that find_studies.py takes from PubMed and Crossref unattended. A
DOI almost certainly cannot carry "</script>" through either service, which
is why this was a hardening note in the October 2026 security review rather
than a finding.

It is still the one sink where a change of data source turns into stored XSS
with nothing else having to go wrong, and the fix costs a string replace.
Escaping "<" is enough on its own: "\\u003c" is a valid JSON escape, it
survives JSON.parse unchanged, and no "<" can appear in JSON's own
punctuation, so replacing every one of them only ever touches string
contents.
"""
import json

__all__ = ["dumps"]


def dumps(obj, indent=2):
    """json.dumps, safe to drop between <script> and </script>."""
    return json.dumps(obj, indent=indent, ensure_ascii=False).replace("<", "\\u003c")
