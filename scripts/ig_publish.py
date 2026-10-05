# -*- coding: utf-8 -*-
"""Publish the day's Reel to Instagram, via Meta's Content Publishing API.

Runs from .github/workflows/post-reel.yml, once a day, on GitHub's machines
rather than anybody's laptop. That is the whole reason this exists: Meta's
API has no scheduling. There is no scheduled_publish_time for Instagram the
way there is for a Facebook Page -- /media_publish posts the moment it is
called -- so something has to be awake at the posting time, and it cannot be
a desktop that might be shut.

Publishing is two calls and a wait:

  1. POST /<ig-user-id>/media with the video and cover URLs. This returns a
     container id immediately but does NOT mean Instagram has the video yet;
     it goes and fetches both URLs itself, which is why they have to be
     public. A URL behind a login, a localhost address or a file path all
     fail here.
  2. Poll GET /<container-id>?fields=status_code until it reads FINISHED.
     A reel takes tens of seconds. ERROR is terminal and carries a reason.
  3. POST /<ig-user-id>/media_publish with the container id.

The cover is passed as cover_url, which takes precedence over thumb_offset
and is the only way to keep the pipeline's own cover art. Without it
Instagram picks a frame, and the profile grid stops being a checkerboard and
starts being 87 arbitrary video stills.

Nothing is posted unless --live is passed. The default is a dry run that
does everything except the two POSTs, so the manifest, the URLs and the
caption can all be checked against a real account without anything going out.
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
MANIFEST = os.path.join(SITE, "data", "reels.json")

# graph.facebook.com, not graph.instagram.com. There are two Instagram APIs
# and they are not interchangeable: graph.instagram.com serves "Instagram API
# with Instagram Login", for accounts that stand alone. This account is
# managed through Meta Business Suite, which means it is a professional
# account connected to a Facebook Page -- the "Instagram API with Facebook
# Login" route, which lives on graph.facebook.com and wants instagram_basic,
# instagram_content_publish and pages_read_engagement.
#
# Getting this wrong does not fail obviously. The wrong host answers, and
# returns an authorisation error that reads like a bad token.
API = os.environ.get("IG_API_BASE", "https://graph.facebook.com/v23.0")

# A reel of this size finishes in well under a minute, but Instagram's own
# docs decline to promise a time, so this waits generously and gives up
# rather than hanging a workflow run forever.
POLL_SECONDS = 5
POLL_MAX = 60  # five minutes


def api(path, params=None, post=False, token=None):
    params = dict(params or {})
    params["access_token"] = token
    url = f"{API}/{path}"
    if post:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")
    else:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        # Meta puts the useful part in the body, not the status line. Printing
        # the status alone turns every failure into "HTTP Error 400: Bad
        # Request", which says nothing about which field was wrong.
        raise SystemExit(f"Instagram API error {e.code} on {path}:\n{body}")


def reachable(url):
    """Check a URL the way Instagram will: an unauthenticated fetch.

    Worth doing before creating a container, because a 404 here produces a
    container that fails minutes later with a generic error, and the actual
    cause -- a file that was never pushed, or pushed but not yet deployed --
    is much easier to see now."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Length")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001 - DNS, TLS, timeouts all mean "no"
        return str(e), None


def entry_for(day, manifest):
    for e in manifest["posts"]:
        if e["day"] == day:
            return e
    return None


def publish(entry, token, ig_user_id, wait=True):
    print(f"  creating container for {entry['postId']}")
    container = api(f"{ig_user_id}/media", {
        "media_type": "REELS",
        "video_url": entry["videoUrl"],
        "cover_url": entry["coverUrl"],
        "caption": entry["caption"],
    }, post=True, token=token)
    cid = container["id"]
    print(f"  container {cid}")

    if wait:
        for attempt in range(POLL_MAX):
            status = api(cid, {"fields": "status_code,status"}, token=token)
            code = status.get("status_code")
            if code == "FINISHED":
                print(f"  ready after {attempt * POLL_SECONDS}s")
                break
            if code == "ERROR":
                raise SystemExit(f"  container failed: {status.get('status')}")
            time.sleep(POLL_SECONDS)
        else:
            raise SystemExit("  container never finished -- not publishing")

    published = api(f"{ig_user_id}/media_publish",
                    {"creation_id": cid}, post=True, token=token)
    return published.get("id")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="YYYY-MM-DD (default: today, US Eastern)")
    ap.add_argument("--live", action="store_true",
                    help="actually post. Without this, nothing is sent.")
    args = ap.parse_args()

    token = os.environ.get("IG_ACCESS_TOKEN")
    ig_user_id = os.environ.get("IG_USER_ID")

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    # The site's readers and its posting schedule are both American, and a
    # workflow running in UTC would post the 1st of the month on the 30th.
    day = args.day or (datetime.datetime.now(datetime.timezone.utc)
                       - datetime.timedelta(hours=5)).date().isoformat()

    entry = entry_for(day, manifest)
    if not entry:
        # Not an error. Batches run out, and a quiet exit is the right
        # behaviour for a cron that fires every day whether or not there is
        # something queued.
        print(f"nothing queued for {day} -- "
              f"manifest covers {manifest['posts'][0]['day']} to "
              f"{manifest['posts'][-1]['day']}")
        return 0

    print(f"{day}: {entry['postId']}")
    for field in ("videoUrl", "coverUrl"):
        status, size = reachable(entry[field])
        mb = f", {int(size) / 1048576:.1f} MB" if size else ""
        print(f"  {field}: {status}{mb}")
        if status != 200:
            raise SystemExit(f"  {field} is not publicly reachable -- "
                             f"has the site deployed since the push?")
    print(f"  caption: {len(entry['caption'])} characters")

    if not args.live:
        print("\nDRY RUN -- nothing was posted. Re-run with --live to post.")
        return 0

    if not token or not ig_user_id:
        raise SystemExit("IG_ACCESS_TOKEN and IG_USER_ID must be set to post")

    media_id = publish(entry, token, ig_user_id)
    print(f"  published: {media_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
