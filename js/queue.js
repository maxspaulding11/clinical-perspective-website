// Reader Queue — visitors suggest studies (DOI or link) and upvote them.
// Runs against Firestore when configured; otherwise falls back to a
// per-browser "preview mode" using localStorage.
//
// Two display modes, detected from the page:
//   - homepage: top 3 most-voted suggestions from the last 30 days
//   - archive (queue.html): every suggestion, sorted by votes

(function () {
  const form = document.getElementById("queue-form");
  const titleInput = document.getElementById("queue-title-input");
  const linkInput = document.getElementById("queue-link-input");
  const list = document.getElementById("queue-list");
  const msg = document.getElementById("queue-msg");
  const note = document.getElementById("queue-note");
  const isArchive = document.body.dataset.queuePage === "archive";

  if (!list) return;

  const VOTED_KEY = "tcp-queue-voted";
  const DEMO_KEY = "tcp-queue-demo";
  const LAST_SUBMIT_KEY = "tcp-queue-last-submit";
  const HOME_LIMIT = 3;
  const MONTH_MS = 30 * 24 * 60 * 60 * 1000;

  const votedIds = new Set(JSON.parse(localStorage.getItem(VOTED_KEY) || "[]"));

  // ---------- link validation ----------
  function normalizeLink(raw) {
    const value = raw.trim();
    const doiMatch = value.match(/^(?:doi:\s*)?(10\.\d{4,9}\/\S+)$/i);
    if (doiMatch) return "https://doi.org/" + doiMatch[1];
    try {
      const url = new URL(value);
      if (url.protocol === "http:" || url.protocol === "https:") return url.href;
    } catch (e) { /* not a URL */ }
    return null;
  }

  function showMsg(text, isError) {
    if (!msg) return;
    msg.textContent = text;
    msg.classList.toggle("queue-msg-error", !!isError);
    if (text) setTimeout(() => { if (msg.textContent === text) msg.textContent = ""; }, 6000);
  }

  // ---------- sorting / filtering ----------
  function timestampOf(item) {
    if (item.createdAt && typeof item.createdAt.toMillis === "function") {
      return item.createdAt.toMillis();
    }
    if (typeof item.createdAt === "number") return item.createdAt;
    return Date.now(); // pending server timestamp on a just-added doc
  }

  function prepare(items) {
    const withTs = items.map((i) => ({ ...i, ts: timestampOf(i) }));
    withTs.sort((a, b) => b.votes - a.votes || b.ts - a.ts);
    if (isArchive) return withTs;
    const cutoff = Date.now() - MONTH_MS;
    return withTs.filter((i) => i.ts >= cutoff).slice(0, HOME_LIMIT);
  }

  // ---------- rendering ----------
  function render(items) {
    list.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "queue-empty";
      li.textContent = isArchive
        ? "No suggestions yet — be the first to add one."
        : "No suggestions in the past 30 days — add the first one!";
      list.appendChild(li);
      return;
    }
    items.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "queue-item";

      if (!isArchive) {
        const rank = document.createElement("span");
        rank.className = "queue-rank";
        rank.textContent = index + 1;
        li.appendChild(rank);
      }

      const voteBtn = document.createElement("button");
      voteBtn.type = "button";
      voteBtn.className = "queue-vote";
      const hasVoted = votedIds.has(item.id);
      if (hasVoted) voteBtn.classList.add("voted");
      voteBtn.disabled = hasVoted;
      voteBtn.setAttribute("aria-label", hasVoted ? "Already upvoted" : "Upvote this study");
      voteBtn.innerHTML = `<span class="queue-arrow">&#9650;</span><span class="queue-count">${item.votes}</span>`;
      voteBtn.addEventListener("click", () => upvote(item.id));

      const body = document.createElement("div");
      body.className = "queue-item-body";

      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener nofollow";
      link.className = "queue-item-title";
      link.textContent = item.title;

      const host = document.createElement("span");
      host.className = "queue-item-host";
      try { host.textContent = new URL(item.url).hostname.replace(/^www\./, ""); } catch (e) {}

      body.appendChild(link);
      body.appendChild(host);
      li.appendChild(voteBtn);
      li.appendChild(body);
      list.appendChild(li);
    });
  }

  function rememberVote(id) {
    votedIds.add(id);
    localStorage.setItem(VOTED_KEY, JSON.stringify([...votedIds]));
  }

  function rateLimited() {
    const last = parseInt(localStorage.getItem(LAST_SUBMIT_KEY) || "0", 10);
    return Date.now() - last < 60000;
  }

  // ---------- backend selection ----------
  const config = window.firebaseConfig || {};
  const isConfigured =
    config.apiKey && config.apiKey !== "PASTE_YOUR_CONFIG_HERE" &&
    typeof firebase !== "undefined";

  let submitFn, upvote;

  if (isConfigured) {
    // ----- live shared database (Firestore) -----
    firebase.initializeApp(config);
    const db = firebase.firestore();
    const col = db.collection("suggestions");

    col.orderBy("createdAt", "desc").limit(200).onSnapshot(
      (snap) => {
        const items = snap.docs.map((d) => ({ id: d.id, ...d.data() }));
        render(prepare(items));
      },
      () => {
        list.innerHTML = "";
        const li = document.createElement("li");
        li.className = "queue-empty";
        li.textContent = "Couldn't load the queue right now. Please refresh.";
        list.appendChild(li);
      }
    );

    submitFn = async (title, url) => {
      const ref = await col.add({
        title: title,
        url: url,
        votes: 1,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
      });
      rememberVote(ref.id);
    };

    upvote = async (id) => {
      if (votedIds.has(id)) return;
      rememberVote(id);
      try {
        await col.doc(id).update({
          votes: firebase.firestore.FieldValue.increment(1)
        });
      } catch (e) { /* snapshot listener keeps UI consistent */ }
    };
  } else {
    // ----- preview mode (this browser only) -----
    if (note) {
      note.textContent =
        "Preview mode: suggestions currently save only in your own browser. " +
        "They'll be shared with all visitors once the site's database is connected.";
    }

    const load = () => JSON.parse(localStorage.getItem(DEMO_KEY) || "[]");
    const save = (items) => localStorage.setItem(DEMO_KEY, JSON.stringify(items));
    const rerender = () => render(prepare(load()));

    submitFn = async (title, url) => {
      const items = load();
      const id = "demo-" + Date.now();
      items.push({ id, title, url, votes: 1, createdAt: Date.now() });
      save(items);
      rememberVote(id);
      rerender();
    };

    upvote = (id) => {
      if (votedIds.has(id)) return;
      const items = load();
      const item = items.find((i) => i.id === id);
      if (!item) return;
      item.votes += 1;
      save(items);
      rememberVote(id);
      rerender();
    };

    rerender();
  }

  // ---------- form handling ----------
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const title = titleInput.value.trim();
      const url = normalizeLink(linkInput.value);

      if (title.length < 3) {
        showMsg("Please enter the study's title.", true);
        return;
      }
      if (!url) {
        showMsg("That doesn't look like a DOI or link. Try e.g. 10.1001/jama.2026.1234", true);
        return;
      }
      if (rateLimited()) {
        showMsg("Please wait a minute between submissions.", true);
        return;
      }

      try {
        await submitFn(title, url);
        localStorage.setItem(LAST_SUBMIT_KEY, String(Date.now()));
        form.reset();
        showMsg("Added — thanks for the suggestion!");
      } catch (err) {
        showMsg("Couldn't submit right now. Please try again.", true);
      }
    });
  }
})();
