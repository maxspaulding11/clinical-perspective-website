/* ============================================================
   "My List" page — renders saved schools & professors from
   localStorage against data/programs.json and data/professors.json
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  const STATUS_LABEL = {
    posted:     'List posted',
    pending:    'Not posted yet',
    unverified: 'Not checked by us yet',
    cohort:     'Admits by cohort — no mentor list',
    closed:     'Program closed this cycle'
  };

  // Names in a program's accepting/maybe/notAccepting lists sometimes carry
  // credentials, parenthetical notes ("(Affiliated Faculty)", "(retired)"),
  // or hyphenated/double surnames a professor's own record doesn't split the
  // same way — normalize both sides the same way before comparing.
  function normName(s) {
    return String(s)
      .toLowerCase()
      .replace(/\([^)]*\)/g, ' ')
      .replace(/\b(dr|phd|psyd|ph\.d|psy\.d|jr|sr|ii|iii|abpp|mph|mdiv|mscp)\b\.?/g, '')
      .replace(/[.,]/g, '')
      .replace(/-/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function nameTokens(s) {
    return normName(s).split(' ').filter(Boolean);
  }

  function firstName(s) {
    return nameTokens(s)[0] || '';
  }

  // Every token after the first name — covers hyphenated and double surnames
  // ("Sarah Mattson Weller" → ["mattson", "weller"]) so a list entry that only
  // gives one piece of a compound surname still finds the right person.
  function surnameTokens(s) {
    const t = nameTokens(s);
    return t.length > 1 ? t.slice(1) : t;
  }

  function levenshtein(a, b) {
    const m = a.length, n = b.length;
    const dp = [];
    for (let i = 0; i <= m; i++) dp.push([i]);
    for (let j = 1; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        dp[i][j] = a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
      }
    }
    return dp[m][n];
  }

  let profByExactKey = {};
  let profByLastKey = {};
  let profsBySchoolProgram = {};
  let statusByProfId = {};

  // Accepting-list names are sometimes nicknames, drop a middle initial, or
  // carry a slightly different spelling than the professor's own bio page.
  // Try, in order: exact normalized match; same surname token (unique within
  // the program); surname + first-name prefix tiebreak; and finally a small
  // edit-distance fallback for genuine spelling variants (only when it
  // resolves to exactly one person, so it can't misfire).
  function findProfId(school, program, rawName) {
    const exactKey = school + '|||' + program + '|||' + normName(rawName);
    if (profByExactKey[exactKey]) return profByExactKey[exactKey];

    const surnames = surnameTokens(rawName);
    const seen = {};
    let candidates = [];
    surnames.forEach(tok => {
      (profByLastKey[school + '|||' + program + '|||' + tok] || []).forEach(c => {
        if (!seen[c.id]) { seen[c.id] = true; candidates.push(c); }
      });
    });
    if (candidates.length === 1) return candidates[0].id;
    if (candidates.length > 1) {
      const fn = firstName(rawName);
      const pref = candidates.filter(c => c.firstName.indexOf(fn) === 0 || fn.indexOf(c.firstName) === 0);
      if (pref.length === 1) return pref[0].id;
    }

    const pool = profsBySchoolProgram[school + '|||' + program] || [];
    if (pool.length && surnames.length) {
      const lastTok = surnames[surnames.length - 1];
      const close = pool.filter(c => c.surnameTokens.some(t => levenshtein(t, lastTok) <= 2));
      if (close.length === 1) return close[0].id;
    }
    return null;
  }

  function acceptingBadge(p) {
    const rec = p._prog;
    if (!rec) return '';
    if (rec.status !== 'posted') {
      const label = STATUS_LABEL[rec.status];
      return label ? '<span class="fac-badge ' + rec.status + '">' + label + '</span>' : '';
    }
    const status = statusByProfId[p.id];
    if (status === 'accepting') {
      return '<span class="fac-check" title="Accepting doctoral students this cycle" aria-label="Accepting doctoral students this cycle">✓</span>' +
        '<span class="fac-badge posted">Accepting this cycle</span>';
    }
    if (status === 'maybe') return '<span class="fac-badge pending">Maybe — contact directly</span>';
    if (status === 'not-accepting') return '<span class="fac-badge closed">Not accepting this cycle</span>';
    return '';
  }

  function profStarBtn(id) {
    const saved = window.TCPSaved && window.TCPSaved.isProfSaved(id);
    return '<button type="button" class="star-btn star-btn-sm' + (saved ? ' is-saved' : '') + '" ' +
      'data-star-prof="' + esc(id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '" ' +
      'aria-label="' + (saved ? 'Remove from my list' : 'Save professor to my list') + '" ' +
      'title="' + (saved ? 'Saved — click to remove' : 'Save to my list') + '">' +
      (saved ? '★' : '☆') + '</button>';
  }

  const GRE_LABEL = {
    required:        'GRE required',
    optional:        'GRE optional',
    'not accepted':  'GRE not accepted',
    'not mentioned': 'GRE: not stated'
  };

  function appInfo(p) {
    if (!p) return '';
    const items = [];
    if (p.applicationDeadline) {
      items.push('<span class="fac-appinfo-item">Deadline: <strong>' + esc(p.applicationDeadline) + '</strong>' +
        (p.deadlineCycle ? ' <span class="fac-appinfo-sub">(' + esc(p.deadlineCycle) + ')</span>' : '') + '</span>');
    }
    const gre = GRE_LABEL[p.greRequired];
    if (gre) items.push('<span class="fac-appinfo-item">' + esc(gre) + '</span>');
    if (p.numReferences) {
      items.push('<span class="fac-appinfo-item">' + p.numReferences + ' reference' + (p.numReferences === 1 ? '' : 's') + '</span>');
    }
    if (p.applicationFee) items.push('<span class="fac-appinfo-item">Fee: ' + esc(p.applicationFee) + '</span>');

    const other = (p.otherRequirements || []).length
      ? '<ul class="fac-appinfo-other">' + p.otherRequirements.map(r => '<li>' + esc(r) + '</li>').join('') + '</ul>'
      : '';

    if (!items.length && !other) return '';
    return '<div class="fac-appinfo">' +
      (items.length ? '<div class="fac-appinfo-row">' + items.join('') + '</div>' : '') +
      other +
    '</div>';
  }

  function nameList(names, p) {
    if (!names || !names.length) return '';
    return '<div class="fac-group">' +
      '<p class="fac-group-label yes">Accepting students</p>' +
      '<ul class="fac-names">' +
        names.map(n => {
          const profId = findProfId(p.school, p.program, n);
          return profId
            ? '<li class="yes has-star"><span class="fac-name-text">' + esc(n) + '</span>' + profStarBtn(profId) + '</li>'
            : '<li class="yes">' + esc(n) + '</li>';
        }).join('') +
      '</ul></div>';
  }

  function schoolCard(p) {
    const count = (p.accepting || []).length;
    const badge = p.status === 'posted'
      ? '<span class="fac-badge posted">' + count + ' accepting</span>'
      : '<span class="fac-badge ' + p.status + '">' + (STATUS_LABEL[p.status] || '') + '</span>';

    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.school) + '</h3>' +
          '<p class="fac-sub">' + esc(p.program) + (p.state ? ' · ' + esc(p.state) : '') + '</p>' +
        '</div>' +
        '<div class="fac-head-right">' +
          '<button type="button" class="star-btn is-saved" data-remove-school="' + esc(p.id) + '" ' +
            'aria-label="Remove from my list" title="Remove from my list">★</button>' +
          window.TCPSaved.watchButtonHTML(p.id, p.status) +
          badge +
        '</div>' +
      '</div>' +
      appInfo(p) +
      nameList(p.accepting, p) +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">Check the program\'s own page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  function profCard(p) {
    const interests = (p.interests || []).map(i => '<li>' + esc(i) + '</li>').join('');
    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.name) + '</h3>' +
          '<p class="fac-sub">' + esc(p.school) + (p.program ? ' · ' + esc(p.program) : '') + '</p>' +
        '</div>' +
        '<div class="fac-head-right">' +
          '<button type="button" class="star-btn is-saved" data-remove-prof="' + esc(p.id) + '" ' +
            'aria-label="Remove from my list" title="Remove from my list">★</button>' +
          acceptingBadge(p) +
        '</div>' +
      '</div>' +
      appInfo(p._prog) +
      '<ul class="prof-interests">' + interests + '</ul>' +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">View their university page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  const MONTH_RE = '(January|February|March|April|May|June|July|August|September|October|November|December)';
  const DEADLINE_RE = new RegExp('\\b' + MONTH_RE + '\\s+(\\d{1,2}),?\\s+(\\d{4})\\b');

  function parseEarliestDeadline(text) {
    if (!text) return null;
    const m = DEADLINE_RE.exec(text);
    if (!m) return null;
    const d = new Date(m[1] + ' ' + m[2] + ', ' + m[3]);
    return isNaN(d.getTime()) ? null : d;
  }

  function parseFee(text) {
    if (!text) return null;
    const m = /\$([\d,]+)/.exec(text);
    if (!m) return null;
    const n = parseInt(m[1].replace(/,/g, ''), 10);
    return isNaN(n) ? null : n;
  }

  function statTile(label, value, sub) {
    return '<div class="stat-tile">' +
      '<p class="stat-tile-value">' + value + '</p>' +
      '<p class="stat-tile-label">' + esc(label) + '</p>' +
      (sub ? '<p class="stat-tile-sub">' + sub + '</p>' : '') +
      '</div>';
  }

  function renderStatsBox(schools) {
    const box = $('#saved-stats-box');
    if (!schools.length) { box.hidden = true; box.innerHTML = ''; return; }

    const tiles = [statTile('Saved schools', schools.length)];

    let earliest = null;
    schools.forEach(p => {
      const d = parseEarliestDeadline(p.applicationDeadline);
      if (d && (!earliest || d < earliest.date)) earliest = { date: d, school: p.school };
    });
    if (earliest) {
      const dateStr = earliest.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      tiles.push(statTile('Earliest deadline', esc(dateStr), esc(earliest.school)));
    }

    let feeTotal = 0, feeCount = 0;
    schools.forEach(p => {
      const fee = parseFee(p.applicationFee);
      if (fee != null) { feeTotal += fee; feeCount++; }
    });
    if (feeCount) {
      const sub = feeCount === schools.length
        ? 'across all ' + feeCount + ' saved schools'
        : 'across ' + feeCount + ' of ' + schools.length + ' with a listed fee';
      tiles.push(statTile('Total application fees', '$' + feeTotal.toLocaleString(), esc(sub)));
    }

    let maxRefs = 0, maxRefSchools = [];
    schools.forEach(p => {
      if (typeof p.numReferences === 'number' && p.numReferences > 0) {
        if (p.numReferences > maxRefs) { maxRefs = p.numReferences; maxRefSchools = [p.school]; }
        else if (p.numReferences === maxRefs) maxRefSchools.push(p.school);
      }
    });
    if (maxRefs > 0) {
      const shown = maxRefSchools.slice(0, 2).join(', ') +
        (maxRefSchools.length > 2 ? ' +' + (maxRefSchools.length - 2) + ' more' : '');
      tiles.push(statTile('Most references needed', maxRefs, esc(shown)));
    }

    box.hidden = false;
    box.innerHTML = tiles.join('');
  }

  function renderSchools(programs) {
    const byId = {};
    programs.forEach(p => { byId[p.id] = p; });
    const shown = window.TCPSaved.getSchoolIds()
      .map(id => byId[id])
      .filter(Boolean)
      .sort((a, b) => a.school.localeCompare(b.school));

    $('#saved-schools-count').textContent = shown.length + (shown.length === 1 ? ' saved' : ' saved');
    $('#saved-schools-list').innerHTML = shown.length
      ? shown.map(schoolCard).join('')
      : '<li class="fac-empty">No saved schools yet. <a href="faculty-accepting-students.html">Browse who\'s accepting students →</a></li>';
    renderStatsBox(shown);
  }

  function renderProfs(professors) {
    const byId = {};
    professors.forEach(p => { byId[p.id] = p; });
    const shown = window.TCPSaved.getProfIds()
      .map(id => byId[id])
      .filter(Boolean)
      .sort((a, b) => a.name.localeCompare(b.name));

    $('#saved-profs-count').textContent = shown.length + ' saved';
    $('#saved-profs-list').innerHTML = shown.length
      ? shown.map(profCard).join('')
      : '<li class="fac-empty">No saved professors yet. <a href="professor-search.html">Search professors by research interest →</a></li>';
  }

  Promise.all([
    fetch('../data/programs.json').then(r => r.ok ? r.json() : { programs: [] }).catch(() => ({ programs: [] })),
    fetch('../data/professors.json').then(r => r.ok ? r.json() : { professors: [] }).catch(() => ({ professors: [] }))
  ]).then(([progData, profData]) => {
    const programs = progData.programs || [];
    const professors = profData.professors || [];

    const programIndex = {};
    programs.forEach(rec => { programIndex[rec.school + '|||' + rec.program] = rec; });
    professors.forEach(p => { p._prog = programIndex[p.school + '|||' + p.program] || null; });

    professors.forEach(prof => {
      const exactKey = prof.school + '|||' + prof.program + '|||' + normName(prof.name);
      profByExactKey[exactKey] = prof.id;
      const surnames = surnameTokens(prof.name);
      const fn = firstName(prof.name);
      surnames.forEach(tok => {
        const lastKey = prof.school + '|||' + prof.program + '|||' + tok;
        (profByLastKey[lastKey] = profByLastKey[lastKey] || []).push({ id: prof.id, firstName: fn });
      });
      const spKey = prof.school + '|||' + prof.program;
      (profsBySchoolProgram[spKey] = profsBySchoolProgram[spKey] || []).push({ id: prof.id, surnameTokens: surnames });
    });

    // Resolve each posted program's accepting/maybe/notAccepting names to a
    // professor id once, using the same matching the star button uses — so
    // the checkmark and the save star never disagree about who's who.
    programs.filter(rec => rec.status === 'posted').forEach(rec => {
      [['accepting', 'accepting'], ['maybe', 'maybe'], ['notAccepting', 'not-accepting']].forEach(([field, status]) => {
        (rec[field] || []).forEach(name => {
          const id = findProfId(rec.school, rec.program, name);
          if (id) statusByProfId[id] = status;
        });
      });
    });

    renderSchools(programs);
    renderProfs(professors);

    $('#saved-schools-list').addEventListener('click', e => {
      if (window.TCPSaved.handleWatchClick(e.target)) return;
      const removeBtn = e.target.closest('[data-remove-school]');
      if (removeBtn) {
        window.TCPSaved.removeSchool(removeBtn.dataset.removeSchool);
        renderSchools(programs);
        return;
      }
      const starBtn = e.target.closest('[data-star-prof]');
      if (starBtn && window.TCPSaved) {
        window.TCPSaved.toggleProf(starBtn.dataset.starProf);
        renderSchools(programs);
        renderProfs(professors);
      }
    });

    $('#saved-profs-list').addEventListener('click', e => {
      const btn = e.target.closest('[data-remove-prof]');
      if (!btn) return;
      window.TCPSaved.removeProf(btn.dataset.removeProf);
      renderProfs(professors);
    });

    document.addEventListener('tcp-saved-synced', () => {
      renderSchools(programs);
      renderProfs(professors);
    });
  }).catch(() => {
    $('#saved-schools-list').innerHTML = '<li class="fac-empty">Could not load your saved list. Please refresh.</li>';
    $('#saved-profs-list').innerHTML = '<li class="fac-empty">Could not load your saved list. Please refresh.</li>';
  });
})();

/* ---------- What changed ----------
   Notices about programs the signed-in person asked to be told about. Written
   by scripts/watch_notify.py after a publish; nothing is pushed or emailed, so
   this panel is where they actually get read. Hidden entirely when there is
   nothing to show, rather than sitting there empty. */
