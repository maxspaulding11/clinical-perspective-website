/* Export the saved list: pick the columns, pick the format.
 *
 * The point of this is the conversation an applicant has with somebody else.
 * A shortlist is the thing you send your undergrad advisor, your lab PI or the
 * group chat, and until now it lived behind a sign-in on one device and could
 * not leave. So it leaves as a file, and the columns are chosen rather than
 * fixed, because what you send a research mentor (who is accepting, whose
 * interests match) is not what you send whoever is helping you budget (fees,
 * deadlines, how many references to line up).
 *
 * Everything is selected by default. Somebody exporting for the first time
 * does not yet know which columns they want, and deleting a column in Word is
 * easier than discovering afterwards that the fee was available all along.
 *
 * No libraries. The site ships no bundler and adding a CDN for this would put
 * a third party in the path of a button that works offline otherwise:
 *   PDF    the browser's own print-to-PDF, against a print stylesheet
 *   Word   an HTML document served as .doc, which Word opens with formatting
 *   Excel  CSV, which Excel, Numbers and Sheets all open without a warning
 *   Google the clipboard, because writing into someone's Drive needs OAuth
 *          and a Drive scope; rich HTML pastes into Docs and TSV lands in
 *          Sheets cells, which is the same result without the permissions
 */
(function () {
  'use strict';

  var FIELDS = [
    { key: 'school', label: 'School name', always: true },
    { key: 'program', label: 'Program' },
    { key: 'state', label: 'State' },
    { key: 'status', label: 'Accepting status' },
    { key: 'starred', label: 'Your starred professors' },
    { key: 'allAccepting', label: 'All faculty listed as accepting', off: true },
    { key: 'deadline', label: 'Application deadline' },
    { key: 'fee', label: 'Application fee' },
    { key: 'refs', label: 'References required' },
    { key: 'gre', label: 'GRE requirement' },
    { key: 'gpa', label: 'GPA guidance' },
    { key: 'other', label: 'Other requirements' },
    { key: 'pcsas', label: 'PCSAS accredited' },
    { key: 'acceptance', label: 'Acceptance rate' },
    { key: 'match', label: 'Internship match rate' },
    { key: 'years', label: 'Years to finish' },
    { key: 'confirmed', label: 'What the school told us' },
    { key: 'deptUrl', label: 'Department link' },
    { key: 'appUrl', label: 'Application info link' },
    { key: 'checked', label: 'Last checked' }
  ];

  var GRE_LABEL = {
    required: 'GRE required',
    optional: 'GRE optional',
    'not required': 'GRE not required',
    'not accepted': 'GRE not accepted',
    'not stated': 'GRE not stated'
  };

  var STATUS_LABEL = {
    posted: 'List posted',
    pending: 'Not posted yet',
    cohort: 'Cohort admission',
    closed: 'Not accepting this cycle',
    unverified: 'Unverified'
  };

  var data = null;      // { programs, profsById, outcomes }
  var modal = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];
  var ANY_DATE = new RegExp('\\b(' + MONTHS.join('|') + ')\\s+(\\d{1,2})\\b', 'gi');

  // Most programs write "December 1", which is clear on their own page and
  // ambiguous on a list spanning two calendar years. scripts/deadline.py adds
  // the year when the site is built, so an export taking the raw field would
  // hand somebody the one thing that was fixed. Same rule here: the intake
  // fixes the year, because nobody takes applications after the class starts.
  function datedDeadline(raw, cycle) {
    if (!raw) return '';
    if (/\b(19|20)\d\d\b/.test(raw)) return raw;         // already dated
    var m = /\b(20\d\d)\b/.exec(cycle || '');
    if (!m) return raw;                                   // no cycle to work from
    var start = parseInt(m[1], 10);
    return raw.replace(ANY_DATE, function (whole, month, day) {
      var n = MONTHS.indexOf(month.charAt(0).toUpperCase() + month.slice(1).toLowerCase());
      if (n < 0) return whole;
      return month + ' ' + day + ', ' + (n >= 7 ? start - 1 : start);
    });
  }

  // GPA is not a field. 142 programs mention one inside otherRequirements,
  // in their own words, and inventing a number from that prose would be
  // exactly the kind of tidy-looking wrong answer this site exists to avoid.
  // So the matching requirement is quoted whole, or the cell is left empty.
  function gpaFrom(p) {
    var reqs = p.otherRequirements || [];
    for (var i = 0; i < reqs.length; i++) {
      if (/\bGPA\b/i.test(reqs[i])) return reqs[i];
    }
    return '';
  }

  function load() {
    if (data) return Promise.resolve(data);
    var base = location.pathname.indexOf('/tools/') >= 0 ? '../' : '';
    return Promise.all([
      fetch(base + 'data/programs.json').then(function (r) { return r.json(); }),
      fetch(base + 'data/professors.json').then(function (r) { return r.json(); }),
      // The APA disclosures. Missing for most programs, so a failure here must
      // not take the export down with it -- the columns simply come out empty.
      fetch(base + 'data/outcomes.json').then(function (r) { return r.json(); })
        .catch(function () { return { programs: {} }; })
    ]).then(function (res) {
      var profs = res[1].professors || res[1];
      var byId = {};
      profs.forEach(function (x) { byId[x.id] = x; });
      data = { programs: res[0].programs || [], profsById: byId,
               cycle: res[0].cycle, outcomes: (res[2] || {}).programs || {} };
      return data;
    });
  }

  /* One row per saved school, with only the chosen columns filled in. */
  function rows(chosen) {
    var saved = window.TCPSaved;
    var schoolIds = saved ? saved.getSchoolIds() : [];
    var profIds = saved ? saved.getProfIds() : [];

    // Starred professors are stored as their own ids, not under a school, so
    // they are grouped back by the school and program on each professor's
    // record -- the same pair the tracker keys everything else on.
    var starredBySchool = {};
    profIds.forEach(function (id) {
      var prof = data.profsById[id];
      if (!prof) return;
      var key = prof.school + '|||' + prof.program;
      (starredBySchool[key] = starredBySchool[key] || []).push(prof.name);
    });

    var wanted = {};
    schoolIds.forEach(function (id) { wanted[id] = true; });

    return data.programs.filter(function (p) { return wanted[p.id]; }).map(function (p) {
      var key = p.school + '|||' + p.program;
      var row = {};
      if (chosen.school) row['School name'] = p.school;
      if (chosen.program) row['Program'] = p.program;
      if (chosen.state) row['State'] = p.state || '';
      if (chosen.status) row['Accepting status'] = STATUS_LABEL[p.status] || p.status || '';
      if (chosen.starred) row['Your starred professors'] = (starredBySchool[key] || []).join('; ');
      if (chosen.allAccepting) row['All faculty accepting'] = (p.accepting || []).join('; ');
      if (chosen.deadline) {
        var dl = datedDeadline(p.applicationDeadline, p.cycle || data.cycle);
        row['Application deadline'] = dl
          ? dl + (p.deadlineCycle ? ' (' + p.deadlineCycle + ')' : '')
          : '';
      }
      if (chosen.fee) row['Application fee'] = p.applicationFee || '';
      if (chosen.refs) row['References required'] = p.numReferences || '';
      if (chosen.gre) row['GRE requirement'] = GRE_LABEL[p.greRequired] || p.greRequired || '';
      if (chosen.gpa) row['GPA guidance'] = gpaFrom(p);
      if (chosen.other) row['Other requirements'] = (p.otherRequirements || []).join('; ');
      if (chosen.pcsas) row['PCSAS accredited'] = p.pcsas ? 'Yes' : '';
      var o = data.outcomes[p.id] || {};
      // Blank rather than a dash when a program's disclosure could not be
      // read: a dash in a spreadsheet column reads as a reported zero.
      if (chosen.acceptance) {
        row['Acceptance rate'] = o.acceptanceRate != null
          ? o.acceptanceRate + '% (' + o.offers + ' of ' + o.applicants + ')' : '';
      }
      if (chosen.match) {
        row['Internship match rate'] = o.internshipMatchedPct != null
          ? o.internshipMatchedPct + '%' : '';
      }
      if (chosen.years) {
        row['Years to finish'] = o.medianYears != null ? o.medianYears : '';
      }
      if (chosen.confirmed) {
        row['What the school told us'] = p.confirmed && p.confirmed.answer
          ? p.confirmed.answer + ' (told us ' + (p.confirmed.on || '') + ')'
          : '';
      }
      if (chosen.deptUrl) row['Department link'] = p.url || '';
      if (chosen.appUrl) row['Application info link'] = p.appInfoSourceUrl || '';
      if (chosen.checked) row['Last checked'] = p.checked || '';
      return row;
    }).sort(function (a, b) {
      return (a['School name'] || '').localeCompare(b['School name'] || '');
    });
  }

  function columnsOf(list) {
    var seen = [], has = {};
    list.forEach(function (r) {
      Object.keys(r).forEach(function (k) { if (!has[k]) { has[k] = true; seen.push(k); } });
    });
    return seen;
  }

  function stamp() {
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
      '-' + String(d.getDate()).padStart(2, '0');
  }

  function download(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Revoked on a timer rather than immediately: Safari has not always
    // finished reading the blob by the time the click handler returns.
    setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
  }

  function tableHtml(list, cols) {
    var head = '<tr>' + cols.map(function (c) { return '<th>' + esc(c) + '</th>'; }).join('') + '</tr>';
    var body = list.map(function (r) {
      return '<tr>' + cols.map(function (c) { return '<td>' + esc(r[c] || '') + '</td>'; }).join('') + '</tr>';
    }).join('');
    return '<table border="1" cellspacing="0" cellpadding="6"><thead>' + head +
      '</thead><tbody>' + body + '</tbody></table>';
  }

  function docTitle() {
    return 'My clinical psychology shortlist' + (data && data.cycle ? ' — ' + data.cycle : '');
  }

  function wrapperHtml(list, cols) {
    return '<html><head><meta charset="utf-8"><title>' + esc(docTitle()) + '</title>' +
      '<style>body{font-family:Georgia,serif;font-size:11pt}' +
      'h1{font-size:15pt;margin:0 0 4pt}p.src{font-size:9pt;color:#555;margin:0 0 12pt}' +
      'table{border-collapse:collapse;width:100%}th{background:#f0ece4;text-align:left}' +
      'th,td{border:1px solid #bbb;padding:5pt;vertical-align:top;font-size:9.5pt}</style></head><body>' +
      '<h1>' + esc(docTitle()) + '</h1>' +
      '<p class="src">' + list.length + ' school' + (list.length === 1 ? '' : 's') +
      ', exported ' + stamp() + ' from theclinicalperspective.org. Every entry is what ' +
      'the program itself published; confirm on their own page before you apply.</p>' +
      tableHtml(list, cols) + '</body></html>';
  }

  function toCsv(list, cols) {
    function cell(v) {
      v = String(v == null ? '' : v);
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    var lines = [cols.map(cell).join(',')];
    list.forEach(function (r) { lines.push(cols.map(function (c) { return cell(r[c] || ''); }).join(',')); });
    // A BOM, so Excel opens it as UTF-8 rather than mangling every name with
    // an accent in it.
    return '﻿' + lines.join('\r\n');
  }

  function toTsv(list, cols) {
    function cell(v) { return String(v == null ? '' : v).replace(/[\t\n\r]+/g, ' '); }
    var lines = [cols.join('\t')];
    list.forEach(function (r) { lines.push(cols.map(function (c) { return cell(r[c] || ''); }).join('\t')); });
    return lines.join('\n');
  }

  function copy(text, html, done) {
    // Rich HTML where the target understands it, so a paste into Google Docs
    // arrives as a table rather than as a wall of tabs.
    if (html && window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
      navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([text], { type: 'text/plain' })
      })]).then(function () { done(true); }, function () { done(false); });
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
      return;
    }
    done(false);
  }

  function printable(list, cols) {
    var old = document.getElementById('export-print-area');
    if (old) old.remove();
    var div = document.createElement('div');
    div.id = 'export-print-area';
    div.innerHTML = '<h1>' + esc(docTitle()) + '</h1>' +
      '<p>' + list.length + ' school' + (list.length === 1 ? '' : 's') + ', ' + stamp() +
      ' · theclinicalperspective.org</p>' + tableHtml(list, cols);
    document.body.appendChild(div);
    window.print();
  }

  /* ---------------------------------------------------------------- modal */

  function chosenFields() {
    var out = {};
    FIELDS.forEach(function (f) {
      var box = modal.querySelector('#exp-' + f.key);
      out[f.key] = box ? box.checked : false;
    });
    return out;
  }

  function withRows(fn) {
    load().then(function () {
      var list = rows(chosenFields());
      var cols = columnsOf(list);
      if (!list.length) { say('Nothing saved yet — star a school first.'); return; }
      if (!cols.length) { say('Pick at least one column.'); return; }
      fn(list, cols);
    }).catch(function () { say('Could not load the program data. Check your connection.'); });
  }

  function say(msg) {
    var el = modal.querySelector('#exp-status');
    el.textContent = msg;
  }

  function build() {
    modal = document.createElement('div');
    modal.className = 'export-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'exp-title');
    modal.hidden = true;

    var boxes = FIELDS.map(function (f) {
      return '<label class="export-chip"><input type="checkbox" id="exp-' + f.key + '"' +
        (f.off ? '' : ' checked') + (f.always ? ' data-always="1"' : '') + '> ' +
        '<span>' + esc(f.label) + '</span></label>';
    }).join('');

    modal.innerHTML =
      '<div class="export-backdrop" data-close="1"></div>' +
      '<div class="export-panel">' +
        '<button type="button" class="export-x" data-close="1" aria-label="Close">×</button>' +
        '<h2 id="exp-title">Export your list</h2>' +
        '<p class="export-sub">Everything is included unless you untick it.</p>' +
        '<div class="export-chips">' + boxes + '</div>' +
        '<div class="export-actions">' +
          '<button type="button" class="export-btn" data-fmt="pdf">PDF</button>' +
          '<button type="button" class="export-btn" data-fmt="word">Word</button>' +
          '<button type="button" class="export-btn" data-fmt="csv">Excel / Sheets</button>' +
          '<button type="button" class="export-btn is-ghost" data-fmt="gdoc">Copy for Google Docs</button>' +
          '<button type="button" class="export-btn is-ghost" data-fmt="gsheet">Copy for Google Sheets</button>' +
        '</div>' +
        '<p class="export-note" id="exp-status">Google can’t be written to directly without ' +
          'handing over access to your Drive, so the two copy buttons put the list on your ' +
          'clipboard instead — paste straight into a Doc or a Sheet. The Excel file opens in ' +
          'Google Sheets too, if you would rather upload it.</p>' +
      '</div>';

    document.body.appendChild(modal);

    modal.addEventListener('click', function (e) {
      if (e.target.getAttribute('data-close')) { close(); return; }
      var btn = e.target.closest('.export-btn');
      if (!btn) return;
      run(btn.getAttribute('data-fmt'));
    });

    // School name is what makes a row identifiable; unticking it leaves a
    // table of fees belonging to nobody.
    var schoolBox = modal.querySelector('#exp-school');
    schoolBox.addEventListener('change', function () {
      if (!schoolBox.checked) { schoolBox.checked = true; say('School name has to stay — without it the rows are anonymous.'); }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !modal.hidden) close();
    });
  }

  function run(fmt) {
    withRows(function (list, cols) {
      var name = 'clinical-psych-shortlist-' + stamp();
      if (fmt === 'pdf') {
        say('Opening your print dialog — choose “Save as PDF”.');
        printable(list, cols);
      } else if (fmt === 'word') {
        download(new Blob(['﻿' + wrapperHtml(list, cols)],
          { type: 'application/msword' }), name + '.doc');
        say('Downloaded ' + name + '.doc');
      } else if (fmt === 'csv') {
        download(new Blob([toCsv(list, cols)], { type: 'text/csv;charset=utf-8' }), name + '.csv');
        say('Downloaded ' + name + '.csv — opens in Excel, Numbers or Google Sheets.');
      } else if (fmt === 'gdoc') {
        copy(toTsv(list, cols), wrapperHtml(list, cols), function (ok) {
          say(ok ? 'Copied. Paste into a Google Doc — it arrives as a table.'
                 : 'Your browser blocked the clipboard. Use Word or PDF instead.');
        });
      } else if (fmt === 'gsheet') {
        copy(toTsv(list, cols), null, function (ok) {
          say(ok ? 'Copied. Click the first cell in a Google Sheet and paste.'
                 : 'Your browser blocked the clipboard. Use the Excel file instead.');
        });
      }
    });
  }

  function open() {
    if (!modal) build();
    modal.hidden = false;
    document.body.classList.add('export-open');
    var first = modal.querySelector('.export-chips input');
    if (first) first.focus();
    load().then(function () {
      var n = rows(chosenFields()).length;
      if (!n) say('Nothing saved yet — star a school on the tracker first.');
    });
  }

  function close() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('export-open');
    var btn = document.getElementById('export-open-btn');
    if (btn) btn.focus();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('export-open-btn');
    if (btn) btn.addEventListener('click', open);
  });
})();
