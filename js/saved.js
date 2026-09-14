/* ============================================================
   "My List" — saved schools & professors. Kept in localStorage
   so it works with no account; if signed in to Spare Change,
   also synced to the account so the same list follows you to
   any device. Shared by faculty.js, professor-search.js,
   saved-list.js, and the "★ My List" nav button on every tools
   page. Must load AFTER spare-change-config.js and auth-status.js.
   ============================================================ */
(function () {
  'use strict';

  var SCHOOLS_KEY = 'tcp-saved-schools';
  var PROFS_KEY = 'tcp-saved-profs';
  var WATCH_KEY = 'tcp-watching';
  var origin = window.SPARE_CHANGE_ORIGIN;
  var signedIn = false; // flips true once we know there's an account session

  // Watching is not like starring. A star is a private bookmark and works
  // fine with no account, so it lives in localStorage first. A watch is a
  // request to be told something, and there is nowhere to tell an anonymous
  // browser — so it only exists on the account. The local copy here is a
  // render cache so the button doesn't flicker on a repeat visit, and it is
  // cleared the moment we learn nobody is signed in, because showing
  // "Notifying" to someone who is signed out would be a lie.

  function readSet(key) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch (e) {
      return new Set();
    }
  }

  function writeSet(key, set) {
    try {
      localStorage.setItem(key, JSON.stringify(Array.from(set)));
    } catch (e) { /* storage unavailable — saving silently no-ops */ }
    updateBadges();
  }

  function count() {
    return readSet(SCHOOLS_KEY).size + readSet(PROFS_KEY).size;
  }

  function updateBadges() {
    var n = count();
    document.querySelectorAll('.nav-saved-count').forEach(function (el) {
      el.textContent = n ? String(n) : '';
      el.hidden = n === 0;
    });
  }

  function keyFor(kind) { return kind === 'school' ? SCHOOLS_KEY : PROFS_KEY; }

  function apiSave(kind, id, action) {
    if (!signedIn || !origin) return;
    fetch(origin + '/api/saved', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: kind, id: id, action: action })
    }).catch(function () { /* offline or request failed — local copy still holds */ });
  }

  function toggle(kind, id) {
    var set = readSet(keyFor(kind));
    var nowSaved;
    if (set.has(id)) {
      set.delete(id);
      nowSaved = false;
    } else {
      set.add(id);
      nowSaved = true;
    }
    writeSet(keyFor(kind), set);
    apiSave(kind, id, nowSaved ? 'add' : 'remove');
    return nowSaved;
  }

  function remove(kind, id) {
    var set = readSet(keyFor(kind));
    set.delete(id);
    writeSet(keyFor(kind), set);
    apiSave(kind, id, 'remove');
  }

  // Returns true if now watching, false if no longer, and null if we can't —
  // which the caller turns into a prompt to sign in rather than a dead click.
  function toggleWatch(id) {
    if (!signedIn || !origin) return null;
    var set = readSet(WATCH_KEY);
    var now;
    if (set.has(id)) { set.delete(id); now = false; } else { set.add(id); now = true; }
    writeSet(WATCH_KEY, set);
    apiSave('school-watch', id, now ? 'add' : 'remove');
    return now;
  }

  // The bell's markup, repaint and click behaviour live here rather than in
  // faculty.js, because the tracker and "My List" both draw the same control
  // and two copies would drift the moment one of them changed.
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  var ON_TITLE = 'You\'ll be told when this program changes';
  var OFF_TITLE = 'Tell me when this program changes';

  // Statuses with nothing left to wait for. Offering to tell somebody when a
  // list appears, on a program whose list is already up, is noise.
  var SETTLED = { posted: true, closed: true };

  // Returns '' when there is nothing worth offering — but never when the
  // person is already watching. Hiding the control along with the invitation
  // would leave them holding a watch they cannot switch off.
  function watchButtonHTML(id, status) {
    var on = signedIn && readSet(WATCH_KEY).has(id);
    if (!on && SETTLED[status]) return '';
    return '<button type="button" class="watch-btn' + (on ? ' is-watching' : '') + '" ' +
      'data-watch-school="' + esc(id) + '" aria-pressed="' + (on ? 'true' : 'false') + '" ' +
      'title="' + (on ? ON_TITLE : OFF_TITLE) + '">' +
      '<span aria-hidden="true">' + (on ? '✓' : '🔔') + '</span> ' +
      '<span class="watch-btn-text">' + (on ? 'Notifying' : 'Notify me') + '</span>' +
      '</button>';
  }

  function paintWatchButton(btn, on) {
    btn.classList.toggle('is-watching', on);
    btn.classList.remove('watch-btn-needs-auth');
    btn.setAttribute('aria-pressed', String(on));
    btn.title = on ? ON_TITLE : OFF_TITLE;
    btn.firstElementChild.textContent = on ? '✓' : '🔔';
    btn.querySelector('.watch-btn-text').textContent = on ? 'Notifying' : 'Notify me';
  }

  // Returns true if this click was a watch toggle and has been dealt with,
  // so a list's own click handler can stop there.
  function handleWatchClick(target) {
    var btn = target.closest && target.closest('[data-watch-school]');
    if (!btn) return false;
    var now = toggleWatch(btn.dataset.watchSchool);
    if (now === null) {
      // Signed out. Say why rather than doing nothing.
      btn.querySelector('.watch-btn-text').textContent = 'Sign in to be notified';
      btn.classList.add('watch-btn-needs-auth');
    } else {
      paintWatchButton(btn, now);
    }
    return true;
  }

  window.TCPSaved = {
    isSchoolSaved: function (id) { return readSet(SCHOOLS_KEY).has(id); },
    isProfSaved: function (id) { return readSet(PROFS_KEY).has(id); },
    toggleSchool: function (id) { return toggle('school', id); },
    toggleProf: function (id) { return toggle('professor', id); },
    removeSchool: function (id) { remove('school', id); },
    removeProf: function (id) { remove('professor', id); },
    getSchoolIds: function () { return Array.from(readSet(SCHOOLS_KEY)); },
    getProfIds: function () { return Array.from(readSet(PROFS_KEY)); },
    isWatching: function (id) { return signedIn && readSet(WATCH_KEY).has(id); },
    toggleWatch: toggleWatch,
    watchButtonHTML: watchButtonHTML,
    paintWatchButton: paintWatchButton,
    handleWatchClick: handleWatchClick,
    getWatchIds: function () { return signedIn ? Array.from(readSet(WATCH_KEY)) : []; },
    canWatch: function () { return signedIn && !!origin; },
    count: count,
    updateBadges: updateBadges
  };

  document.addEventListener('DOMContentLoaded', updateBadges);

  // If signed in, reconcile this device's local list with the account:
  // push up anything saved here before sign-in (or while offline), pull
  // down anything saved on another device, then keep localStorage as an
  // offline-first cache mirroring the account from here on.
  if (origin && window.spareChangeSession) {
    window.spareChangeSession.then(function (user) {
      if (!user) {
        // Signed out: the star lists stand on their own, but a cached watch
        // list would claim notifications nobody is going to receive.
        writeSet(WATCH_KEY, new Set());
        document.dispatchEvent(new CustomEvent('tcp-saved-synced'));
        return;
      }
      signedIn = true;

      return fetch(origin + '/api/saved', { credentials: 'include' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          var serverSchools = new Set(data.schools || []);
          var serverProfs = new Set(data.professors || []);

          // Watches are not merged the way stars are. There is no offline
          // watch to push up — the button is only offered to signed-in
          // people — so the account is simply the answer.
          writeSet(WATCH_KEY, new Set(data.watching || []));
          var localOnlySchools = Array.from(readSet(SCHOOLS_KEY)).filter(function (id) { return !serverSchools.has(id); });
          var localOnlyProfs = Array.from(readSet(PROFS_KEY)).filter(function (id) { return !serverProfs.has(id); });

          localOnlySchools.forEach(function (id) { apiSave('school', id, 'add'); serverSchools.add(id); });
          localOnlyProfs.forEach(function (id) { apiSave('professor', id, 'add'); serverProfs.add(id); });

          writeSet(SCHOOLS_KEY, serverSchools);
          writeSet(PROFS_KEY, serverProfs);

          // Let any already-rendered list (star buttons, saved.html) know
          // the saved state may have changed, e.g. items saved elsewhere.
          document.dispatchEvent(new CustomEvent('tcp-saved-synced'));
        })
        .catch(function () { /* couldn't reach the account API — local copy stands */ });
    });
  }
})();
