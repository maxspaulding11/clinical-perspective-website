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
    unverified: 'No page found yet',
    closed:     'Program closed this cycle'
  };

  function nameList(names) {
    if (!names || !names.length) return '';
    return '<div class="fac-group">' +
      '<p class="fac-group-label yes">Accepting students</p>' +
      '<ul class="fac-names">' +
        names.map(n => '<li class="yes">' + esc(n) + '</li>').join('') +
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
          badge +
        '</div>' +
      '</div>' +
      nameList(p.accepting) +
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
        '<button type="button" class="star-btn is-saved" data-remove-prof="' + esc(p.id) + '" ' +
          'aria-label="Remove from my list" title="Remove from my list">★</button>' +
      '</div>' +
      '<ul class="prof-interests">' + interests + '</ul>' +
      '<div class="fac-foot">' +
        '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">View their university page →</a>' +
        (p.checked ? '<span class="fac-checked">Checked ' + esc(p.checked) + '</span>' : '') +
      '</div>' +
    '</li>';
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

    renderSchools(programs);
    renderProfs(professors);

    $('#saved-schools-list').addEventListener('click', e => {
      const btn = e.target.closest('[data-remove-school]');
      if (!btn) return;
      window.TCPSaved.removeSchool(btn.dataset.removeSchool);
      renderSchools(programs);
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
