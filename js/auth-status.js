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

      const name = document.createElement("a");
      name.className = "nav-account-name";
      name.href = "queue.html#my-activity";
      name.title = "See your submitted and upvoted studies";

      if (user.image) {
        const avatar = document.createElement("img");
        avatar.className = "nav-account-avatar";
        avatar.src = user.image;
        avatar.alt = "";
        name.appendChild(avatar);
      } else {
        const avatar = document.createElement("span");
        avatar.className = "nav-account-avatar nav-account-avatar-fallback";
        avatar.textContent = firstName.charAt(0).toUpperCase();
        name.appendChild(avatar);
      }
      const nameText = document.createElement("span");
      nameText.className = "nav-account-name-text";
      nameText.textContent = firstName;
      name.appendChild(nameText);

      const signOut = document.createElement("a");
      signOut.className = "nav-signout";
      signOut.href = origin + "/signout?callbackUrl=" + callbackUrl;
      signOut.textContent = "Sign out";

      slot.appendChild(name);
      slot.appendChild(signOut);
    } else {
      const signIn = document.createElement("a");
      signIn.className = "nav-signin";
      signIn.href = origin + "/api/auth/signin?callbackUrl=" + callbackUrl;
      signIn.textContent = "Sign in";
      slot.appendChild(signIn);
    }
  });
})();
