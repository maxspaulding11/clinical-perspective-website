/* ============================================================
   Citation builder — UI wiring for citations.html
   All formatting logic lives in js/apa.js (window.APA).
   ============================================================ */
(function () {
  'use strict';

  const $ = s => document.querySelector(s);
  const STORE = 'tcp-citations-v1';

  const state = { refs: [], editing: null, manual: APA.newRef() };

  /* ---------- feedback ---------- */
  function toast(msg) {
    const t = $('#cite-toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('show'), 2000);
  }
  function setStatus(msg, cls) {
    const n = $('#cite-status');
    n.textContent = msg;
    n.className = 'cite-status' + (cls ? ' ' + cls : '');
  }

  /* ---------- persistence (this browser only) ---------- */
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify(state.refs)); } catch (e) { /* full or blocked */ }
  }
  function load() {
    try {
      const d = JSON.parse(localStorage.getItem(STORE) || '[]');
      if (Array.isArray(d)) state.refs = d;
    } catch (e) { state.refs = []; }
  }

  /* ---------- look-up ---------- */
  async function doLookup() {
    const lines = $('#cite-input').value.split('\n').map(s => s.trim()).filter(Boolean);
    if (!lines.length) { setStatus('Paste a DOI, PubMed ID or ISBN first.', 'err'); return; }

    const btn = $('#cite-lookup');
    btn.disabled = true;
    btn.textContent = 'Looking up…';
    let added = 0;
    const errors = [];

    for (const line of lines) {
      try {
        const r = await APA.lookupOne(line);
        if (!r) continue;
        if (!r.title) { errors.push('No title returned for "' + line.slice(0, 40) + '"'); continue; }

        /* CrossRef lower-cases DOIs; keep the publisher's capitalisation. */
        const typed = APA.parseQuery(line);
        if (typed && typed.kind === 'doi' && r.doi &&
            typed.value.toLowerCase() === r.doi.toLowerCase()) r.doi = typed.value;

        if ($('#cite-sentence').checked &&
            ['article', 'chapter', 'book', 'report', 'thesis'].indexOf(r.type) !== -1)
          r.title = APA.toSentenceCase(r.title);

        if (state.refs.some(x => x.doi && r.doi && x.doi.toLowerCase() === r.doi.toLowerCase())) {
          errors.push('Already in your list: ' + r.title.slice(0, 36) + '…');
          continue;
        }
        state.refs.push(r);
        added++;
      } catch (e) {
        errors.push(/fetch|Failed|NetworkError/i.test(e.message)
          ? 'Could not reach the look-up service — check your connection.'
          : e.message);
      }
    }

    btn.disabled = false;
    btn.textContent = 'Look up & add';
    if (added) $('#cite-input').value = '';
    setStatus((added ? 'Added ' + added + '. ' : '') + errors.join(' · '), errors.length ? 'err' : 'ok');
    renderRefs();
    save();
  }

  /* ---------- manual entry form ---------- */
  const FIELDS = {
    article: [['title','Article title'],['container','Journal name'],['volume','Volume'],['issue','Issue'],
              ['pages','Pages'],['doi','DOI'],['url','URL (if no DOI)']],
    book:    [['title','Book title'],['edition','Edition (e.g. 3rd)'],['publisher','Publisher'],['doi','DOI'],['url','URL']],
    chapter: [['title','Chapter title'],['container','Book title'],['pages','Page range'],['publisher','Publisher'],['doi','DOI'],['url','URL']],
    webpage: [['title','Page title'],['container','Site name'],['date','Month and day (e.g. March 4)'],['url','URL']],
    report:  [['title','Report title'],['number','Report number'],['publisher','Publishing organisation'],['doi','DOI'],['url','URL']],
    thesis:  [['title','Thesis title'],['number','Type (e.g. Doctoral dissertation)'],['publisher','Institution'],['url','URL']]
  };
  const TYPE_LABEL = { article:'Journal article', book:'Book', chapter:'Book chapter',
                       webpage:'Web page', report:'Report', thesis:'Thesis / dissertation' };

  function editForm(r) {
    const rows = FIELDS[r.type] || FIELDS.article;
    const val = k => APA.escHtml(r[k] || '');
    const people = list => (list || [])
      .map(a => a.literal || (a.family + (a.given ? ', ' + a.given : ''))).join('; ');

    return '<div class="cite-form" data-form="' + r.id + '">' +
      '<div class="cite-field"><label>Source type</label><select data-f="type">' +
        Object.keys(TYPE_LABEL).map(k =>
          '<option value="' + k + '"' + (r.type === k ? ' selected' : '') + '>' + TYPE_LABEL[k] + '</option>'
        ).join('') +
      '</select></div>' +
      '<div class="cite-field"><label>Authors <span>— “Surname, First M.”, separated by semicolons. ' +
        'Use a single name alone for an organisation.</span></label>' +
        '<input type="text" data-f="authors" value="' + APA.escHtml(people(r.authors)) + '"></div>' +
      (r.type === 'chapter'
        ? '<div class="cite-field"><label>Editors <span>— same format</span></label>' +
          '<input type="text" data-f="editors" value="' + APA.escHtml(people(r.editors)) + '"></div>'
        : '') +
      '<div class="cite-two">' +
        '<div class="cite-field"><label>Year</label>' +
          '<input type="text" data-f="year" value="' + val('year') + '" placeholder="2024 or n.d."></div>' +
        rows.slice(0, 1).map(f =>
          '<div class="cite-field"><label>' + f[1] + '</label>' +
          '<input type="text" data-f="' + f[0] + '" value="' + val(f[0]) + '"></div>').join('') +
      '</div>' +
      '<div class="cite-two">' +
        rows.slice(1).map(f =>
          '<div class="cite-field"><label>' + f[1] + '</label>' +
          '<input type="text" data-f="' + f[0] + '" value="' + val(f[0]) + '"></div>').join('') +
      '</div>' +
      '<div class="cite-row">' +
        '<button class="btn btn-primary btn-small" data-save="' + r.id + '">Save</button>' +
        '<button class="btn btn-secondary btn-small" data-cancel="1">Cancel</button>' +
        '<button class="btn btn-secondary btn-small" data-sentence="' + r.id + '">Sentence-case title</button>' +
      '</div>' +
    '</div>';
  }

  function readForm(form, r) {
    form.querySelectorAll('[data-f]').forEach(inp => {
      const k = inp.dataset.f, v = inp.value.trim();
      if (k === 'authors' || k === 'editors') r[k] = APA.parsePeople(v);
      else r[k] = v;
    });
    return r;
  }

  /* ---------- rendering ---------- */
  function renderRefs() {
    const list = $('#cite-refs');
    const n = state.refs.length;
    $('#cite-count').textContent = n ? '(' + n + ')' : '';
    $('#cite-actions').hidden = !n;

    if (!n) {
      list.innerHTML = '<li class="cite-empty">No references yet — add your first source above.</li>';
      return;
    }
    list.innerHTML = APA.sortRefs(state.refs).map(r =>
      '<li data-id="' + r.id + '">' +
        '<p class="cite-ref">' + APA.formatRef(r) + '</p>' +
        (r.warn ? '<p class="cite-warn">' + APA.escHtml(r.warn) + '</p>' : '') +
        '<div class="cite-meta">' +
          '<button class="cite-chip" data-copy="' + APA.escHtml(APA.inText(r, false)) + '" ' +
            'title="Copy parenthetical citation">' + APA.escHtml(APA.inText(r, false)) + '</button>' +
          '<button class="cite-chip" data-copy="' + APA.escHtml(APA.inText(r, true)) + '" ' +
            'title="Copy narrative citation">' + APA.escHtml(APA.inText(r, true)) + '</button>' +
          '<span class="cite-spacer"></span>' +
          '<button class="cite-link" data-copyref="' + r.id + '">Copy</button>' +
          '<button class="cite-link" data-edit="' + r.id + '">Edit</button>' +
          '<button class="cite-link danger" data-del="' + r.id + '">Remove</button>' +
        '</div>' +
        (state.editing === r.id ? editForm(r) : '') +
      '</li>'
    ).join('');
  }

  function renderManual() { $('#cite-manual-box').innerHTML = editForm(state.manual); }

  /* ---------- clipboard ---------- */
  function copyRich(html, plain) {
    const d = document.createElement('div');
    d.contentEditable = 'true';
    d.innerHTML = html;
    d.style.cssText = 'position:fixed;left:-9999px;top:0;';
    document.body.appendChild(d);
    const range = document.createRange();
    range.selectNodeContents(d);
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    sel.removeAllRanges();
    d.remove();
    if (!ok && plain) navigator.clipboard.writeText(plain).catch(() => {});
  }

  /* ---------- events ---------- */
  $('#cite-lookup').addEventListener('click', doLookup);
  $('#cite-input').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doLookup(); }
  });

  $('#cite-refs').addEventListener('click', e => {
    const copy = e.target.closest('[data-copy]');
    if (copy) {
      navigator.clipboard.writeText(copy.dataset.copy)
        .then(() => toast('In-text citation copied.'))
        .catch(() => toast('Copy blocked by your browser.'));
      return;
    }
    const copyRef = e.target.closest('[data-copyref]');
    if (copyRef) {
      const r = state.refs.find(x => x.id === copyRef.dataset.copyref);
      copyRich('<p>' + APA.formatRef(r) + '</p>', APA.refToPlain(r));
      toast('Reference copied.');
      return;
    }
    const del = e.target.closest('[data-del]');
    if (del) {
      state.refs = state.refs.filter(x => x.id !== del.dataset.del);
      if (state.editing === del.dataset.del) state.editing = null;
      renderRefs(); save(); toast('Removed.');
      return;
    }
    const ed = e.target.closest('[data-edit]');
    if (ed) {
      state.editing = state.editing === ed.dataset.edit ? null : ed.dataset.edit;
      renderRefs();
      return;
    }
    const sv = e.target.closest('[data-save]');
    if (sv) {
      const form = document.querySelector('[data-form="' + sv.dataset.save + '"]');
      const r = state.refs.find(x => x.id === sv.dataset.save);
      if (form && r) { readForm(form, r); r.warn = ''; }
      state.editing = null;
      renderRefs(); save(); toast('Reference updated.');
      return;
    }
    if (e.target.closest('[data-cancel]')) { state.editing = null; renderRefs(); return; }
    const sc = e.target.closest('[data-sentence]');
    if (sc) {
      const form = document.querySelector('[data-form="' + sc.dataset.sentence + '"]');
      const inp = form && form.querySelector('[data-f="title"]');
      if (inp) inp.value = APA.toSentenceCase(inp.value);
    }
  });

  /* Changing the type in an open edit form re-renders its fields. */
  $('#cite-refs').addEventListener('change', e => {
    const sel = e.target.closest('[data-f="type"]');
    if (!sel) return;
    const r = state.refs.find(x => x.id === state.editing);
    if (!r) return;
    readForm(sel.closest('[data-form]'), r);   // keep what's already typed
    r.type = sel.value;
    renderRefs();
  });

  $('#cite-manual-box').addEventListener('change', e => {
    const sel = e.target.closest('[data-f="type"]');
    if (!sel) return;
    readForm(sel.closest('[data-form]'), state.manual);
    state.manual.type = sel.value;
    renderManual();
  });

  $('#cite-manual-box').addEventListener('click', e => {
    if (e.target.closest('[data-save]')) {
      const form = $('#cite-manual-box').querySelector('[data-form]');
      readForm(form, state.manual);
      if (!state.manual.title) { toast('Give the source a title first.'); return; }
      state.refs.push(state.manual);
      state.manual = APA.newRef();
      renderManual(); renderRefs(); save();
      $('#cite-manual').open = false;
      toast('Reference added.');
      return;
    }
    if (e.target.closest('[data-cancel]')) {
      state.manual = APA.newRef();
      renderManual();
      $('#cite-manual').open = false;
      return;
    }
    const sc = e.target.closest('[data-sentence]');
    if (sc) {
      const inp = $('#cite-manual-box').querySelector('[data-f="title"]');
      if (inp) inp.value = APA.toSentenceCase(inp.value);
    }
  });

  /* ---------- exports ---------- */
  $('#cite-docx').addEventListener('click', () => {
    if (!state.refs.length) { toast('Nothing to export yet.'); return; }
    try {
      APA.downloadBlob(APA.buildReferencesDocx(state.refs), 'References (APA 7).docx');
      toast('Word document downloaded.');
    } catch (e) {
      toast('Could not build the document.');
    }
  });
  $('#cite-copy').addEventListener('click', () => {
    if (!state.refs.length) { toast('Nothing to copy yet.'); return; }
    copyRich(APA.refsToHtml(state.refs), APA.refsToPlain(state.refs));
    toast('Copied ' + state.refs.length + ' reference' + (state.refs.length === 1 ? '' : 's') + '.');
  });
  $('#cite-clear').addEventListener('click', () => {
    if (state.refs.length && confirm('Delete all ' + state.refs.length + ' references? This cannot be undone.')) {
      state.refs = [];
      state.editing = null;
      renderRefs(); save();
    }
  });

  /* ---------- boot ---------- */
  load();
  renderRefs();
  renderManual();
})();
