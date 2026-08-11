# Managing The Clinical Perspective — Complete Guide

No coding experience needed for the day-to-day sections. The parts that
genuinely require Claude Code's help say so explicitly — for those, just
open a session and describe what you want in plain English.

**Last reviewed:** 2026-08-09.

---

## 0. The big picture — what you actually have

Two separate projects, connected by one shared login:

| | What it is | Where it lives | Where it's hosted |
|---|---|---|---|
| **The Clinical Perspective** | The public content site — studies, About, Tools, legal pages | `Desktop\The Clinical Perspective\Website` | Netlify, deployed by dragging this folder onto the Netlify Deploys page |
| **Spare Change** | A separate Next.js app with real user accounts (Google sign-in) that also powers the Reader Queue's shared login | `Desktop\The Clinical Perspective\spare-change` | Vercel, deployed from the CLI (no GitHub repo) |

They talk to each other over the network (the Website calls Spare Change's
API for sign-in and the Reader Queue), but they are edited, tested, and
deployed completely separately. Nothing you do to one automatically touches
the other.

**Confirmed manually (2026-08-09):** this site is on Netlify's manual
deploy model, not continuous deployment. There **is** a real git repo with a
GitHub remote, and Claude Code can commit and push to it — but pushing to
GitHub by itself does **not** update the live site. GitHub is being used
here purely as version history, not as Netlify's deploy source. **Every
change still needs the drag-and-drop step in Section 2 to actually go
live**, even after a successful git push. This is the opposite of what an
earlier version of this guide assumed — if anything here ever seems to
contradict what actually happens when you deploy, trust what you observe
and tell Claude Code, since this can drift out of date again.

---

## PART A — The Clinical Perspective (the main site)

## 1. What's in this folder (and what you can ignore)

