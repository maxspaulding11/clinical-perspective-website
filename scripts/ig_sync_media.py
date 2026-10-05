# -*- coding: utf-8 -*-
"""Push a batch's Reel media to the repo that serves it.

Separate from this site's repo on purpose. A batch is about 33MB and this
repo's whole history is 6MB, so keeping the media here would grow it by
roughly 560MB a year, permanently. In its own repo the same files can be
deleted outright once they have posted -- or the repo emptied and started
again -- and nothing the site depends on notices.

Expects the media repo cloned beside this one:

    ../tcp-reel-media

Run after scripts/ig_manifest.py, before the first post of a batch. The
publisher checks both URLs return 200 before it creates anything, so a batch
that was never synced fails loudly on the day rather than posting a Reel with
no video.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
STAGED = os.path.join(SITE, "media", "reels")
REPO = os.path.abspath(os.path.join(SITE, os.pardir, "tcp-reel-media"))


def run(args, cwd):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="delete media already in the repo before copying, so "
                         "a finished batch does not accumulate")
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(REPO, ".git")):
        raise SystemExit(
            f"no media repo at {REPO}\n"
            "Clone it there first:\n"
            "  git clone https://github.com/maxspaulding11/tcp-reel-media.git")
    if not os.path.isdir(STAGED) or not os.listdir(STAGED):
        raise SystemExit(f"nothing staged in {STAGED} -- run ig_manifest.py first")

    dest = os.path.join(REPO, "media", "reels")
    if args.prune and os.path.isdir(dest):
        for name in os.listdir(dest):
            os.remove(os.path.join(dest, name))
    os.makedirs(dest, exist_ok=True)

    copied = 0
    for name in sorted(os.listdir(STAGED)):
        shutil.copy2(os.path.join(STAGED, name), os.path.join(dest, name))
        copied += 1

    run(["git", "add", "-A"], REPO)
    if not run(["git", "status", "--porcelain"], REPO):
        print("media repo already up to date")
        return 0
    run(["git", "commit", "-m", f"Add {copied} Reel media files"], REPO)
    run(["git", "push"], REPO)

    size = sum(os.path.getsize(os.path.join(dest, n))
               for n in os.listdir(dest)) / 1048576
    print(f"pushed {copied} files ({size:.0f} MB) to tcp-reel-media")
    print("GitHub Pages usually serves them within a minute.")
    print("Check before posting:  python scripts/ig_publish.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
