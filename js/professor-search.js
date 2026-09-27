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
    cohort:     'Admits by cohort — no mentor list',
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

  // Shared by the click handler and by the saved-list sync, so the two cannot
  // drift apart on what a saved star looks like.
  function paintStar(btn, saved) {
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  }

  // Correct the stars already on screen instead of rebuilding the list.
  //
  // Same defect the tracker had: this page ships its cards pre-rendered with
  // every star empty, because the HTML is one document served to everybody,
  // and the real saved list arrives later from a fetch to another origin.
  // Re-rendering on arrival tore down and rebuilt every card well after first
  // paint -- and there are 2,647 names here, so it is the larger of the two.
  // Nothing in that sync changes which professors match or what a card says.
  function repaintSaved() {
    if (!window.TCPSaved) return;
    document.querySelectorAll('#prof-list [data-star-prof]').forEach(b => {
      paintStar(b, window.TCPSaved.isProfSaved(b.dataset.starProf));
    });
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

  // The pre-render writes this link on every card and it was being thrown away:
  // rebuilding the list dropped all 2,672 of them, so the one route from a
  // professor to their program's accepting-students entry existed in the HTML
  // and vanished a moment after the page loaded. It is also the reason
  // render_professors.py does not pre-render the badge -- "the answer is one
  // click away" only holds while the link survives the rebuild.
  function trackerLink(p) {
    const rec = p._prog;
    if (!rec) return '';
    return '<a class="prof-tracker-link" ' +
      'href="faculty-accepting-students.html#program-' + esc(rec.id) + '">' +
      'Accepting-students status →</a>';
  }

  // Split from card() because the first pass fills the pre-rendered cards in
  // place rather than replacing them, and so needs the innards without the
  // <li>. Anything added here must also be added to full_card() in
  // scripts/render_professors.py, or the first screenful will change height
  // when this runs.
  function cardInner(p) {
    const interests = (p.interests || [])
      .map(i => '<li>' + esc(i) + '</li>')
      .join('');

    return '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.name) + '</h3>' +
          '<p class="fac-sub">' + esc(p.school) + (p.program ? ' · ' + esc(p.program) : '') + '</p>' +
        '</div>' +
        '<div class="fac-head-right">' + starBtn(p) + acceptingBadge(p) + '</div>' +
      '</div>' +
      '<ul class="prof-interests">' + interests + '</ul>' +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">View their university page →</a>' +
        trackerLink(p) +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>';
  }

  function card(p) {
    // Keep the id the pre-render writes, so a link to one professor still
    // resolves after this script replaces the list.
    return '<li class="fac-card" id="prof-' + esc(p.id) + '">' + cardInner(p) + '</li>';
  }

  // Note for anyone tempted to skip the first render here the way faculty.js
  // does: you cannot. The tracker's pre-rendered cards are complete, so
  // keeping the server's markup loses nothing. These are not -- to keep this
  // page's HTML down, scripts/render_professors.py deliberately ships most
  // cards without their research interests, star or accepting badge, and this
  // script is what adds them. Skipping the work entirely would leave the page
  // permanently missing all three.
  //
  // So the first pass is a real content change, not a redundant one, and it
  // was the larger part of this page's layout shift. The note that used to sit
  // here said fixing it meant either shipping every interest in the HTML
  // (131KB gzipped to 304KB -- the 227KB-to-9KB work deliberately stopped
  // doing that) or reserving the height the cards grow to, which cannot be
  // done honestly because an interest wraps to one line or two depending on
  // the viewport.
  //
  // There is a third option both of those missed: a shift only counts against
  // CLS if it happens inside the viewport, so only the first screenful has to
  // ship complete. render_professors.py now pre-renders FULL_CARDS of them in
  // full and the rest lean, and enhanceInPlace fills the lean ones where they
  // already sit. The cards that grow are all below the fold, and the ones in
  // view are byte-identical to what cardInner would have produced, so filling
  // them changes nothing. Cost of the complete ones: under 4KB gzipped.
  function render() {
    const list = $('#prof-list');
    const shown = DATA.professors.filter(matches);

    $('#prof-showing').textContent = query
      ? 'Showing ' + shown.length + ' of ' + DATA.professors.length + ' professors'
      : '';

    renderList(list, shown);
  }

  // How many cards go in on the first pass, and how many per batch after.
  // FIRST_CHUNK only has to cover a tall screen; the rest can arrive after.
  const FIRST_CHUNK = 150;
  const CHUNK = 250;
  let appendTimer = 0;

  // Build the visible part now and the rest in batches.
  //
  // Debouncing alone does not save this page: one render of all 2,647 cards
  // measured 890-1,010ms here, so even a single keystroke after the pause
  // froze the tab for about a second. The first 150 cards are already far more
  // than a screenful, so they go in immediately and the remainder is appended
  // in batches between frames.
  //
  // Appending only ever adds below what is already there, so nothing visible
  // moves and this does not trade the INP problem for a CLS one. Any new query
  // cancels a batch run still in flight, otherwise the old results would keep
  // arriving underneath the new ones.
  // Fill the pre-rendered cards where they already are.
  //
  // The list arrives from the server with every card in place, so there is
  // nothing to add or remove -- only innards to complete. Replacing each
  // card's contents instead of the list's means no card is ever detached, the
  // page never collapses to a fraction of its height and back, and the cards
  // that do grow taller are the lean ones below the fold. Chunked for the same
  // reason renderList is: doing all 2,672 in one pass measured about a second
  // of blocked main thread.
  function enhanceInPlace(list) {
    clearTimeout(appendTimer);
    const byId = {};
    DATA.professors.forEach(p => { byId['prof-' + p.id] = p; });
    // Matched by id rather than by position: this script sorts with
    // localeCompare and the pre-render sorts with Python's lower(), which do
    // not agree on every name, and a mismatch here would put the wrong
    // interests under a name.
    const cards = Array.prototype.slice.call(list.children);
    let i = 0;
    (function fillMore() {
      const end = Math.min(i + CHUNK, cards.length);
      for (; i < end; i++) {
        const p = byId[cards[i].id];
        if (p) cards[i].innerHTML = cardInner(p);
      }
      if (i < cards.length) { appendTimer = setTimeout(fillMore, 0); }
      else { repaintSaved(); }
    })();
  }

  function renderList(list, shown) {
    clearTimeout(appendTimer);
    if (!shown.length) {
      list.innerHTML = '<li class="fac-empty">Nothing matches that search.</li>';
      return;
    }
    list.innerHTML = shown.slice(0, FIRST_CHUNK).map(card).join('');
    let i = FIRST_CHUNK;
    (function appendMore() {
      if (i >= shown.length) return;
      appendTimer = setTimeout(() => {
        list.insertAdjacentHTML('beforeend',
          shown.slice(i, i + CHUNK).map(card).join(''));
        i += CHUNK;
        appendMore();
      }, 0);
    })();
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

    // Fill the server's cards in place when they are all still there. A query
    // typed before the JSON landed, or a pre-render that is out of step with
    // the JSON, both fall through to a normal render.
    const list = $('#prof-list');
    if (!query && list.querySelectorAll('.fac-card').length === data.professors.length) {
      $('#prof-showing').textContent = '';
      enhanceInPlace(list);
    } else {
      render();
    }
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

  // Same reasoning as the tracker: the handler records the query and returns,
  // so the typed character paints without waiting for 2,647 cards.
  let filterTimer = 0;

  $('#prof-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    clearTimeout(filterTimer);
    filterTimer = setTimeout(render, 160);
  });

  $('#prof-list').addEventListener('click', e => {
    const btn = e.target.closest('[data-star-prof]');
    if (!btn || !window.TCPSaved) return;
    paintStar(btn, window.TCPSaved.toggleProf(btn.dataset.starProf));
  });

  // Repaint, do not re-render: this fires after a cross-origin fetch, long
  // past first paint, and rebuilding 2,647 cards there shifted the page.
  document.addEventListener('tcp-saved-synced', repaintSaved);
})();