| File / folder | What it is | Do you touch it? |
|---|---|---|
| `scripts\studies-source.json` | The master list of every study you've covered | **Yes — every time you post** |
| `scripts\build.py` | Regenerates the site from that file | Run it, don't edit it |
| `research.html`, `studies\`, `data\posts.json`, `data\studies.json`, `sitemap.xml` | Generated from `studies-source.json` | No — rebuilt automatically, edits get wiped |
| `data\programs.json` | The "who's accepting doctoral students" data | No — see Part A, Section 4 |
| `tools\` | The Citation Generator, PhD guide, and faculty directory pages | No, unless asking Claude to change wording |
| `index.html`, `about.html`, `legal.html`, etc. | The main pages | Only with Claude's help, or careful manual HTML edits |
| `css\style.css` | Colors and fonts | No |
| `js\main.js` | Site behavior | Only to change your contact email |
| `js\analytics-config.js` | Cloudflare visitor stats — already turned on | No, unless the token needs replacing |
| `js\spare-change-config.js` | Points the Reader Queue at Spare Change | Only when the Spare Change URL changes |
| `assets\logo.png` | Your logo | No |

> **Rule of thumb:** if a file is described as "generated" anywhere in this
> guide, never hand-edit it. Edit the source file and rebuild instead.

---

## 2. Deploying changes — two separate steps, both required

There are genuinely two different systems here, and doing only one of them
leaves the live site unchanged. This is easy to miss because git makes it
*feel* like something happened.

**Step 1 — git (version history only, does NOT go live):**
1. Changes are made to files in this folder.
2. `git add` stages them, `git commit` saves a labeled checkpoint, and
   `git push origin main` sends that history to GitHub.
3. This is useful — it's a real backup and changelog of everything ever
   done to the site — but **GitHub is not connected to Netlify's deploy
   process here**. Pushing does nothing to the live site by itself.

**Step 2 — the actual deploy, done by hand every time:**
1. Log into **app.netlify.com** and open your site.
2. Click the **Deploys** tab.
3. Open File Explorer to `Desktop\The Clinical Perspective\Website`.
4. **Drag the whole `Website` folder** onto the Netlify page, where it says
   to drop your site's folder.
5. Wait about 30 seconds — Netlify shows the new deploy as "Published."

**To check the live result:** visit **theclinicalperspective.org** directly.

**The practical rule:** whenever Claude Code says a change is "committed" or
"pushed," that only means Step 1 happened. Nothing is actually live until
someone does Step 2. Claude Code cannot do Step 2 itself — it requires your
own logged-in Netlify session and an OS-level drag-and-drop, neither of
which Claude Code can perform. Always do the drag-and-drop after any commit
you want to see on the real site.

**Worth considering:** Netlify can link directly to your GitHub repo so that
`git push` alone triggers a real deploy, permanently removing Step 2. That's
a one-time change in **Site configuration → Build & deploy → Link repository**
on Netlify's side — ask Claude Code if you'd like help thinking through it,
since it would make the git-based workflow actually match what this guide
described before this correction. Not urgent, just worth knowing it's an
option.

If you ever want to make a small wording change yourself without asking
Claude: edit the file in Notepad, save it, then drag the `Website` folder
onto Netlify's Deploys page (Section 2, Step 2) — that's the part that
actually matters for the live site. Committing to git is good practice but
optional for a quick manual edit like this.

---

## 3. Add a new study (do this each time you post on Instagram)

Every study gets its own real page — that's what Google indexes; Instagram
embeds alone are invisible to search engines.

**The easy way: ask Claude Code.** Say *"add this study to the site and
deploy it"* and paste your summary + citation.

**The manual way:**

1. Open `scripts\studies-source.json` in Notepad.
2. Copy an existing entry (`{` to `}`) and paste it before the final `]`.
   Add a comma after the entry above it.
3. Fill in the new study:

   ```
   {
     "index": 46,
     "date": "2026-08-26",
     "title": "Does EMDR really work?",
     "tag": "Myth Check",
     "blurb": "One sentence teaser for the homepage and Google results.",
     "summary": "Your full lay summary paragraph.",
     "journal": "Cureus",
     "authors": "Peji et al.",
     "pubdate": "June 2026",
     "pmid": "42483107",
     "doi": "10.7759/cureus.111244",
     "url": null,
     "instagram": ""
   }
   ```

   - Fill in whichever of `pmid` / `doi` / `url` you have; `null` for the rest.
   - `instagram` is optional — paste the post link to embed it on the homepage card.
   - Reuse an existing `tag` where possible (they become the archive filter buttons).

4. Save and close.
5. Open a terminal in this folder and run:
   ```
   python scripts\build.py
   ```
   You should see `N study pages written`.
6. Drag the `Website` folder onto Netlify's Deploys page (Section 2) to
   actually publish it. Commit and push to git too if you want it in your
   version history, but that step alone won't make it live.

⚠️ The two mistakes that break the build: a missing **comma** between
entries, or a missing **quote mark**.

**Scheduling ahead is fine.** A study dated in the future stays hidden
everywhere (no page, no homepage card, not in the sitemap) until you run the
build on or after its date — so you can queue up weeks of content at once
and it releases itself on schedule as you post.

---

## 4. The Tools section (`/tools/`)

Three tools live here, linked from the nav as **Tools**:

**Citation Generator** (`tools/citations.html`) — paste a DOI, PubMed ID, or
ISBN and it produces a correct APA 7 reference, both in-text forms, and a
downloadable Word reference page. Nothing to maintain; the underlying logic
is in `js/apa.js` and `js/citations.js`.

**Applying to Clinical Psychology PhD Programs** (`tools/applying-to-clinical-psychology-phd-programs.html`)
— a static how-to guide. Update it the same way as any other page: ask
Claude Code, or edit the HTML directly.

**Who's Accepting Doctoral Students** (`tools/faculty-accepting-students.html`)
— a directory of which clinical psychology faculty are accepting doctoral
students, sourced from ~253 APA-accredited programs' own admissions pages.
The data lives in `data/programs.json`.

**This one needs periodic re-checking, and it needs Claude Code's help to do
it properly** — the whole point of this tool is that every name is read
directly from a program's own page (never from search results, which were
tested and found to be wrong or incomplete on every program checked). That
verification process can't be done by hand at this scale. To refresh it:

- Say *"re-check the schools marked pending in the faculty-accepting-students
  data"* — most useful **August through October**, since that's when
  programs actually post their Fall admissions lists. A school currently
  showing "pending" or "no page found" isn't necessarily wrong — it may
  simply not have posted yet.
- If you spot a specific school that's outdated or wrong, tell Claude Code
  which one and it'll re-verify just that program.

---

## 5. Seeing who visits your site

**Already turned on** — Cloudflare Web Analytics, free, no cookies, no
cookie banner needed. It went live with the deployment described in Section
2, so numbers only start counting from that point forward (no history from
before).

**To check it:** go to **dash.cloudflare.com**, log in, then
**Analytics & Logs → Web Analytics**. You'll see page views, which pages get
read most, and where visitors came from (e.g. a spike right after an
Instagram post pointing to it).

If you're not sure whether you already have a Cloudflare account: try
logging in with whatever email you'd use for this project. If an account
exists, "Forgot password" will find it and let you reset it.

---

## 6. Setting up the weekly newsletter (one-time)

The site has a hidden "Weekly Digest" section that appears automatically
once MailerLite is connected.

1. Sign up free at **mailerlite.com** (free up to 1,000 subscribers).
2. **Forms → Embedded forms → Create embedded form.** Design doesn't matter
   — click through to the code screen and find the URL inside
   `action="https://assets.mailerlite.com/jsonp/..."` (ends in `/subscribe`).
3. Paste that URL into `js\newsletter-config.js`, replacing the placeholder.
4. Drag the `Website` folder onto Netlify's Deploys page (Section 2, Step 2) to
   actually publish it. Committing and pushing to git is optional and doesn't
   put it live by itself.

**Sending an issue:** MailerLite → **Campaigns → Create campaign**. Paste in
the week's studies, what's leading the Reader Queue, and links to the site
and Instagram. Sending consistently on the same day each week is what builds
the reading habit.

---

## 7. Legal, redirects, and things that stay hidden on purpose

- **`_redirects`** handles two things: the old `netlify.app` address
  forwarding to the real domain, and blocking `/scripts/*` from ever being
  served publicly (the build script and study-source file aren't meant to be
  visible to visitors).
- **`robots.txt`** and **`sitemap.xml`** tell Google what to index —
  `sitemap.xml` regenerates automatically every time you run `build.py`.
- **Every Tools page carries structured data** (invisible to visitors, read
  by Google) describing what each page actually is — this is what makes
  the citation tool and faculty directory eligible to show up richly in
  search results rather than as a plain blue link.

None of this needs regular attention — it's here so you know it exists and
why, in case something looks unusually quiet in analytics or search results.

---

## PART B — Spare Change & shared accounts

## 8. What Spare Change is, and how it connects here

Spare Change is a separate app with real user accounts (Google sign-in),
built on Next.js + a Postgres database (hosted on **Neon**) + Prisma. It's
the identity provider for this site's Reader Queue — when someone signs in
to suggest or vote on a study here, they're actually signing into Spare
Change, and the two sites share that login via a cookie that works across
both domains.

**You never edit Spare Change's code to manage the Website**, but you will
occasionally want to look at its data — who's signed up, streaks, queue
suggestions.

## 9. Looking at user accounts, streaks, and submissions

The database has no built-in dashboard, but Prisma (already installed)
ships with a free visual browser called **Prisma Studio** that needs no
setup beyond what already exists.

**To open it:**
1. Open a terminal in `Desktop\The Clinical Perspective\spare-change`.
2. Run:
   ```
   npx prisma studio
   ```
3. Open **http://localhost:5555** in your own browser.
4. Click any table on the left — **User** shows every account (name, email,
   when they joined, current streak, best streak); **Suggestion** and
   **Vote** show Reader Queue activity.

This only runs on your own computer (`localhost`) — it is never reachable
from the internet, which is deliberate: Prisma Studio has no password
protection of its own, so anyone who could reach it would have full access
to every user's data. Keep it local-only.

**Removing spam or bad suggestions:** open Prisma Studio, click
**Suggestion**, find the row, and delete it directly — or ask Claude Code to
do it for you.

**Note on account dates:** `createdAt` was added to the User table on
2026-08-09. Accounts created before that date all show that same date,
since there's no way to recover when they actually signed up — but every
account created from now on will show its real join date.

## 10. Deploying changes to Spare Change

This project has **no GitHub repository** — it deploys straight from this
computer to Vercel via the command line. Ask Claude Code to deploy it when
something changes; the short version of what happens is `vercel --prod` run
from inside the `spare-change` folder. Database schema changes (like the one
in Section 9) apply directly to the live Neon database the moment they're
run — they don't wait for a separate deploy step.

## 11. Domain and DNS

You own **theclinicalperspective.org**. The matching `.com` is owned by a
third party; a broker-assisted purchase path exists for later if you want
it, but isn't urgent. Ask Claude Code for the current status if you're
picking this back up — it changes infrequently enough that it's not worth
duplicating here.

---

## 12. The recurring checklist

The only things worth doing on a schedule, roughly in order of how often:

| How often | What | How |
|---|---|---|
| Each time you post on Instagram | Add the study to the site | Section 3 |
| Weekly (if running it) | Send the newsletter | Section 6 |
| Occasionally | Check traffic | Section 5 |
| **August–October** | Re-check pending schools in the faculty directory | Section 4 — ask Claude Code |
| As needed | Remove spam Reader Queue suggestions | Section 9 |
| As needed | Check who's signed up / streak activity | Section 9 |

Everything else in this guide is one-time setup or reference material for
when something needs fixing.

---

## 13. When something looks broken

Nothing on the live site changes until a deploy actually happens (Section
2) — so if you're mid-edit and something looks wrong locally, nothing is
at risk yet. If the *live* site is broken:

1. Check **Netlify → Deploys** for a failed build and read the error.
2. Come back to Claude Code, describe what's wrong (or paste the error),
   and ask for a fix.
3. Once fixed, drag the `Website` folder onto Netlify's Deploys page again
   (Section 2, Step 2) to publish the fix. There is no auto-deploy — every
   fix requires that manual drag-and-drop.

Git history means nothing is ever truly lost — even a bad deploy can be
rolled back to the previous working commit if needed. Ask Claude Code if
that's ever necessary; it's not a routine operation.
