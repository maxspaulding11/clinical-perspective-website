// Loads Cloudflare Web Analytics, but only once a real token is configured
// in analytics-config.js. Until then this does nothing at all — no script is
// fetched and no beacon fires.
(function () {
  var token = window.analyticsToken;

  if (!token || typeof token !== "string") return;
  if (token.indexOf("PASTE_") === 0) return;

  // Don't count local previews as real traffic.
  var host = location.hostname;
  if (host === "localhost" || host === "127.0.0.1" || host === "" || host === "::1") return;

  var s = document.createElement("script");
  s.defer = true;
  s.src = "https://static.cloudflareinsights.com/beacon.min.js";
  s.setAttribute("data-cf-beacon", JSON.stringify({ token: token }));
  document.head.appendChild(s);
})();
