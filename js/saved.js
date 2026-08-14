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
  var origin = window.SPARE_CHANGE_ORIGIN;
  var signedIn = false; // flips true once we know there's an account session

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

  window.TCPSaved = {
    isSchoolSaved: function (id) { return readSet(SCHOOLS_KEY).has(id); },
    isProfSaved: function (id) { return readSet(PROFS_KEY).has(id); },
    toggleSchool: function (id) { return toggle('school', id); },
    toggleProf: function (id) { return toggle('professor', id); },
    removeSchool: function (id) { remove('school', id); },
    removeProf: function (id) { remove('professor', id); },
    getSchoolIds: function () { return Array.from(readSet(SCHOOLS_KEY)); },
    getProfIds: function () { return Array.from(readSet(PROFS_KEY)); },
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
      if (!user) return;
      signedIn = true;

      return fetch(origin + '/api/saved', { credentials: 'include' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          var serverSchools = new Set(data.schools || []);
          var serverProfs = new Set(data.professors || []);
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
