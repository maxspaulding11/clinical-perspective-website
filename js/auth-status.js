// Shared login with Spare Change. Fetches the current session once per page
// load and exposes it as a promise other scripts (queue.js) can await, and
// renders the "Sign in" / account nav widget if the page has a slot for it.

window.spareChangeSession = (function () {
  const origin = window.SPARE_CHANGE_ORIGIN;
  if (!origin) return Promise.resolve(null);
  return fetch(origin + "/api/auth/session", { credentials: "include" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => (data && data.user ? data.user : null))
    .catch(() => null);
})();

(function () {
  const slot = document.getElementById("nav-account");
  const origin = window.SPARE_CHANGE_ORIGIN;
  if (!slot || !origin) return;

  const callbackUrl = encodeURIComponent(window.location.href);

  window.spareChangeSession.then((user) => {
    slot.innerHTML = "";
    if (user) {
      const firstName = (user.name || user.email || "Account").trim().split(/\s+/)[0];

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "nav-account-name";
      toggle.setAttribute("aria-haspopup", "true");
      toggle.setAttribute("aria-expanded", "false");

      if (user.image) {
        const avatar = document.createElement("img");
        avatar.className = "nav-account-avatar";
        avatar.src = user.image;
        avatar.alt = "";
        toggle.appendChild(avatar);
      } else {
        const avatar = document.createElement("span");
        avatar.className = "nav-account-avatar nav-account-avatar-fallback";
        avatar.textContent = firstName.charAt(0).toUpperCase();
        toggle.appendChild(avatar);
      }
      const nameText = document.createElement("span");
      nameText.className = "nav-account-name-text";
      nameText.textContent = firstName;
      toggle.appendChild(nameText);

      const caret = document.createElement("span");
      caret.className = "nav-account-caret";
      caret.setAttribute("aria-hidden", "true");
      caret.textContent = "▾";
      toggle.appendChild(caret);

      const menu = document.createElement("div");
      menu.className = "nav-account-menu";

      const activity = document.createElement("a");
      activity.href = "/queue.html#my-activity";
      activity.title = "See your submitted and upvoted studies";
      activity.textContent = "My activity";
      menu.appendChild(activity);

      const signOut = document.createElement("a");
      signOut.className = "nav-signout";
      signOut.href = origin + "/signout?callbackUrl=" + callbackUrl;
      signOut.textContent = "Sign out";
      menu.appendChild(signOut);

      slot.appendChild(toggle);
      slot.appendChild(menu);

      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = slot.classList.toggle("open");
        toggle.setAttribute("aria-expanded", String(isOpen));
      });
      document.addEventListener("click", () => {
        slot.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    } else {
      const signIn = document.createElement("a");
      signIn.className = "nav-signin";
      signIn.href = origin + "/api/auth/signin?callbackUrl=" + callbackUrl;
      signIn.textContent = "Sign in";
      slot.appendChild(signIn);
    }
  });
})();
