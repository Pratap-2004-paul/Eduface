// ============================================================
// EDUFACE — Shared Utilities & API Client
// ============================================================

window.EduFace = window.EduFace || {};

// ── API fetch wrapper ─────────────────────────────────────────
// All endpoints match exactly what app.py defines under /api/*
EduFace.api = async function(method, url, body = null, isFormData = false) {
  const opts = {
    method,
    credentials: 'same-origin',
    headers: isFormData ? {} : { 'Content-Type': 'application/json' }
  };
  if (body !== null) {
    opts.body = isFormData ? body : JSON.stringify(body);
  }
  try {
    const res  = await fetch(url, opts);
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); }
    catch { data = { ok: false, msg: `Server returned non-JSON: ${text.slice(0,120)}` }; }
    if (!res.ok && data.ok === undefined) data.ok = false;
    return data;
  } catch (err) {
    return { ok: false, msg: 'Network error — is Flask running on port 5000?' };
  }
};

EduFace.get      = url      => EduFace.api('GET',    url);
EduFace.post     = (url, b) => EduFace.api('POST',   url, b);
EduFace.del      = url      => EduFace.api('DELETE', url);
EduFace.postForm = (url, f) => EduFace.api('POST',   url, f, true);

// ── Toast ─────────────────────────────────────────────────────
EduFace.toast = function(message, type = 'info', duration = 3500) {
  let c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    document.body.appendChild(c);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  c.appendChild(t);
  setTimeout(() => {
    t.style.animation = 'slideOut .3s ease forwards';
    setTimeout(() => t.remove(), 300);
  }, duration);
};

// ── Modal ─────────────────────────────────────────────────────
EduFace.openModal  = id => {
  const e = document.getElementById(id);
  if (e) { e.classList.add('active'); document.body.style.overflow = 'hidden'; }
};
EduFace.closeModal = id => {
  const e = document.getElementById(id);
  if (e) { e.classList.remove('active'); document.body.style.overflow = ''; }
};

// ── Navigate ──────────────────────────────────────────────────
EduFace.navigate = url => { window.location.href = url; };

// ── Auth guard — checks /api/auth/me ─────────────────────────
EduFace.requireRole = async function(expectedRole) {
  const data = await EduFace.get('/api/auth/me');
  if (!data.ok || data.role !== expectedRole) {
    EduFace.navigate('/');
    return null;
  }
  if (data.role === 'admin') return { id: 'admin', name: 'Administrator' };
  return data.user;
};

// ── Helpers ───────────────────────────────────────────────────
EduFace.initials = name => (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
EduFace.todayStr = () => new Date().toISOString().slice(0, 10);
EduFace.fmtDate  = str => {
  if (!str) return '—';
  try { return new Date(str).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return str; }
};
EduFace.fmtTime = () => new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

EduFace.togglePwd = function(iconEl) {
  const input = iconEl.closest('.input-group').querySelector('input');
  if (input.type === 'password') { input.type = 'text';     iconEl.textContent = '🙈'; }
  else                           { input.type = 'password'; iconEl.textContent = '👁️'; }
};

EduFace.copyText = text =>
  navigator.clipboard.writeText(text).then(() => EduFace.toast('Copied!', 'success', 1500));

EduFace.previewImage = function(input, previewId) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const p = document.getElementById(previewId);
    if (p) { p.src = e.target.result; p.style.display = 'block'; }
  };
  reader.readAsDataURL(file);
};

// ── Multi-step form ───────────────────────────────────────────
EduFace.setupMultiStep = function(prefix, totalSteps) {
  let current = 1;
  const form  = document.getElementById(`${prefix}-form`);
  if (!form) return { reset: () => {} };

  function update() {
    for (let i = 1; i <= totalSteps; i++) {
      document.getElementById(`${prefix}-step-circle-${i}`)
        ?.classList.toggle('active', i === current);
      document.getElementById(`${prefix}-step-circle-${i}`)
        ?.classList.toggle('done',   i < current);
      document.getElementById(`${prefix}-step-label-${i}`)
        ?.classList.toggle('active', i === current);
      document.getElementById(`${prefix}-step-content-${i}`)
        ?.classList.toggle('active', i === current);
    }
  }

  form.querySelectorAll('[data-next]').forEach(btn =>
    btn.addEventListener('click', () => { if (current < totalSteps) { current++; update(); } }));
  form.querySelectorAll('[data-prev]').forEach(btn =>
    btn.addEventListener('click', () => { if (current > 1)          { current--; update(); } }));

  update();
  return { reset: () => { current = 1; update(); } };
};

// ── Drag & drop file upload ───────────────────────────────────
EduFace.initDropzones = function() {
  document.querySelectorAll('.file-upload-area').forEach(area => {
    area.addEventListener('dragover',  e => { e.preventDefault(); area.classList.add('dragover'); });
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', e => {
      e.preventDefault(); area.classList.remove('dragover');
      const input = area.querySelector('input[type="file"]');
      if (input && e.dataTransfer.files[0]) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change'));
      }
    });
    area.addEventListener('click', e => {
      if (e.target.tagName !== 'INPUT') area.querySelector('input[type="file"]')?.click();
    });
  });
};