(function () {
  'use strict';

  var origin = window.SPARE_CHANGE_ORIGIN;
  var panel = document.getElementById('watch-panel');
  var list = document.getElementById('watch-list');
  var markBtn = document.getElementById('watch-mark-read');
  if (!origin || !panel || !list) return;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function when(ms) {
    var days = Math.floor((Date.now() - ms) / 86400000);
    if (days <= 0) return 'today';
    if (days === 1) return 'yesterday';
    if (days < 30) return days + ' days ago';
    return new Date(ms).toLocaleDateString('en-US',
      { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function line(c) {
    var name = esc(c.school || c.id) +
      (c.program ? ' <span class="watch-prog">' + esc(c.program) + '</span>' : '');
    var what;
    if (c.to === 'closed') {
      what = 'closed this cycle';
    } else if (c.from === 'posted' && c.to === 'posted') {
      what = 'list changed to ' + c.accepting + ' faculty accepting';
    } else {
      what = 'posted its list — ' + c.accepting + ' faculty accepting';
    }
    return '<span class="watch-school">' + name + '</span>' +
           '<span class="watch-what">' + esc(what) + '</span>';
  }

  function render(data) {
    var items = data.items || [];
    if (!items.length) { panel.hidden = true; return; }

    list.innerHTML = items.map(function (n) {
      var changes = Array.isArray(n.changes) ? n.changes : [];
      return '<li class="watch-item' + (n.read ? '' : ' is-unread') + '">' +
        '<p class="watch-when">' + esc(when(n.createdAt)) +
          (n.read ? '' : ' <span class="watch-new">New</span>') + '</p>' +
        '<ul class="watch-changes">' +
          changes.map(function (c) { return '<li>' + line(c) + '</li>'; }).join('') +
        '</ul></li>';
    }).join('');

    panel.hidden = false;
    if (markBtn) markBtn.hidden = data.unread === 0;
  }

  function load() {
    fetch(origin + '/api/notifications', { credentials: 'include' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) render(data); })
      .catch(function () { /* offline — the panel just stays hidden */ });
  }

  if (markBtn) {
    markBtn.addEventListener('click', function () {
      markBtn.hidden = true;
      fetch(origin + '/api/notifications', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'read' })
      }).then(load).catch(load);
    });
  }

  // Only signed-in people have notifications, so wait until we know.
  if (window.spareChangeSession) {
    window.spareChangeSession.then(function (user) { if (user) load(); });
  }
})();

