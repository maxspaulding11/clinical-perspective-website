// Reader Queue — visitors sign in (shared login with Spare Change) to
// suggest studies (DOI or link) and upvote each other's suggestions.
// Falls back to a per-browser "preview mode" only if Spare Change itself
// can't be reached (e.g. its dev server isn't running, or it's briefly down).
//
// Two display modes, detected from the page:
//   - homepage: top 3 most-voted suggestions from the last 60 days
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

  const DEMO_KEY = "tcp-queue-demo";
  const HOME_LIMIT = 3;
  const WINDOW_MS = 60 * 24 * 60 * 60 * 1000;
  const origin = window.SPARE_CHANGE_ORIGIN;

  let signedIn = false;
  let rerender, submitFn, upvote;

  // ---------- link validation (matches Spare Change's server-side check) ----------
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
  function prepare(items) {
    const sorted = [...items].sort((a, b) => b.votes - a.votes || b.createdAt - a.createdAt);
    if (isArchive) return sorted;
    const cutoff = Date.now() - WINDOW_MS;
    return sorted.filter((i) => i.createdAt >= cutoff).slice(0, HOME_LIMIT);
  }

  // ---------- rendering ----------
  function render(items) {
    list.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "queue-empty";
      li.textContent = isArchive
        ? "No suggestions yet — be the first to add one."
        : "No suggestions in the past 60 days — add the first one!";
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
      const hasVoted = !!item.votedByMe;
      if (hasVoted) voteBtn.classList.add("voted");
      voteBtn.disabled = hasVoted || !signedIn;
      const voteLabel = hasVoted ? "Already upvoted" : signedIn ? "Upvote this study" : "Sign in to upvote";
      voteBtn.setAttribute("aria-label", voteLabel);
      if (!signedIn && !hasVoted) voteBtn.title = voteLabel;
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

  function setFormEnabled(enabled) {
    if (!form) return;
    titleInput.disabled = !enabled;
    linkInput.disabled = !enabled;
    const btn = form.querySelector("button[type=submit]");
    if (btn) btn.disabled = !enabled;
    if (note) note.textContent = enabled ? "" : "Sign in (top of page) to submit or upvote a study.";
  }

  // ---------- offline fallback (this browser only, Spare Change unreachable) ----------
  function useOfflineFallback() {
    if (form) {
      titleInput.disabled = false;
      linkInput.disabled = false;
      const btn = form.querySelector("button[type=submit]");
      if (btn) btn.disabled = false;
    }
    if (note) {
      note.textContent =
        "Couldn't reach the shared queue right now — showing a local preview instead.";
    }
    signedIn = true;

    const load = () => JSON.parse(localStorage.getItem(DEMO_KEY) || "[]");
    const save = (items) => localStorage.setItem(DEMO_KEY, JSON.stringify(items));
    rerender = () => render(prepare(load()));

    submitFn = async (title, url) => {
      const items = load();
      items.push({ id: "demo-" + Date.now(), title, url, votes: 1, createdAt: Date.now(), votedByMe: true });
      save(items);
      rerender();
    };

    upvote = (id) => {
      const items = load();
      const item = items.find((i) => i.id === id);
      if (!item || item.votedByMe) return;
      item.votes += 1;
      item.votedByMe = true;
      save(items);
      rerender();
    };

    rerender();
  }

  // ---------- backend selection ----------
  if (origin) {
    // ----- live shared database, via Spare Change's API -----
    const api = (path, options) =>
      fetch(origin + path, { credentials: "include", ...options }).then((res) => {
        if (!res.ok) return res.json().catch(() => ({})).then((body) => Promise.reject(body));
        return res.json();
      });

    rerender = () =>
      api("/api/queue")
        .then((items) => render(prepare(items)))
        .catch((err) => {
          if (err instanceof TypeError) {
            // Network/CORS failure — Spare Change isn't reachable right now.
            useOfflineFallback();
            return;
          }
          list.innerHTML = "";
          const li = document.createElement("li");
          li.className = "queue-empty";
          li.textContent = "Couldn't load the queue right now. Please refresh.";
          list.appendChild(li);
        });

    submitFn = (title, url) =>
      api("/api/queue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, url }),
      }).then(() => rerender());

    upvote = (id) => {
      api(`/api/queue/${id}/vote`, { method: "POST" }).then(() => rerender());
    };

    setFormEnabled(false); // enabled once we know the visitor is signed in
    rerender();
    Promise.resolve(window.spareChangeSession)
      .then((user) => {
        signedIn = !!user;
        setFormEnabled(signedIn);
        rerender();
      })
      .catch(() => {});
  } else {
    useOfflineFallback();
  }

  // ---------- form handling ----------
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!signedIn) {
        showMsg("Sign in first to submit a study.", true);
        return;
      }

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

      try {
        await submitFn(title, url);
        form.reset();
        showMsg("Added — thanks for the suggestion!");
      } catch (err) {
        showMsg((err && err.error) || "Couldn't submit right now. Please try again.", true);
      }
    });
  }
})();
