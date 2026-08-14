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

  const STATUS_LABEL = {
    posted:     'List posted',
    pending:    'Not posted yet',
    unverified: 'No page found yet',
    closed:     'Program closed this cycle'
  };

  function matches(p) {
    if (accred === 'pcsas' && !p.pcsas) return false;
    if (statusFilter === 'posted'  && p.status !== 'posted')  return false;
    if (statusFilter === 'pending' && p.status === 'posted')  return false;
    if (!query) return true;
    const hay = [p.school, p.program, p.state,
                 ...(p.accepting || []), ...(p.maybe || [])].join(' ').toLowerCase();
    return hay.indexOf(query) !== -1;
  }

  function nameList(names, cls, label) {
    if (!names || !names.length) return '';
    return '<div class="fac-group">' +
      '<p class="fac-group-label ' + cls + '">' + label + '</p>' +
      '<ul class="fac-names">' +
        names.map(n => '<li class="' + cls + '">' + esc(n) + '</li>').join('') +
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
      nameList(p.accepting, 'yes', 'Accepting students') +
      nameList(p.maybe, 'maybe', 'Undecided — contact directly') +
      nameList(p.notAccepting, 'no', 'Not accepting this cycle') +
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
    render();
  }

  fetch('../data/programs.json')
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(boot)
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
    const btn = e.target.closest('[data-star-school]');
    if (!btn || !window.TCPSaved) return;
    const saved = window.TCPSaved.toggleSchool(btn.dataset.starSchool);
    btn.classList.toggle('is-saved', saved);
    btn.setAttribute('aria-pressed', String(saved));
    btn.setAttribute('aria-label', saved ? 'Remove from my list' : 'Save to my list');
    btn.title = saved ? 'Saved — click to remove' : 'Save to my list';
    btn.textContent = saved ? '★' : '☆';
  });

  document.addEventListener('tcp-saved-synced', render);
})();