/* Recently removed, with a way back.
 *
 * The removal itself is recorded by saved.js; this only draws it. Names are
 * resolved from the same two data files the rest of the page uses, so a
 * restored entry reads as the school or professor it is rather than as a slug.
 * An id that no longer resolves -- a program dropped from the tracker since --
 * still gets a row, because the point is to let somebody put back a thing they
 * did not mean to lose, and a name we can no longer look up is not a reason to
 * hide it from them.
 */
(function () {
  'use strict';

  function ago(ms) {
    var mins = Math.round((Date.now() - ms) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + (mins === 1 ? ' minute ago' : ' minutes ago');
    var hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + (hrs === 1 ? ' hour ago' : ' hours ago');
    var days = Math.round(hrs / 24);
    return days + (days === 1 ? ' day ago' : ' days ago');
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function titleCase(id) {
    return id.split('-').map(function (w) {
      return w ? w[0].toUpperCase() + w.slice(1) : w;
    }).join(' ');
  }

  function render(programs, profs) {
    var S = window.TCPSaved;
    var box = document.getElementById('removed-box');
    var list = document.getElementById('removed-list');
    if (!S || !S.recentlyRemoved || !box || !list) return;

    var rows = S.recentlyRemoved();
    if (!rows.length) { box.hidden = true; return; }

    list.innerHTML = rows.map(function (r) {
      var label;
      if (r.kind === 'professor') {
        var pr = profs[r.id];
        label = pr ? pr.name + ' \u00b7 ' + pr.school : titleCase(r.id);
      } else {
        var pg = programs[r.id];
        label = pg ? pg.school : titleCase(r.id);
      }
      return '<li class="removed-item">' +
        '<span>' + esc(label) + '</span>' +
        '<span class="removed-when">' + esc(ago(r.at)) + '</span>' +
        '<button type="button" class="removed-restore" data-kind="' + esc(r.kind) +
        '" data-id="' + esc(r.id) + '">Restore</button></li>';
    }).join('');
    box.hidden = false;

    list.onclick = function (e) {
      var btn = e.target.closest ? e.target.closest('.removed-restore') : null;
      if (!btn) return;
      S.restore(btn.getAttribute('data-kind'), btn.getAttribute('data-id'));
      location.reload();
    };
  }

  function load() {
    var base = '../data/';
    Promise.all([
      fetch(base + 'programs.json').then(function (r) { return r.json(); }),
      fetch(base + 'professors.json').then(function (r) { return r.json(); })
    ]).then(function (res) {
      var pg = {}, pr = {};
      (res[0].programs || []).forEach(function (x) { pg[x.id] = x; });
      ((res[1].professors || res[1]) || []).forEach(function (x) { pr[x.id] = x; });
      render(pg, pr);
    }).catch(function () {
      // The data files failing should not hide the list -- slugs are worse
      // than names but far better than nothing.
      render({}, {});
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
