/* ============================================================
   Find a measure by diagnosis — renders data/measures.json
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

  const ACCESS_CLASS = {
    'free': 'posted',
    'registration': 'pending',
    'licensed': 'unverified'
  };

  function accessInfo(access) {
    const a = (access || '').toLowerCase();
    if (a.indexOf('public domain') !== -1 || (a.indexOf('free') !== -1 && a.indexOf('registration') === -1)) {
      return { cls: ACCESS_CLASS.free, label: 'Free to use' };
    }
    if (a.indexOf('registration') !== -1) {
      return { cls: ACCESS_CLASS.registration, label: 'Free with registration' };
    }
    if (a.indexOf('copyright') !== -1 || a.indexOf('licen') !== -1 || a.indexOf('purchase') !== -1) {
      return { cls: ACCESS_CLASS.licensed, label: 'Licensed / purchase required' };
    }
    return { cls: 'unverified', label: access || 'Access unknown' };
  }

  let DATA = { measures: [] };
  let query = '';
  let category = '';

  function matches(m) {
    if (category && m.categories.indexOf(category) === -1) return false;
    if (!query) return true;
    return m._hay.indexOf(query) !== -1;
  }

  function card(m) {
    const access = accessInfo(m.access);
    const subParts = [m.categories.join(', ')];
    if (m.population) subParts.push(m.population);
    if (m.items) subParts.push(m.items + ' items');

    return '<li class="fac-card">' +
      '<div class="fac-head">' +
        '<div>' +
          '<h3>' + esc(m.name) + (m.fullName ? ' <span class="measure-full">— ' + esc(m.fullName) + '</span>' : '') + '</h3>' +
          '<p class="fac-sub">' + esc(subParts.join(' · ')) + '</p>' +
        '</div>' +
        '<span class="fac-badge ' + access.cls + '">' + esc(access.label) + '</span>' +
      '</div>' +
      (m.description ? '<p class="measure-desc">' + esc(m.description) + '</p>' : '') +
      (m.citation ? '<p class="fac-quote">' + esc(m.citation) + '</p>' : '') +
      '<div class="fac-foot">' +
        (m.url ? '<a href="' + esc(m.url) + '" target="_blank" rel="noopener">Official source →</a>' : '<span></span>') +
        (m.citation ? '<button type="button" class="cite-link" data-copy-citation="' + esc(m.citation) + '">Copy citation</button>' : '') +
      '</div>' +
    '</li>';
  }

  function render() {
    const list = $('#measures-list');
    const shown = DATA.measures.filter(matches);

    $('#measures-showing').textContent = (query || category)
      ? 'Showing ' + shown.length + ' of ' + DATA.measures.length + ' measures'
      : '';

    list.innerHTML = shown.length
      ? shown.map(card).join('')
      : '<li class="fac-empty">Nothing matches that search.</li>';
  }

  function renderCategoryFilters() {
    const cats = new Set();
    DATA.measures.forEach(m => (m.categories || []).forEach(c => cats.add(c)));
    const sorted = Array.from(cats).sort((a, b) => a.localeCompare(b));

    const select = $('#measures-category');
    select.innerHTML = '<option value="">All categories</option>' +
      sorted.map(c => '<option value="' + esc(c) + '">' + esc(c) + '</option>').join('');
  }

  function toast(msg) {
    const t = $('#measures-toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('show'), 2000);
  }

  function boot(data) {
    data.measures.sort((a, b) => a.name.localeCompare(b.name));
    data.measures.forEach(m => {
      m._hay = [m.name, m.fullName, m.description, ...(m.categories || [])].join(' ').toLowerCase();
    });
    DATA = data;
    const cats = new Set();
    data.measures.forEach(m => (m.categories || []).forEach(c => cats.add(c)));
    $('#measures-stats').innerHTML =
      '<strong>' + data.measures.length + '</strong> measures across <strong>' +
      cats.size + '</strong> categories · last updated ' + esc(data.updated || '');
    renderCategoryFilters();
    render();
  }

  fetch('../data/measures.json')
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(boot)
    .catch(() => {
      $('#measures-list').innerHTML =
        '<li class="fac-empty">Could not load the measures list. Please refresh.</li>';
    });

  $('#measures-search').addEventListener('input', e => {
    query = e.target.value.trim().toLowerCase();
    render();
  });

  $('#measures-category').addEventListener('change', e => {
    category = e.target.value;
    render();
  });

  $('#measures-list').addEventListener('click', e => {
    const btn = e.target.closest('[data-copy-citation]');
    if (!btn) return;
    navigator.clipboard.writeText(btn.dataset.copyCitation)
      .then(() => toast('Citation copied.'))
      .catch(() => toast('Copy blocked by your browser.'));
  });
})();
