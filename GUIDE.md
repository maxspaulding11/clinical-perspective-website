# How to Use Your Website — Plain English Guide

No coding experience needed. This covers everything: viewing the site, putting
it online, adding new posts, and changing things later.

---

## 1. What's in this folder (and what you can ignore)

Your website lives in this folder (`Desktop\CP`). Only **one file matters**
for day-to-day use:

| File | What it is | Do you touch it? |
|---|---|---|
| `scripts\studies-source.json` | The master list of every study you've covered | **Yes — every time you post** |
| `research.html` | The full research archive page | No — it's generated |
| `studies\` | One page per study (45 of them) | No — they're generated |
| `data\posts.json` | Feeds the homepage "Latest Research" | No — it's generated |
| `index.html` | The homepage | No |
| `css\style.css` | Colors and fonts | No |
| `js\main.js` | Makes the site work | Only to change your email |
| `js\analytics-config.js` | Turns on visitor stats | Once, in section 9 |
| `js\spare-change-config.js` | Points the Reader Queue at Spare Change | Only once you buy a custom domain (section 6) |
| `assets\logo.jpg` | Your CP logo | No |

> **Important:** anything marked *generated* is rebuilt from
> `scripts\studies-source.json`. If you edit those files by hand, your changes
> get wiped the next time the site is rebuilt. Always edit the source file.

---

## 2. Put your website online (one-time setup, ~10 minutes)

We'll use **Netlify** — it's free and doesn't require any coding.

1. Go to **https://app.netlify.com/signup** in your browser.
2. Sign up with your email (free — no credit card).
3. Once logged in, go to **https://app.netlify.com/drop**.
4. Open File Explorer, find your `CP` folder on your Desktop.
5. **Drag the whole CP folder** onto the Netlify page where it says
   "Drag and drop your site output folder here."
6. Wait about 30 seconds. Netlify gives you a link like
   `https://random-name-12345.netlify.app` — **that's your live website.**
7. To make the link nicer: in Netlify, click **Site configuration →
   Change site name** and pick something like `theclinicalperspective`
   → your site becomes `https://theclinicalperspective.netlify.app`.
8. Copy that link and paste it into your **Instagram bio**
   (Edit profile → Website).

> Want a custom address like `theclinicalperspective.com`? You can buy one
> later (~$12/year) through Netlify: **Domain management → Add a domain**.
> Everything else stays the same.

---

## 3. Add a new study to the site (do this each time you post on Instagram)

Every study now gets its **own page** on your site with the full summary on
it — that's what Google can find and index. All of those pages are built
automatically from one file, so you only ever edit that one file.

**The easy way: ask Claude Code.** Say *"add this study to the site"* and
paste your summary + citation. It'll add the entry and rebuild everything.

**The manual way:**

1. Open `CP\scripts\studies-source.json` in Notepad.
2. Copy an existing entry (from `{` to `}`) and paste it at the end of the
   list, just before the final `]`. Add a **comma** after the `}` above it.
3. Fill in your new study:

   ```
   {
     "index": 46,
     "date": "2026-08-26",
     "title": "Does EMDR really work?",
     "tag": "Myth Check",
     "blurb": "One sentence teaser — this shows on the homepage and in Google results.",
     "summary": "Your full lay summary paragraph goes here.",
     "journal": "Cureus",
     "authors": "Peji et al.",
     "pubdate": "June 2026",
     "pmid": "42483107",
     "doi": "10.7759/cureus.111244",
     "url": null,
     "instagram": ""
   }
   ```

   - `pmid`, `doi`, and `url` — fill in whichever you have, put `null` for
     the rest. The "Read the original study" button uses the DOI first, then
     the PMID, then the URL.
   - `instagram` — optional. Paste the post's Instagram link
     (`https://www.instagram.com/p/ABC123xyz/`) and the homepage card will
     embed the actual post. Leave it as `""` if you'd rather not.
   - `tag` — reuse an existing one where you can (they become the filter
     buttons on the archive page).

4. **Save** (Ctrl+S) and close Notepad.
5. Rebuild the site — open the `CP` folder, type `cmd` in the address bar,
   press Enter, then run:

   ```
   python scripts\build.py
   ```

   You should see `46 study pages written`.

