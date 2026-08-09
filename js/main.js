// The Clinical Perspective — site behavior

const CONTACT_EMAIL = "theclinicalperspective@gmail.com";

document.getElementById("year").textContent = new Date().getFullYear();

// Mobile nav toggle
const navToggle = document.getElementById("nav-toggle");
const mainNav = document.getElementById("main-nav");
navToggle.addEventListener("click", () => {
  const isOpen = mainNav.classList.toggle("open");
  navToggle.setAttribute("aria-expanded", String(isOpen));
});
mainNav.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    mainNav.classList.remove("open");
    navToggle.setAttribute("aria-expanded", "false");
  });
});

// Email submission link
const emailBtn = document.getElementById("email-btn");
const subject = encodeURIComponent("Research Submission — The Clinical Perspective");
const body = encodeURIComponent(
  "Hi,\n\nI'd like to submit a study for The Clinical Perspective.\n\n" +
  "Paper title / link:\n" +
  "Why it's clinically relevant:\n" +
  "My name and affiliation:\n"
);
emailBtn.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;

// Weekly newsletter signup (MailerLite). The section stays hidden until
// a real form URL is pasted into js/newsletter-config.js.
(function () {
  const section = document.getElementById("newsletter");
  const navLink = document.getElementById("nav-newsletter");
  const nlForm = document.getElementById("newsletter-form");
  const emailInput = document.getElementById("newsletter-email");
  const nlMsg = document.getElementById("newsletter-msg");
  const action = window.newsletterFormAction;

  if (!section) return;
  const configured =
    typeof action === "string" &&
    action.indexOf("mailerlite.com") !== -1 &&
    action.indexOf("PASTE_") === -1;
  if (!configured) return; // section and nav link stay hidden

  section.hidden = false;
  if (navLink) navLink.hidden = false;

  nlForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      nlMsg.textContent = "Please enter a valid email address.";
      nlMsg.classList.add("newsletter-msg-error");
      return;
    }
    // Post through a hidden iframe: works from any static host with no
    // cross-origin issues, and the page never navigates away.
    nlForm.action = action;
    nlForm.method = "POST";
    nlForm.target = "ml-hidden";
    const mlFlag = document.createElement("input");
    mlFlag.type = "hidden";
    mlFlag.name = "ml-submit";
    mlFlag.value = "1";
    nlForm.appendChild(mlFlag);
    nlForm.submit();
    mlFlag.remove();
    nlForm.reset();
    nlMsg.classList.remove("newsletter-msg-error");
    nlMsg.textContent =
      "Almost done — check your inbox for a confirmation email.";
  });
})();

// Multi-axis parallax for the research-themed background decor:
// each shape gets its own vertical speed, horizontal drift, and rotation rate
const decorItems = document.querySelectorAll(".bg-decor .decor");
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (decorItems.length && !reduceMotion) {
  let ticking = false;
  const updateDecor = () => {
    const y = window.scrollY;
    decorItems.forEach((el) => {
      const speed = parseFloat(el.dataset.speed) || 0;
      const drift = parseFloat(el.dataset.drift) || 0;
      const rot = parseFloat(el.dataset.rot) || 0;
      el.style.transform =
        `translate3d(${y * drift}px, ${y * speed}px, 0) rotate(${y * rot}deg)`;
    });
    ticking = false;
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(updateDecor);
      }
    },
    { passive: true }
  );
  updateDecor();
}

// Scroll-reveal: elements with .reveal rise into view as they enter the viewport
document.body.classList.add("js-reveal");
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
);

function observeReveals(root) {
  (root || document).querySelectorAll(".reveal:not(.visible)").forEach((el) => {
    revealObserver.observe(el);
  });
}

if (reduceMotion) {
  document.querySelectorAll(".reveal").forEach((el) => el.classList.add("visible"));
} else {
  observeReveals();
}

// Load and render posts
const grid = document.getElementById("posts-grid");

function formatDate(dateStr) {
  // "2026-08-25" passed to new Date() is parsed as UTC midnight, which renders
  // as the previous day in any timezone behind UTC. Build a local date instead.
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateStr).trim());
  const d = parts
    ? new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]))
    : new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

// How many of the most recent studies to show on the homepage. The rest
// live in the full archive at research.html.
const HOMEPAGE_POST_LIMIT = 9;

function renderPosts(posts) {
  if (!Array.isArray(posts) || posts.length === 0) {
    grid.innerHTML = '<p class="posts-empty">No posts yet. Check back soon.</p>';
    return;
  }

  grid.innerHTML = "";

  // Safety net: the build already withholds studies dated in the future, but
  // if the site isn't rebuilt for a while, never show a study before the day
  // it's posted.
  const today = new Date();
  const todayIso = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");

  posts
    .slice()
    .filter((post) => !post.date || String(post.date) <= todayIso)
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .slice(0, HOMEPAGE_POST_LIMIT)
    .forEach((post, index) => {
      const card = document.createElement("article");
      card.className = "post-card reveal";
      card.style.transitionDelay = `${(index % 3) * 0.12}s`;

      // Only Instagram permalinks (…/p/… or …/reel/…) can be embedded; a bare
      // profile link would render every card as the same profile widget.
      const igEmbeddable = /instagram\.com\/(p|reel)\//.test(post.instagram || "");

      card.innerHTML = `
        <a class="post-card-link" href="${escapeAttr(post.url)}">
          <div class="post-card-meta">
            ${post.tag ? `<span class="post-tag">${escapeHtml(post.tag)}</span>` : ""}
            <h3>${escapeHtml(post.title || "Untitled")}</h3>
            ${post.date ? `<span class="post-date">${formatDate(post.date)}</span>` : ""}
          </div>
          ${post.blurb ? `<p class="post-blurb">${escapeHtml(post.blurb)}</p>` : ""}
        </a>
        ${igEmbeddable ? `
        <div class="post-embed">
          <blockquote class="instagram-media" data-instgrm-permalink="${escapeAttr(post.instagram)}" data-instgrm-version="14"></blockquote>
        </div>` : ""}
        <a class="post-fallback-link" href="${escapeAttr(post.url)}">Read the summary &rarr;</a>
      `;

      grid.appendChild(card);
    });

  if (reduceMotion) {
    grid.querySelectorAll(".reveal").forEach((el) => el.classList.add("visible"));
  } else {
    observeReveals(grid);
  }

  // Ask Instagram's embed script to render the blockquotes we just inserted
  if (window.instgrm && window.instgrm.Embeds) {
    window.instgrm.Embeds.process();
  } else {
    // embed.js may still be loading; retry briefly
    let attempts = 0;
    const retry = setInterval(() => {
      attempts += 1;
      if (window.instgrm && window.instgrm.Embeds) {
        window.instgrm.Embeds.process();
        clearInterval(retry);
      } else if (attempts > 20) {
        clearInterval(retry);
      }
    }, 300);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;");
}

fetch("data/posts.json")
  .then((res) => {
    if (!res.ok) throw new Error("Failed to load posts.json");
    return res.json();
  })
  .then(renderPosts)
  .catch(() => {
    grid.innerHTML = '<p class="posts-error">Couldn\'t load posts right now. Please refresh, or visit the Instagram page directly.</p>';
  });
