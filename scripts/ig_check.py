# -*- coding: utf-8 -*-
"""Check a Meta token before trusting a scheduled job to it.

Setting this up means creating an app, a system user, a token and two GitHub
secrets, and every one of those can be subtly wrong in a way that only shows
up as a failed post at nine in the morning. This answers the three questions
that actually matter, locally, before any of it is wired up:

  Does the token work, and is it the kind that does not expire?
  Which Instagram account does it reach -- and is it the right one?
  Does it carry the permissions publishing needs?

It also prints the Instagram user id, which is the other value the workflow
needs and is otherwise a two-step lookup through the Page.

Nothing is posted and nothing is written. Run it with the token in the
environment rather than on the command line, so it stays out of the shell
history:

  IG_ACCESS_TOKEN=... python scripts/ig_check.py        (bash)
  $env:IG_ACCESS_TOKEN="..."; python scripts/ig_check.py  (PowerShell)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("IG_API_BASE", "https://graph.facebook.com/v23.0")

# What publishing needs on the Facebook-Login route. ads_management and
# ads_read appear too when the user has a Business Manager role, which is
# normal and not a problem.
NEEDED = ["instagram_basic", "instagram_content_publish", "pages_read_engagement"]


def get(path, params, token):
    params = dict(params)
    params["access_token"] = token
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body)["error"]["message"]
        except Exception:  # noqa: BLE001
            msg = body
        return {"_error": msg, "_code": e.code}


def main():
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "Set IG_ACCESS_TOKEN first. Do not paste the token into a chat or "
            "a file -- it is a key to the account.")

    print(f"api: {API}\n")

    # debug_token tells you what a token IS, which is the thing nobody can
    # tell by looking at it. Crucially it reports expires_at: 0 means never,
    # which is the whole point of using a system user.
    info = get("debug_token", {"input_token": token}, token)
    if "_error" in info:
        raise SystemExit(f"token rejected: {info['_error']}")
    data = info.get("data", {})
    expires = data.get("expires_at", None)
    print("TOKEN")
    print(f"  type:      {data.get('type')}")
    print(f"  app:       {data.get('application')}")
    print(f"  valid:     {data.get('is_valid')}")
    if expires in (0, None):
        print("  expires:   never  <- correct for a scheduled job")
    else:
        import datetime
        when = datetime.datetime.fromtimestamp(expires, datetime.timezone.utc)
        days = (when - datetime.datetime.now(datetime.timezone.utc)).days
        print(f"  expires:   {when:%Y-%m-%d} ({days} days)")
        print("  WARNING: this token expires. When it does, posting stops with")
        print("           no error anyone sees. Use a System User token instead.")

    scopes = data.get("scopes", [])
    print(f"\nPERMISSIONS ({len(scopes)})")
    for p in NEEDED:
        print(f"  {'ok ' if p in scopes else 'MISSING'}  {p}")
    extra = [s for s in scopes if s not in NEEDED]
    if extra:
        print(f"  also: {', '.join(sorted(extra))}")

    # The Instagram user id is not something the token announces; it hangs off
    # the Page, which hangs off the token.
    print("\nACCOUNTS")
    pages = get("me/accounts", {"fields": "id,name"}, token)
    if "_error" in pages:
        print(f"  could not list Pages: {pages['_error']}")
        return 1
    found = False
    for page in pages.get("data", []):
        ig = get(page["id"],
                 {"fields": "instagram_business_account{id,username}"}, token)
        acct = ig.get("instagram_business_account") if "_error" not in ig else None
        if acct:
            found = True
            print(f"  Page '{page['name']}' -> Instagram @{acct.get('username')}")
            print(f"\n  IG_USER_ID = {acct['id']}")
        else:
            print(f"  Page '{page['name']}' -- no Instagram account attached")
    if not found:
        print("\n  No Instagram Business account found. The account must be a")
        print("  professional account connected to a Page, and the system user")
        print("  must have been granted access to that Page as an asset.")
        return 1

    missing = [p for p in NEEDED if p not in scopes]
    print("\n" + ("Ready." if not missing else
                  "Not ready -- missing: " + ", ".join(missing)))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