⚠️ The two mistakes that break it (if the build fails or the page goes
blank, it's one of these):
- A missing **comma** between entries
- A missing **quote mark** around any of the text

Newest always shows first — you never need to reorder anything.

**Scheduling ahead is fine.** `studies-source.json` holds your whole
schedule, including studies you haven't posted yet. A study with a future
`date` is **not** published — no page, not on the homepage, not in the
archive, not in the sitemap. It's released automatically the first time you
run the build on or after its date. So the build output normally looks like:

```
Published 22 studies (through 2026-08-02).
Holding back 23 scheduled studies dated after 2026-08-02.
  Next up: 2026-08-03 — Schizophrenia genetics beyond European ancestry
```

That's why the count on the site is lower than the number of entries in the
file — the rest are queued, not missing. Since you re-upload after each
Instagram post anyway, each day's study goes live right on schedule.

**Step C — update the live website:**
1. Log in to **netlify.com** and click your site.
2. Click the **Deploys** tab.
3. Drag your whole `CP` folder onto the page again (same as before).
4. Done — the live site updates in about 30 seconds.

That's the whole routine: *post on Instagram → add the entry → run the
build → drag folder to Netlify.*

---

## 4. When someone wants to submit research to you

Nothing for you to do — it's automatic:
- **"Email a Submission"** opens an email addressed to you
  (theclinicalperspective@gmail.com) with a pre-filled template.
- **"Message on Instagram"** opens a DM to @the_clinical_perspective.

Submissions just arrive in your inbox / DMs like normal messages.

---

## 5. Common changes

**Change the contact email:** open `js\main.js` in Notepad, find the line
near the top that says `const CONTACT_EMAIL = "..."` and change the address
between the quotes. Save, then re-upload to Netlify (Step 3C).

**Remove or correct a study:** open `scripts\studies-source.json`, edit or
delete that study's entry (from its `{` to its `}`, including the comma that
separated it from its neighbor), then run `python scripts\build.py` and
re-upload. Don't edit files in `studies\` or `data\` directly — they get
overwritten by the build.

**Issue a correction:** your editorial policy is that corrections are public,
not quietly edited. Add a line at the end of that study's `summary` such as
*"Correction (Sept 3, 2026): an earlier version said X; the study actually
found Y."* Then rebuild and re-upload.

