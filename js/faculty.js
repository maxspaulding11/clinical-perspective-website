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
  // school|||program|||name -> professor id, precomputed by
  // scripts/render_starmap.py. This page used to download data/professors.json
  // (227KB gzipped, mostly research-interest prose) purely to work these out in
  // the browser, and displayed none of the rest of it. The answer is known at
  // build time, so it arrives as a 9KB lookup instead.
  let starMap = {};

  const STATUS_LABEL = {
    posted:     'List posted',
    pending:    'Not posted yet',
    unverified: 'Not checked by us yet',
    cohort:     'Admits by cohort — no mentor list',
    closed:     'Program closed this cycle'
  };

  // One lookup, no matching. The rules that used to run here -- exact
  // normalised compare, surname pass, first-name tiebreak, then an
  // edit-distance fallback -- now run once in scripts/render_starmap.py, so
  // their results can be read from a file instead of recomputed in every
  // visitor's browser. A name with no entry gets no save button, which is what
  // the matcher did too for the few people whose department has not published
  // a page for them.
  function findProfId(school, program, rawName) {
    return starMap[school + '|||' + program + '|||' + rawName] || null;
  }

  function matches(p) {
    if (accred === 'pcsas' && !p.pcsas) return false;
    // each button now means exactly its own status, so 'Awaiting list'
    // no longer sweeps in cohort-admission or closed programs
    if (statusFilter === 'posted'  && p.status !== 'posted')  return false;
    if (statusFilter === 'pending' && p.status !== 'pending') return false;
    if (statusFilter === 'cohort'  && p.status !== 'cohort')  return false;
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

  // One place that knows what a star looks like in each state, used both when
  // somebody clicks one and when the saved list arrives from the account API.
  function paintStar(btn, saved) {
    const prof = btn.hasAttribute('data-star-prof');
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list'
      : (prof ? 'Save professor to my list' : 'Save to my list'));
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  }

  // Correct the stars and bells on the cards that are already on screen,
  // without rebuilding them.
  //
  // This page ships 257 cards pre-rendered, with every star un-starred and
  // every bell off, because the HTML is one document served to everybody --
  // it cannot know who is asking. The saved list arrives later, from a fetch
  // to another origin. Re-rendering the whole list at that point tore down and
  // rebuilt 257 cards a long way after first paint, which is where this page's
  // layout shift came from: Cloudflare measured CLS 0.708 on #fac-list, seven
  // times the threshold for "good", on the page carrying most of the site's
  // search traffic.
  //
  // Nothing about that sync changes which programs match or what a card says.
  // It changes the state of two buttons, so only those are touched.
  //
  // The one case that genuinely needs new markup: somebody watching a program
  // whose list is already posted. The server omits that bell (it cannot know),
  // so it has to be created, and for that rare card a rebuild is still right.
  function repaintSaved() {
    if (!window.TCPSaved) return;
    let missingBell = false;
    document.querySelectorAll('#fac-list .fac-card').forEach(card => {
      const id = card.id.replace(/^program-/, '');
      const school = card.querySelector('[data-star-school]');
      if (school) paintStar(school, window.TCPSaved.isSchoolSaved(id));
      card.querySelectorAll('[data-star-prof]').forEach(b => {
        paintStar(b, window.TCPSaved.isProfSaved(b.dataset.starProf));
      });
      const bell = card.querySelector('[data-watch-school]');
      const on = window.TCPSaved.isWatching(id);
      if (bell) window.TCPSaved.paintWatchButton(bell, on);
      else if (on) missingBell = true;
    });
    if (missingBell) render(true);
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

    // keep the id the pre-render writes, so a link to a single program
    // still resolves after this script replaces the list
    return '<li class="fac-card" id="program-' + esc(p.id) + '">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(p.school) + '</h3>' +
          '<p class="fac-sub">' + esc(p.program) + (p.state ? ' · ' + esc(p.state) : '') +
            (p.pcsas ? ' · <span class="fac-pcsas" title="Accredited by the Psychological Clinical Science Accreditation System">PCSAS accredited</span>' : '') +
          '</p>' +
        '</div>' +
        '<div class="fac-head-right">' + starBtn(p) + window.TCPSaved.watchButtonHTML(p.id, p.status) + badge + '</div>' +
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
        // must match the link the pre-render writes, or it disappears the
        // moment this script re-renders the list for a filter
        '<a href="../programs/' + esc(p.id) + '.html">Full entry →</a>' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">Check the program\'s own page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
  }

  // True until this script has replaced the server's list for the first time.
  let serverList = true;

  function render(force) {
    const list = $('#fac-list');
    const shown = DATA.programs.filter(matches)
      .sort((a, b) => a.school.localeCompare(b.school));

    $('#fac-showing').textContent = shown.length
      ? 'Showing ' + shown.length + ' of ' + DATA.programs.length + ' programs checked so far'
      : '';

    // On the first pass there is no filter or search yet, so this would
    // replace the pre-rendered list with an identical one -- paying a full
    // teardown and rebuild of 257 cards, after first paint, for no visible
    // change. Keep the server's markup and just correct the buttons on it.
    // Any later render (a filter, a search) falls through and rebuilds.
    if (serverList && !force && shown.length === DATA.programs.length &&
        list.querySelectorAll('.fac-card').length === shown.length) {
      serverList = false;
      repaintSaved();
      return;
    }
    serverList = false;

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

    // Same rule as scripts/render_tracker.py, deliberately: a posting counts
    // as news for three weeks and then drops out on its own.
    //
    // The cutoff comes from the build, not from this reader's clock. Computing
    // it here meant the two disagreed as soon as the deployed HTML was a day
    // old -- and disagreeing means hiding a banner the server had shown, which
    // drops the 257-card list below it by the banner's height, on every visit,
    // after first paint. Reading the server's date instead makes that
    // impossible: a stale build now produces a stale banner rather than a
    // moving page. Only fall back to the local clock if the attribute is
    // missing, i.e. the HTML predates this change.
    const banner = $('#fac-new-banner');
    const NEWLY_WINDOW_DAYS = 21;
    const cutoff = (banner && banner.dataset.cutoff) ||
      new Date(Date.now() - NEWLY_WINDOW_DAYS * 86400000)
        .toISOString().slice(0, 10);
    const newlyPosted = data.programs
      .filter(p => p.newlyPostedOn && p.newlyPostedOn >= cutoff)
      // Newest first, then alphabetical inside a date — identical to the order
      // scripts/render_tracker.py writes. If the two disagreed the banner
      // would visibly reorder a moment after the page loaded.
      .sort((a, b) => b.newlyPostedOn.localeCompare(a.newlyPostedOn) ||
                      a.school.localeCompare(b.school));

    if (newlyPosted.length) {
      const since = newlyPosted
        .map(p => p.newlyPostedOn)
        .reduce((a, b) => (a < b ? a : b));
      const parts = since.split('-').map(Number);
      const label = new Date(parts[0], parts[1] - 1, parts[2])
        .toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
      $('#fac-new-label').textContent = 'Newly posted since ' + label + ':';
      // Middle dot, not a comma — three of these school names contain commas.
      $('#fac-new-schools').textContent = newlyPosted.map(p => p.school).join(' · ');
      banner.hidden = false;
    } else {
      banner.hidden = true;
    }

    render();
  }

  // Two files, not three, and the big one is gone: data/professors.json was
  // 227KB gzipped of research interests fetched on every visit to resolve save
  // buttons this page never displayed interests for. data/star-map.json is the
  // same answers at 9KB, and data/name-links.json is no longer needed here
  // either — it is the source the map is built from, not something the browser
  // has to read.
  Promise.all([
    fetch('../data/programs.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch('../data/star-map.json').then(r => r.ok ? r.json() : { map: {} }).catch(() => ({ map: {} }))
  ])
    .then(([progData, mapData]) => {
      // A failed map costs save buttons, not the page: every name still
      // renders, just without a star.
      starMap = mapData.map || {};
      boot(progData);
    })
    .catch(() => {
      $('#fac-list').innerHTML =
        '<li class="fac-empty">Could not load the program list. Please refresh.</li>';
    });

  // Filtering runs on a timer rather than on the keystroke.
  //
  // Rebuilding the matching cards costs ~90ms on a desktop here and the field
  // data put this box at 440ms INP, which is what that becomes on a mid-range
  // phone. Doing it inside the input handler meant every character paid it,
  // and the character itself could not paint until it finished -- so typing
  // "trauma" froze the page six times over. Now the handler only records what
  // was typed, the keystroke paints immediately, and one render runs once the
  // typing pauses.
  let filterTimer = 0;
  function scheduleRender() {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(render, 160);
  }

  $('#fac-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    scheduleRender();
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
      paintStar(schoolBtn, window.TCPSaved.toggleSchool(schoolBtn.dataset.starSchool));
      return;
    }
    if (window.TCPSaved && window.TCPSaved.handleWatchClick(e.target)) return;
    const profBtn = e.target.closest('[data-star-prof]');
    if (profBtn && window.TCPSaved) {
      paintStar(profBtn, window.TCPSaved.toggleProf(profBtn.dataset.starProf));
    }
  });

  // Repaint, do not re-render: this fires after a cross-origin fetch, well
  // past first paint, and rebuilding 257 cards there was the layout shift.
  document.addEventListener('tcp-saved-synced', repaintSaved);
})();
