/* Counting what people actually do, without counting who they are.
 *
 * Cloudflare tells us pages were viewed. It cannot tell us whether a visit
 * turned into anything, and "traffic went up" is not an answer to "did that
 * advert work". The number that matters is whether somebody who arrived from
 * an ad went on to star a school, watch a program, or take their list away.
 *
 * What this sends, and nothing else: an event name from a fixed list, and the
 * host somebody arrived from. No identifier, no cookie, no session, no path,
 * no fingerprint. The server keeps one running total per day per event per
 * referring host, so two people doing the same thing on the same day are the
 * number 2 and are not distinguishable afterwards, even by us.
 *
 * The referring host is remembered for the tab only, in sessionStorage, and
 * is gone when the tab closes. It is kept at all because an advert's value
 * shows up on the page after the landing one -- somebody lands on the tracker
 * and stars a school two pages later -- and without it every conversion looks
 * like it came from nowhere. It is a host, never a full URL, so it says
 * "reddit.com" and cannot say which thread.
 *
 * sendBeacon, so a click that navigates away still counts and nothing blocks
 * on the network. Failures are silent by design: analytics must never be the
 * reason a button feels broken.
 */
(function () {
  'use strict';

  var ENDPOINT = (window.spareChangeOrigin || 'https://spare.theclinicalperspective.org')
    + '/api/event';
  var REF_KEY = 'tcp-ref';

  // Anything not on this list is dropped by the server too. A fixed list is
  // what stops this quietly becoming a place to record arbitrary detail.
  var ALLOWED = {
    'save-school': 1, 'save-prof': 1, 'watch': 1,
    'export-open': 1, 'export-file': 1, 'export-copy': 1
  };

  function landingRef() {
    try {
      var kept = sessionStorage.getItem(REF_KEY);
      if (kept !== null) return kept;
    } catch (e) { /* private mode, or storage blocked -- carry on without it */ }

    var host = '';
    try {
      if (document.referrer) {
        var h = new URL(document.referrer).hostname.replace(/^www\./, '');
        // Our own pages are not a referrer worth recording; we want the
        // outside source that started the visit.
        if (h && h !== location.hostname.replace(/^www\./, '')) host = h;
      }
    } catch (e) { /* malformed referrer */ }

    try { sessionStorage.setItem(REF_KEY, host); } catch (e) { /* fine */ }
    return host;
  }

  function send(name) {
    if (!ALLOWED[name]) return;
    if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') return;
    var body = JSON.stringify({ name: name, ref: landingRef() });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
        return;
      }
      fetch(ENDPOINT, {
        method: 'POST', body: body, keepalive: true,
        headers: { 'Content-Type': 'application/json' }
      }).catch(function () {});
    } catch (e) { /* never let counting break the thing being counted */ }
  }

  window.TCPEvent = send;

  // Wrapping the saved-list API rather than listening for clicks on a star:
  // the star is drawn by three different renderers with three different bits
  // of markup, and a selector that drifts out of date fails silently, which
  // is the worst way for a measurement to fail.
  function wrap() {
    var S = window.TCPSaved;
    if (!S || S.__counted) return !!S;
    S.__counted = true;

    // Watches go through toggleWatch, which returns null when somebody is
    // signed out and false when they are un-watching. Counting the click
    // instead counted all three, and the first day recorded 20 watches against
    // 15 that actually existed -- a measurement that overstates by a third is
    // worse than none, because it gets believed.
    if (typeof S.toggleWatch === 'function') {
      var originalWatch = S.toggleWatch;
      S.toggleWatch = function () {
        var now = originalWatch.apply(S, arguments);
        if (now === true) send('watch');
        return now;
      };
    }

    ['toggleSchool', 'toggleProf'].forEach(function (fn) {
      if (typeof S[fn] !== 'function') return;
      var original = S[fn];
      var evt = fn === 'toggleSchool' ? 'save-school' : 'save-prof';
      S[fn] = function (id) {
        var before = fn === 'toggleSchool' ? S.isSchoolSaved(id) : S.isProfSaved(id);
        var out = original.apply(S, arguments);
        // Only an add counts. Un-starring is a real signal but not the one
        // an advert is judged on, and counting both would inflate the total
        // every time somebody changed their mind.
        if (!before) send(evt);
        return out;
      };
    });
    return true;
  }

  if (!wrap()) {
    // saved.js may not have run yet, depending on script order on the page.
    document.addEventListener('DOMContentLoaded', wrap);
  }

  // Export buttons are counted by click because a click on them IS the
  // action -- unlike a watch, there is no later success or failure to wait
  // for. The watch handler that used to live here is gone; see wrap().
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#export-open-btn')) send('export-open');
    else if (t.closest('.export-btn')) {
      var fmt = t.closest('.export-btn').getAttribute('data-fmt');
      send(fmt === 'gdoc' || fmt === 'gsheet' ? 'export-copy' : 'export-file');
    }
  }, true);
})();
