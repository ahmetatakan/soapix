"""Embedded HTML/JS for the soapix interactive playground."""

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>soapix playground</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;height:100vh;display:flex;flex-direction:column}
header{padding:12px 24px;background:#1a1d27;border-bottom:1px solid #2d3148;display:flex;align-items:center;gap:16px;flex-shrink:0}
.logo{font-size:17px;font-weight:700;color:#7c3aed;letter-spacing:-0.02em}
.logo span{color:#a78bfa}
.meta{font-size:13px;color:#64748b}
.service-label{color:#94a3b8;font-weight:600}
.main{display:flex;flex:1;overflow:hidden}
.sidebar{width:250px;background:#13151f;border-right:1px solid #2d3148;overflow-y:auto;flex-shrink:0;display:flex;flex-direction:column}
.sidebar-hd{padding:14px 16px 8px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.1em}
.search{padding:0 12px 10px}
.search input{width:100%;background:#1a1d27;border:1px solid #2d3148;border-radius:6px;padding:7px 10px;color:#e2e8f0;font-size:12px;outline:none}
.search input:focus{border-color:#7c3aed}
.op-item{padding:9px 16px;cursor:pointer;border-left:3px solid transparent;font-size:13px;color:#94a3b8;transition:all 0.12s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.op-item:hover{background:#1e2130;color:#c4b5fd}
.op-item.active{background:#1e2130;border-left-color:#7c3aed;color:#a78bfa;font-weight:600}
.content{flex:1;overflow-y:auto;padding:28px 32px;display:flex;gap:28px}
.form-panel{flex:1;min-width:280px;max-width:520px}
.resp-panel{flex:1;min-width:280px}
.op-title{font-size:22px;font-weight:700;margin-bottom:2px}
.op-sub{font-size:13px;color:#64748b;margin-bottom:22px}
/* flat field */
.field{margin-bottom:14px}
label{display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:5px;letter-spacing:0.01em}
.req{color:#f87171;font-size:11px}
.opt{color:#475569;font-size:10px;font-weight:400;text-transform:none;letter-spacing:0}
input[type=text],textarea{width:100%;background:#1a1d27;border:1px solid #2d3148;border-radius:6px;padding:8px 10px;color:#e2e8f0;font-size:13px;outline:none;transition:border-color 0.15s;font-family:'SF Mono','Fira Code','Consolas',monospace;resize:vertical}
input[type=text]:focus,textarea:focus{border-color:#7c3aed}
.type-hint{font-size:10px;color:#374151;margin-top:3px;font-family:'SF Mono','Fira Code',monospace}
/* nested group */
.field-group{margin-bottom:16px;border:1px solid #1e2130;border-radius:8px;overflow:hidden}
.field-group-hd{padding:8px 12px;background:#13151f;border-bottom:1px solid #1e2130;display:flex;align-items:center;gap:6px}
.field-group-name{font-size:12px;font-weight:700;color:#a78bfa;letter-spacing:0.01em}
.field-group-type{font-size:11px;color:#475569;font-family:'SF Mono','Fira Code',monospace}
.field-group-req{font-size:10px;color:#f87171}
.field-group-opt{font-size:10px;color:#475569}
.field-group-body{padding:12px 12px 4px}
.field-group-body .field{margin-bottom:10px}
.field-group-body label{font-size:11px;color:#64748b}
/* buttons */
.btn{background:#7c3aed;color:#fff;border:none;border-radius:6px;padding:10px 22px;font-size:14px;font-weight:600;cursor:pointer;transition:background 0.15s;display:inline-flex;align-items:center;gap:8px}
.btn:hover{background:#6d28d9}
.btn:disabled{background:#1e293b;color:#475569;cursor:not-allowed}
.btn-row{display:flex;align-items:center;gap:12px;margin-top:4px}
.clear-btn{background:transparent;border:1px solid #2d3148;color:#64748b;border-radius:6px;padding:9px 14px;font-size:13px;cursor:pointer;transition:all 0.15s}
.clear-btn:hover{border-color:#475569;color:#94a3b8}
/* response */
.resp-hd{font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.02em}
.badge-ok{background:#064e3b;color:#34d399}
.badge-err{background:#450a0a;color:#f87171}
.resp-box{background:#080b12;border:1px solid #1e2130;border-radius:8px;padding:16px;font-family:'SF Mono','Fira Code','Consolas',monospace;font-size:12px;line-height:1.7;overflow:auto;min-height:180px;max-height:60vh;white-space:pre;word-break:break-all;color:#94a3b8}
.resp-ok{color:#6ee7b7}
.resp-err{color:#fca5a5}
.resp-time{font-size:11px;color:#475569}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh;color:#374151;text-align:center;gap:10px;flex:1}
.empty-icon{font-size:44px;opacity:0.4}
.no-fields{color:#475569;font-size:13px;font-style:italic;margin-bottom:12px}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#2d3148;border-radius:3px}
</style>
</head>
<body>
<header>
  <div class="logo">soap<span>ix</span></div>
  <div class="meta"><span class="service-label" id="service-name">Loading…</span></div>
  <div class="meta" id="endpoint-label" style="margin-left:auto"></div>
</header>
<div class="main">
  <div class="sidebar">
    <div class="sidebar-hd">Operations</div>
    <div class="search"><input id="search" type="text" placeholder="Filter…" oninput="filterOps(this.value)"></div>
    <div id="op-list"></div>
  </div>
  <div class="content" id="content">
    <div class="empty">
      <div class="empty-icon">⚡</div>
      <div style="font-size:15px;color:#475569">Select an operation from the sidebar</div>
    </div>
  </div>
</div>

<script>
let ops = [];
let currentOp = null;

async function init() {
  const res = await fetch('/api/meta');
  const meta = await res.json();
  document.getElementById('service-name').textContent = meta.service_name;
  document.getElementById('endpoint-label').textContent = meta.endpoint || '';

  const r2 = await fetch('/api/operations');
  ops = await r2.json();
  renderSidebar(ops);
}

function renderSidebar(list) {
  const el = document.getElementById('op-list');
  el.innerHTML = '';
  list.forEach(op => {
    const d = document.createElement('div');
    d.className = 'op-item' + (currentOp && currentOp.name === op.name ? ' active' : '');
    d.textContent = op.name;
    d.title = op.name;
    d.onclick = () => selectOp(op);
    el.appendChild(d);
  });
}

function filterOps(q) {
  const filtered = q ? ops.filter(o => o.name.toLowerCase().includes(q.toLowerCase())) : ops;
  renderSidebar(filtered);
}

function selectOp(op) {
  currentOp = op;
  document.querySelectorAll('.op-item').forEach(e => {
    e.classList.toggle('active', e.textContent === op.name);
  });
  renderForm(op);
}

/* ---- Field rendering ---- */

function renderFields(fields, prefix) {
  let html = '';
  fields.forEach(f => {
    const id = prefix ? prefix + '__' + f.name : f.name;
    if (f.children && f.children.length > 0) {
      // Complex type → grouped section
      const reqLabel = f.required
        ? '<span class="field-group-req">required</span>'
        : '<span class="field-group-opt">optional</span>';
      html += `
        <div class="field-group">
          <div class="field-group-hd">
            <span class="field-group-name">${esc(f.name)}</span>
            <span class="field-group-type">${esc(f.type)}</span>
            ${reqLabel}
          </div>
          <div class="field-group-body">
            ${renderFields(f.children, id)}
          </div>
        </div>`;
    } else {
      // Primitive field
      const isLong = ['base64Binary','string'].includes(f.type);
      const ph = f.required ? 'required' : 'optional';
      const inp = isLong
        ? `<textarea id="f_${esc(id)}" rows="2" placeholder="${ph}"></textarea>`
        : `<input type="text" id="f_${esc(id)}" placeholder="${ph}">`;
      const reqMark = f.required
        ? '<span class="req">*</span>'
        : '<span class="opt">optional</span>';
      html += `
        <div class="field">
          <label>${esc(f.name)}${reqMark}</label>
          ${inp}
          <div class="type-hint">${esc(f.type)}</div>
        </div>`;
    }
  });
  return html;
}

function renderForm(op) {
  const hasFields = op.fields.length > 0;
  const fieldsHtml = hasFields
    ? renderFields(op.fields, '')
    : '<div class="no-fields">No input parameters</div>';

  document.getElementById('content').innerHTML = `
    <div class="form-panel">
      <div class="op-title">${esc(op.name)}</div>
      <div class="op-sub">${op.fields.length} input field${op.fields.length !== 1 ? 's' : ''}</div>
      ${fieldsHtml}
      <div class="btn-row">
        <button class="btn" id="exec-btn" onclick="execute()">&#9654; Execute</button>
        <button class="clear-btn" onclick="clearForm()">Clear</button>
      </div>
    </div>
    <div class="resp-panel">
      <div class="resp-hd">Response <span id="resp-badge"></span> <span class="resp-time" id="resp-time"></span></div>
      <div class="resp-box" id="resp-box"><span style="color:#1e293b">Response will appear here…</span></div>
    </div>`;
}

/* ---- Collect form values (flat with __ separator) ---- */

function collectValues(fields, prefix, out) {
  fields.forEach(f => {
    const id = prefix ? prefix + '__' + f.name : f.name;
    if (f.children && f.children.length > 0) {
      collectValues(f.children, id, out);
    } else {
      const el = document.getElementById('f_' + id);
      if (el && el.value.trim() !== '') out[id] = el.value.trim();
    }
  });
}

/* ---- Execute ---- */

async function execute() {
  if (!currentOp) return;
  const btn = document.getElementById('exec-btn');
  btn.disabled = true; btn.textContent = 'Executing…';
  document.getElementById('resp-box').innerHTML = '<span style="color:#475569">Calling service…</span>';
  document.getElementById('resp-badge').innerHTML = '';
  document.getElementById('resp-time').textContent = '';

  const flat = {};
  collectValues(currentOp.fields, '', flat);

  const t0 = Date.now();
  try {
    const res = await fetch('/api/call/' + currentOp.name, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(flat),
    });
    const data = await res.json();
    const ms = Date.now() - t0;
    const box = document.getElementById('resp-box');
    const badge = document.getElementById('resp-badge');
    document.getElementById('resp-time').textContent = ms + ' ms';
    if (data.ok) {
      badge.innerHTML = '<span class="badge badge-ok">200 OK</span>';
      box.innerHTML = '<span class="resp-ok">' + esc(JSON.stringify(data.result, null, 2)) + '</span>';
    } else {
      badge.innerHTML = '<span class="badge badge-err">Error</span>';
      box.innerHTML = '<span class="resp-err">' + esc(data.error) + '</span>';
    }
  } catch (e) {
    document.getElementById('resp-box').innerHTML = '<span class="resp-err">Network error: ' + esc(e.message) + '</span>';
  }
  btn.disabled = false; btn.innerHTML = '&#9654; Execute';
}

function clearForm() {
  if (!currentOp) return;
  document.querySelectorAll('#content input, #content textarea').forEach(el => el.value = '');
  document.getElementById('resp-box').innerHTML = '<span style="color:#1e293b">Response will appear here…</span>';
  document.getElementById('resp-badge').innerHTML = '';
  document.getElementById('resp-time').textContent = '';
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') execute();
});

init();
</script>
</body>
</html>
"""
