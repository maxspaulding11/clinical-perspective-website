/* ============================================================
   Find a professor by research interest — renders data/professors.json
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  const STATUS_LABEL = {
    pending:    'List not posted yet',
    unverified: 'Not checked by us yet',
    closed:     'Program closed this cycle'
  };

  // Names in programs.json's accepting/maybe/notAccepting lists sometimes carry
  // credentials, parenthetical notes ("(Affiliated Faculty)"), or a hyphenated/
  // double surname a professor's own record doesn't split the same way —
  // normalize both sides the same way before comparing so those don't miss.
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
  // the program — this alone resolves a nickname like "Katie" for "Katherine"
  // as long as only one person there shares that surname); surname + first-
  // name prefix tiebreak when there's more than one; and finally a small
  // edit-distance fallback for genuine spelling variants between the sources.
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

  let DATA = { professors: [] };
  let query = '';

  function matches(p) {
    if (!query) return true;
    return p._hay.indexOf(query) !== -1;
  }

  function starBtn(p) {
    const saved = window.TCPSaved && window.TCPSaved.isProfSaved(p.id);
    return '<button type="button" class="star-btn' + (saved ? ' is-saved' : '') + '" ' +
      'data-star-prof="' + esc(p.id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '" ' +
      'aria-label="' + (saved ? 'Remove from my list' : 'Save to my list') + '" ' +
      'title="' + (saved ? 'Saved — click to remove' : 'Save to my list') + '">' +
      (saved ? '★' : '☆') + '</button>';
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

  function card(p) {
    const interests = (p.interests || [])
      .map(i => '<li>' + esc(i) + '</li>')
      .join('');

    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.name) + '</h3>' +
          '<p class="fac-sub">' + esc(p.school) + (p.program ? ' · ' + esc(p.program) : '') + '</p>' +
        '</div>' +
        '<div class="fac-head-right">' + starBtn(p) + acceptingBadge(p) + '</div>' +
      '</div>' +
      '<ul class="prof-interests">' + interests + '</ul>' +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">View their university page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  function render() {
    const list = $('#prof-list');
    const shown = DATA.professors.filter(matches);

    $('#prof-showing').textContent = query
      ? 'Showing ' + shown.length + ' of ' + DATA.professors.length + ' professors'
      : '';

    list.innerHTML = shown.length
      ? shown.map(card).join('')
      : '<li class="fac-empty">Nothing matches that search.</li>';
  }

  function boot(data, programs) {
    const programIndex = {};
    (programs || []).forEach(rec => {
      programIndex[rec.school + '|||' + rec.program] = rec;
    });

    data.professors.forEach(prof => {
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
    (programs || []).filter(rec => rec.status === 'posted').forEach(rec => {
      [['accepting', 'accepting'], ['maybe', 'maybe'], ['notAccepting', 'not-accepting']].forEach(([field, status]) => {
        (rec[field] || []).forEach(name => {
          const id = findProfId(rec.school, rec.program, name);
          if (id) statusByProfId[id] = status;
        });
      });
    });

    data.professors.sort((a, b) => a.name.localeCompare(b.name));
    data.professors.forEach(p => {
      p._hay = [p.name, p.school, p.program, ...(p.interests || [])].join(' ').toLowerCase();
      p._prog = programIndex[p.school + '|||' + p.program] || null;
    });
    DATA = data;
    const schools = new Set(data.professors.map(p => p.school));
    $('#prof-stats').innerHTML =
      '<strong>' + data.professors.length + '</strong> professors across <strong>' +
      schools.size + '</strong> programs · last updated ' + esc(data.updated || '');
    render();
  }

  Promise.all([
    fetch('../data/professors.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch('../data/programs.json').then(r => r.ok ? r.json() : { programs: [] }).catch(() => ({ programs: [] }))
  ])
    .then(([profData, progData]) => boot(profData, progData.programs))
    .catch(() => {
      $('#prof-list').innerHTML =
        '<li class="fac-empty">Could not load the professor list. Please refresh.</li>';
    });

  $('#prof-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    render();
  });

  $('#prof-list').addEventListener('click', e => {
    const btn = e.target.closest('[data-star-prof]');
    if (!btn || !window.TCPSaved) return;
    const saved = window.TCPSaved.toggleProf(btn.dataset.starProf);
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  });

  document.addEventListener('tcp-saved-synced', render);
})();