**Change any wording on the page:** tell Claude (that's me) what to change —
or open `index.html` in Notepad and carefully edit the text you see between
the tags. Save, re-upload.

**Something looks broken:** don't panic — nothing on the live site changes
until you upload to Netlify. Undo your edit (Ctrl+Z in Notepad), save, and
try again. Or come back to Claude Code and ask me to fix it.

---

## 6. Connecting the Reader Queue to Spare Change (one-time, once you have a domain)

The "Reader Queue" panel lets visitors suggest studies (by DOI or link) and
upvote each other's suggestions. Submitting or voting now requires signing
in with Google — the same account works here and on Spare Change (your other
site), so it's one login for both.

That sign-in only works once both sites live under one custom domain (e.g.
`www.yourdomain.com` for this site and `spare.yourdomain.com` for Spare
Change) — browsers won't share a login between two free `.netlify.app` /
`.vercel.app` addresses. Until you buy a domain, the Reader Queue shows a
local-only preview instead (same as before — nothing is broken in the
meantime).

**Once you've bought a domain and pointed both sites at it:**
1. On your computer, open `CP → js → spare-change-config.js` in Notepad.
2. Replace the `http://localhost:3000` value with your Spare Change
   subdomain, e.g. `window.SPARE_CHANGE_ORIGIN = "https://spare.yourdomain.com";`
3. Save the file and re-upload the folder to Netlify (section 3, Step C).

Ask Claude Code to walk you through the domain/DNS setup itself when you're
ready to buy one — it's a short one-time step on both the domain registrar's
site and Spare Change's Vercel dashboard.

**Removing spam or junk suggestions:** ask Claude Code to remove a specific
suggestion from Spare Change's database, or delete it directly from the
database's dashboard (Neon/Vercel Postgres). Only you have access to that.

---

## 7. Setting up the weekly newsletter (one-time, ~15 minutes)

The site has a hidden "Weekly Digest" signup section. It appears
automatically once you connect your free MailerLite account.

**Part 1 — create the account:**
1. Go to **https://www.mailerlite.com** and click **Sign up free**
   (free up to 1,000 subscribers).
2. Sign up with your email. They'll ask a few questions about your
   "business" — answer honestly (content creator / education is fine).
   They may take up to a day to approve new accounts; that's normal.

**Part 2 — create the signup form:**
1. In MailerLite, click **Forms** in the left menu → **Embedded forms** →
   **Create embedded form**. Name it `Website signup`.
2. Design doesn't matter (your website has its own design) — click
   through to the final step, which shows you code.
3. On the code screen, look for the **HTML** code and find the line that
   contains `action="https://assets.mailerlite.com/jsonp/...`
4. Copy just that URL — everything between the quotes after `action=`.
   It ends in `/subscribe`.

**Part 3 — connect it to your website:**
1. Open `CP → js → newsletter-config.js` in Notepad.
2. Replace `PASTE_YOUR_MAILERLITE_URL_HERE` with the URL you copied
   (keep the quote marks).
3. Save, then re-upload the folder to Netlify (section 3, Step C).

The navy "Weekly Digest" section now appears on the site between About
and Submit Research, with a Newsletter link in the menu.

**Sending your weekly email:**
1. In MailerLite, click **Campaigns → Create campaign**.
2. Give it a subject like "This Week in Clinical Research — Jan 12".
3. Use the drag-and-drop editor: paste in the studies you covered,
   what's leading the Reader Queue, and a link to your site + Instagram.
4. Click **Send** (or schedule it for the same time each week —
   consistency is what builds the habit for readers).

New subscribers get a confirmation email automatically (this "double
opt-in" is a good thing — it keeps your list clean and legal).

---

## 8. Viewing the site on your own computer (optional)

The site needs a small local "server" to preview before uploading — opening
`index.html` by double-clicking won't load the Instagram embeds. The easiest
way to preview: ask Claude Code to "start the preview" — or just upload to
Netlify and check the live link, since uploads are instant and unlimited.

---

## 9. Seeing who visits your site (one-time, ~5 minutes)

Right now you have no idea how many people read the site or which studies
they open. This turns that on, using **Cloudflare Web Analytics** — it's
free, it doesn't use cookies, and it doesn't track people across other
sites, so it needs no cookie banner.

**Part 1 — get your token:**
1. Go to **https://dash.cloudflare.com/sign-up** and make a free account
   (no credit card).
2. In the left menu, click **Analytics & Logs → Web Analytics**.
3. Click **Add a site**, and enter your site's address — your Netlify link
   (e.g. `theclinicalperspective.netlify.app`) or your custom domain.
4. Cloudflare shows you a snippet of code. Inside it you'll see
   `token: "abc123..."`. **Copy just that long token string** (the part
   between the quotes).

**Part 2 — connect it:**
1. Open `CP\js\analytics-config.js` in Notepad.
2. Replace `PASTE_YOUR_CLOUDFLARE_TOKEN_HERE` with your token
   (keep the quote marks).
3. Save, then re-upload the folder to Netlify (section 3, Step C).

Within a few minutes, the Cloudflare dashboard starts showing page views,
which pages are most read, and where visitors came from (e.g. Instagram).

Until you paste a real token, analytics stay completely off — nothing loads
and nothing is sent. Visits from your own computer while previewing locally
are never counted.

> **Note:** your Disclaimer & Privacy page already tells visitors the site
> uses Cloudflare Web Analytics. If you decide *not* to turn this on, ask
> Claude Code to remove that paragraph so the page stays accurate.

---

## 10. Why each study has its own page

Every study you cover gets a real page at `yoursite.com/studies/<name>.html`
with the whole summary written out as text, plus the journal, authors, and a
link to the original paper.

This matters because Instagram embeds are invisible to Google — search
engines can't read inside them. With real pages, someone searching *"does
EMDR really work"* can actually land on your summary. Each new study you add
becomes another door into the site.

The archive at `research.html` lists all of them, with filter buttons by
topic, and `sitemap.xml` (the file that tells Google what exists) is
rebuilt automatically every time you run the build.
