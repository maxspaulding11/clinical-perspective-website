# How to Use Your Website — Plain English Guide

No coding experience needed. This covers everything: viewing the site, putting
it online, adding new posts, and changing things later.

---

## 1. What's in this folder (and what you can ignore)

Your website lives in this folder (`Desktop\CP`). Only **one file matters**
for day-to-day use:

| File | What it is | Do you touch it? |
|---|---|---|
| `data\posts.json` | The list of posts shown on your site | **Yes — every time you post** |
| `index.html` | The page itself | No |
| `css\style.css` | Colors and fonts | No |
| `js\main.js` | Makes the site work | Only to change your email |
| `js\firebase-config.js` | Connects the Reader Queue database | Once, during setup (section 6) |
| `assets\logo.jpg` | Your CP logo | No |

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

## 3. Add a new post to the site (do this each time you post on Instagram)

**Step A — copy your post's link from Instagram:**
1. Open your new post on Instagram.
2. Tap the **···** (three dots) in the corner of the post.
3. Tap **Copy link**. You now have something like
   `https://www.instagram.com/p/ABC123xyz/`

**Step B — add it to your website's list:**
1. On your computer, open the `CP` folder, then the `data` folder.
2. Right-click `posts.json` → **Open with → Notepad**.
3. You'll see entries that look like this:

   ```
   {
     "url": "https://www.instagram.com/p/ABC123xyz/",
     "tag": "Cardiology",
     "title": "New anticoagulant trial shows reduced stroke risk",
     "date": "2026-07-10",
     "blurb": "One sentence on the finding and why it matters."
   }
   ```

4. Copy an existing entry (from `{` to `}`), paste it **at the end of the
   list, just before the final `]`**, and add a **comma** after the `}` of
   the entry above it.
5. Fill in your new post's link, a category tag, a title, today's date
   (format: `2026-07-15`), and a one-sentence blurb.
6. **Save the file** (Ctrl+S) and close Notepad.

⚠️ The two mistakes that break the page (if the Research section goes blank,
it's one of these):
- A missing **comma** between entries
- A missing **quote mark** around any of the text

The newest post automatically shows first — you don't need to reorder anything.

**Step C — update the live website:**
1. Log in to **netlify.com** and click your site.
2. Click the **Deploys** tab.
3. Drag your whole `CP` folder onto the page again (same as before).
4. Done — the live site updates in about 30 seconds.

That's the whole routine: *post on Instagram → paste link into posts.json →
drag folder to Netlify.* About 2 minutes per post.

---

## 4. When someone wants to submit research to you

Nothing for you to do — it's automatic:
- **"Email a Submission"** opens an email addressed to you
  (maxspaulding33@yahoo.com) with a pre-filled template.
- **"Message on Instagram"** opens a DM to @the_clinical_perspective.

Submissions just arrive in your inbox / DMs like normal messages.

---

## 5. Common changes

**Change the contact email:** open `js\main.js` in Notepad, find the line
near the top that says `const CONTACT_EMAIL = "..."` and change the address
between the quotes. Save, then re-upload to Netlify (Step 3C).

**Remove a post from the site:** open `data\posts.json`, delete that post's
entry (from its `{` to its `}`, including the comma that separated it from
its neighbor). Save, re-upload.

**Change any wording on the page:** tell Claude (that's me) what to change —
or open `index.html` in Notepad and carefully edit the text you see between
the tags. Save, re-upload.

**Something looks broken:** don't panic — nothing on the live site changes
until you upload to Netlify. Undo your edit (Ctrl+Z in Notepad), save, and
try again. Or come back to Claude Code and ask me to fix it.

---

## 6. Setting up the Reader Queue (one-time, ~10 minutes)

The "Reader Queue" panel lets visitors suggest studies (by DOI or link) and
upvote each other's suggestions. Until you do this setup, it runs in
"preview mode" — each visitor only sees their own suggestions. Connecting
the free database makes it a real shared board.

**Part 1 — create the free database:**
1. Go to **https://console.firebase.google.com** and sign in with any
   Google account (free, no credit card).
2. Click **Create a Firebase project**. Name it anything
   (e.g. `clinical-perspective`). You can turn OFF Google Analytics when
   asked — you don't need it. Click through to create.
3. In the left menu, click **Build → Firestore Database → Create database**.
4. Choose **Start in production mode** and pick the location closest to you
   (e.g. `us-east1`). Click **Enable**.
5. Click the **Rules** tab, delete everything in the box, paste this
   exactly, then click **Publish**:

   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /suggestions/{doc} {
         allow read: if true;
         allow create: if request.resource.data.keys().hasOnly(['title','url','votes','createdAt'])
           && request.resource.data.title is string
           && request.resource.data.title.size() >= 3
           && request.resource.data.title.size() <= 200
           && request.resource.data.url is string
           && request.resource.data.url.size() <= 500
           && request.resource.data.url.matches('https?://.*')
           && request.resource.data.votes == 1;
         allow update: if request.resource.data.diff(resource.data).affectedKeys().hasOnly(['votes'])
           && request.resource.data.votes == resource.data.votes + 1;
         allow delete: if false;
       }
     }
   }
   ```

   (These rules mean: anyone can read the queue, submissions must be
   properly formatted, votes can only go up by 1 at a time, and nobody
   can delete or vandalize existing entries.)

**Part 2 — connect it to your website:**
1. In Firebase, click the **gear icon → Project settings** (top left).
2. Scroll down to **Your apps**, click the **`</>`** (Web) icon.
3. Nickname: anything (e.g. `website`). Don't check "hosting". Click
   **Register app**.
4. Firebase shows you a code block containing something like
   `apiKey: "AIza..."`, `projectId: "..."` etc. Keep that page open.
5. On your computer, open `CP → js → firebase-config.js` in Notepad.
6. Replace each `"PASTE_YOUR_CONFIG_HERE"` with the matching value from
   the Firebase page (apiKey, authDomain, projectId, storageBucket,
   messagingSenderId, appId). Keep the quote marks.
7. Save the file and re-upload the folder to Netlify (section 3, Step C).

That's it — the queue is now live and shared for everyone. (This `apiKey`
is safe to be public — it only identifies your project; the security rules
above are what protect the data.)

**Removing spam or junk suggestions:** go to Firebase →
**Firestore Database → Data** tab → `suggestions` collection. Click any
entry and delete it. Only you can do this.

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
