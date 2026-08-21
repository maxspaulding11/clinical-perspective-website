/* ============================================================
   Faculty accepting doctoral students — renders data/programs.json
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  let DATA = { programs: [] };
  let query = '';
  let accred = 'apa';
  let statusFilter = 'all';
  let profByExactKey = {};
  let profByLastKey = {};
  let profsBySchoolProgram = {};

  const STATUS_LABEL = {
    posted:     'List posted',
    pending:    'Not posted yet',
    unverified: 'No page found yet',
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
    return nameTokens(s).slice(1);
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
      const close = pool.filter(c => {
        const cSurnames = c.surnameTokens;
        return cSurnames.some(t => levenshtein(t, lastTok) <= 2);
      });
      if (close.length === 1) return close[0].id;
    }
    return null;
  }

  function matches(p) {
    if (accred === 'pcsas' && !p.pcsas) return false;
    if (statusFilter === 'posted'  && p.status !== 'posted')  return false;
    if (statusFilter === 'pending' && p.status === 'posted')  return false;
    if (!query) return true;
    const hay = [p.school, p.program, p.state,
                 ...(p.accepting || []), ...(p.maybe || [])].join(' ').toLowerCase();
    return hay.indexOf(query) !== -1;
  }

  function profStarBtn(id) {
    const saved = window.TCPSaved && window.TCPSaved.isProfSaved(id);
    return '<button type="button" class="star-btn star-btn-sm' + (saved ? ' is-saved' : '') + '" ' +
      'data-star-prof="' + esc(id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '" ' +
      'aria-label="' + (saved ? 'Remove from my list' : 'Save professor to my list') + '" ' +
      'title="' + (saved ? 'Saved — click to remove' : 'Save to my list') + '">' +
      (saved ? '★' : '☆') + '</button>';
  }

  function nameList(names, cls, label, p) {
    if (!names || !names.length) return '';
    return '<div class="fac-group">' +
      '<p class="fac-group-label ' + cls + '">' + label + '</p>' +
      '<ul class="fac-names">' +
        names.map(n => {
          const profId = findProfId(p.school, p.program, n);
          return profId
            ? '<li class="' + cls + ' has-star">' +
                '<span class="fac-name-text">' + esc(n) + '</span>' + profStarBtn(profId) +
              '</li>'
            : '<li class="' + cls + '">' + esc(n) + '</li>';
        }).join('') +
      '</ul></div>';
  }

  function starBtn(p) {
    const saved = window.TCPSaved && window.TCPSaved.isSchoolSaved(p.id);
    return '<button type="button" class="star-btn' + (saved ? ' is-saved' : '') + '" ' +
      'data-star-school="' + esc(p.id) + '" aria-pressed="' + (saved ? 'true' : 'false') + '" ' +
      'aria-label="' + (saved ? 'Remove from my list' : 'Save to my list') + '" ' +
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

  function card(p) {
    const count = (p.accepting || []).length;
    const badge = p.status === 'posted'
      ? '<span class="fac-badge posted">' + count + ' accepting</span>'
      : '<span class="fac-badge ' + p.status + '">' + STATUS_LABEL[p.status] + '</span>';

    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.school) + '</h3>' +
          '<p class="fac-sub">' + esc(p.program) + (p.state ? ' · ' + esc(p.state) : '') +
            (p.pcsas ? ' · <span class="fac-pcsas" title="Accredited by the Psychological Clinical Science Accreditation System">PCSAS accredited</span>' : '') +
          '</p>' +
        '</div>' +
        '<div class="fac-head-right">' + starBtn(p) + badge + '</div>' +
      '</div>' +
      appInfo(p) +
      nameList(p.accepting, 'yes', 'Accepting students', p) +
      nameList(p.maybe, 'maybe', 'Undecided — contact directly', p) +
      nameList(p.notAccepting, 'no', 'Not accepting this cycle', p) +
      (p.note ? '<p class="fac-note">' + esc(p.note) + '</p>' : '') +
      (p.sourceQuote
        ? '<p class="fac-quote">“' + esc(p.sourceQuote) + '”</p>'
        : '') +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">Check the program\'s own page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  function render() {
    const list = $('#fac-list');
    const shown = DATA.programs.filter(matches)
      .sort((a, b) => a.school.localeCompare(b.school));

    $('#fac-showing').textContent = shown.length
      ? 'Showing ' + shown.length + ' of ' + DATA.programs.length + ' programs checked so far'
      : '';

    list.innerHTML = shown.length
      ? shown.map(card).join('')
      : '<li class="fac-empty">Nothing matches that search.</li>';
  }

  function boot(data) {
    DATA = data;
    const posted = data.programs.filter(p => p.status === 'posted');
    const faculty = posted.reduce((n, p) => n + (p.accepting || []).length, 0);

    $('#fac-cycle').textContent = data.cycle || '';
    $('#fac-stats').innerHTML =
      '<strong>' + faculty + '</strong> faculty confirmed accepting across <strong>' +
      posted.length + '</strong> programs · last updated ' + esc(data.updated || '');

    const newlyPosted = data.programs.filter(p => p.newlyPosted).sort((a, b) => a.school.localeCompare(b.school));
    if (newlyPosted.length) {
      $('#fac-new-schools').textContent = newlyPosted.map(p => p.school).join(', ');
      $('#fac-new-banner').hidden = false;
    }

    render();
  }

  Promise.all([
    fetch('../data/programs.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch('../data/professors.json').then(r => r.ok ? r.json() : { professors: [] }).catch(() => ({ professors: [] }))
  ])
    .then(([progData, profData]) => {
      (profData.professors || []).forEach(prof => {
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
      boot(progData);
    })
    .catch(() => {
      $('#fac-list').innerHTML =
        '<li class="fac-empty">Could not load the program list. Please refresh.</li>';
    });

  $('#fac-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    render();
  });
  document.querySelectorAll('[data-accred]').forEach(b => {
    b.addEventListener('click', () => {
      accred = b.dataset.accred;
      document.querySelectorAll('[data-accred]').forEach(x =>
        x.setAttribute('aria-pressed', String(x === b)));
      render();
    });
  });
  document.querySelectorAll('[data-status]').forEach(b => {
    b.addEventListener('click', () => {
      statusFilter = b.dataset.status;
      document.querySelectorAll('[data-status]').forEach(x =>
        x.setAttribute('aria-pressed', String(x === b)));
      render();
    });
  });

  $('#fac-list').addEventListener('click', e => {
    const schoolBtn = e.target.closest('[data-star-school]');
    if (schoolBtn && window.TCPSaved) {
      const saved = window.TCPSaved.toggleSchool(schoolBtn.dataset.starSchool);
      schoolBtn.classList.toggle('is-saved', saved);
      schoolBtn.setAttribute('aria-pressed', String(saved));
      schoolBtn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
      schoolBtn.title = saved ? 'Saved — click to remove' : 'Save to my list';
      schoolBtn.textContent = saved ? '★' : '☆';
      return;
    }
    const profBtn = e.target.closest('[data-star-prof]');
    if (profBtn && window.TCPSaved) {
      const saved = window.TCPSaved.toggleProf(profBtn.dataset.starProf);
      profBtn.classList.toggle('is-saved', saved);
      profBtn.setAttribute('aria-pressed', String(saved));
      profBtn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save professor to my list');
      profBtn.title = saved ? 'Saved — click to remove' : 'Save to my list';
      profBtn.textContent = saved ? '★' : '☆';
    }
  });

  document.addEventListener('tcp-saved-synced', render);
})();
