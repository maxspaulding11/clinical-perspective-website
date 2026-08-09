// Spare Change is where sign-in actually happens (Google login + database) —
// this site is just a client of it, so the Reader Queue can share one login
// across both sites.
//
// For local testing: run Spare Change's dev server (npm run dev, port 3000)
// alongside this site's own dev preview (port 5173), and this value already
// points at the right place.
//
// Once you've bought a domain and pointed Spare Change at a subdomain of it
// (see Stage 2 in GUIDE.md), change this to that address, e.g.
//   window.SPARE_CHANGE_ORIGIN = "https://spare.yourdomain.com";

window.SPARE_CHANGE_ORIGIN = "https://spare.theclinicalperspective.org";
