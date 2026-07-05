# The Clinical Perspective — Website

A static site for the [@the_clinical_perspective](https://www.instagram.com/the_clinical_perspective/)
Instagram page. Each "Latest Research" card is a real, live embed pulled directly
from Instagram (via Instagram's own embed script), so it always reflects the
current state of the original post and links straight back to it.

## Adding a new post to the site

1. Open [`data/posts.json`](data/posts.json).
2. Copy the permalink of your Instagram post (open the post → **···** → **Copy link**).
3. Add a new entry to the array, e.g.:

   ```json
   {
     "url": "https://www.instagram.com/p/XXXXXXXXXXX/",
     "tag": "Cardiology",
     "title": "New anticoagulant trial shows reduced stroke risk",
     "date": "2026-07-10",
     "blurb": "One-sentence summary of the finding and why it matters."
   }
   ```

4. Delete the placeholder "Example Entry" once you've added your first real post.
5. Save the file and redeploy (see below) — or if your host auto-deploys from
   Git, just commit and push.

Posts are shown newest-first automatically, based on their order in the file
(the last entry in the array appears first) — you don't need to sort them.

## Changing the contact email

Open [`js/main.js`](js/main.js) and edit the `CONTACT_EMAIL` constant near the top.

## Running locally

Instagram's embed script requires the page to be served over HTTP (not opened
as a local `file://` path). From this folder, run:

```bash
npx serve .
```

or, if you have Python installed:

```bash
python -m http.server 8000
```

Then open the printed `localhost` URL in your browser.

## Deploying for free

Any static host works since this is plain HTML/CSS/JS with no build step.

**Vercel** (recommended, fastest):
1. Create a free account at vercel.com and install the Vercel CLI, or connect
   a GitHub repo containing this folder.
2. `vercel deploy` from this directory (or import the repo in the Vercel dashboard).
3. You'll get a free `yourproject.vercel.app` URL; a custom domain can be added later.

**Netlify**: drag-and-drop this whole folder onto app.netlify.com/drop, or
connect a Git repo the same way as Vercel.

**GitHub Pages**: push this folder to a GitHub repo, then enable Pages in
the repo's Settings → Pages, pointing at the `main` branch root.

## File structure

```
index.html        Page structure/content
css/style.css      All styling
js/main.js         Nav toggle, mailto link, loads + renders posts.json
data/posts.json    The list of posts shown in "Latest Research" — edit this to update the site
```
