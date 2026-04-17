// ============================================================
// EDUFACE — Admin Dashboard JS
// All fetch calls use /api/admin/* as defined in app.py
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {

  // ── Auth guard ─────────────────────────────────────────────
  const user = await EduFace.requireRole('admin');
  if (!user) return;

  // ── Date in topbar ────────────────────────────────────────
  const todayEl = document.getElementById('today-date');
  if (todayEl) todayEl.textContent =
    new Date().toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  // ── Section navigation ────────────────────────────────────
  const sectionTitles = {
    overview:   'Admin Overview',
    approvals:  'Pending Approvals',
    teachers:   'Teacher Management',
    students:   'Student Management',
    attendance: 'Attendance Records',
    chats:      'All Chats'
  };

  function showSection(id) {
    document.querySelectorAll('.admin-section').forEach(s =>
      s.classList.toggle('hidden', s.id !== `section-${id}`));
    document.querySelectorAll('.nav-item[data-section]').forEach(n =>
      n.classList.toggle('active', n.dataset.section === id));
    document.getElementById('topbar-title').textContent = sectionTitles[id] || id;

    const loaders = {
      overview:   renderOverview,
      approvals:  renderApprovals,
      teachers:   () => renderTeachers(''),
      students:   () => renderStudents(''),
      attendance: () => renderAttendance(''),
      chats:      renderChats
    };
    loaders[id]?.();
  }

  document.querySelectorAll('.nav-item[data-section]').forEach(n =>
    n.addEventListener('click', () => showSection(n.dataset.section)));

  // Logout — calls /api/auth/logout
  document.getElementById('logout-btn')?.addEventListener('click', async () => {
    await EduFace.post('/api/auth/logout');
    EduFace.navigate('/');
  });

  // ── OVERVIEW — /api/admin/stats ───────────────────────────
  async function renderOverview() {
    const res = await EduFace.get('/api/admin/stats');
    if (!res.ok && res.ok !== undefined) { EduFace.toast('Failed to load stats.', 'error'); return; }
    document.getElementById('stat-teachers').textContent   = res.teachers   ?? 0;
    document.getElementById('stat-students').textContent   = res.students   ?? 0;
    document.getElementById('stat-attendance').textContent = res.attendance ?? 0;
    document.getElementById('stat-chats').textContent      = res.messages   ?? 0;
    document.getElementById('stat-pending').textContent    = res.pending    ?? 0;
    updateBadge(res.pending ?? 0);
  }

  function updateBadge(n) {
    const badge = document.getElementById('approval-badge');
    if (!badge) return;
    badge.textContent   = n;
    badge.style.display = n > 0 ? 'inline-block' : 'none';
  }

  // ── TEACHERS — /api/admin/teachers ───────────────────────
  async function renderTeachers(q = '') {
    const tbody = document.getElementById('teachers-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:28px">Loading…</td></tr>`;

    const url  = `/api/admin/teachers${q ? '?q=' + encodeURIComponent(q) : ''}`;
    const list = await EduFace.get(url);

    if (!Array.isArray(list)) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Failed to load.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(t => `
      <tr>
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            ${t.photo_url
              ? `<img src="${t.photo_url}" class="avatar" style="object-fit:cover"/>`
              : `<div class="avatar">${EduFace.initials(t.name)}</div>`}
            <div>
              <div style="font-weight:600;color:var(--slate-900)">${t.name}</div>
              <div style="font-size:.75rem;color:var(--slate-400)">${t.email}</div>
            </div>
          </div>
        </td>
        <td><code style="background:var(--slate-100);padding:2px 8px;border-radius:4px;font-size:.8rem">${t.userid}</code></td>
        <td>
          <span class="pwd-mask">••••••••</span>
          <span onclick="this.previousElementSibling.textContent=this.previousElementSibling.textContent.includes('•')?'${t.password_hash.slice(0,18)}…':'••••••••'"
                style="cursor:pointer;font-size:.72rem;color:var(--indigo-600);margin-left:4px">👁</span>
        </td>
        <td>${t.dept}</td>
        <td>${t.mobile}</td>
        <td><span class="badge badge-${t.status === 'approved' ? 'green' : 'amber'}">${t.status}</span></td>
        <td>${EduFace.fmtDate(t.created_at)}</td>
        <td style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="viewDetail(${t.id},'teacher')" title="View Details">👁 View</button>
          <button class="btn btn-outline btn-sm" onclick="openEditModal(${t.id},'teacher')" title="Edit">✏️ Edit</button>
          ${t.status === 'pending' ? `
            <button class="btn btn-success btn-sm" onclick="doApprove(${t.id},'teacher')" title="Approve">✓ Approve</button>` : ''}
          <button class="btn btn-danger btn-sm" onclick="doDelete(${t.id},'teacher','${t.name.replace(/'/g,"\\'")}')">🗑 Delete</button>
        </td>
      </tr>`).join('') || `<tr><td colspan="8" class="text-center text-muted" style="padding:28px">No teachers found.</td></tr>`;
  }

  document.getElementById('teachers-search')?.addEventListener('input', e =>
    renderTeachers(e.target.value));

  // ── STUDENTS — /api/admin/students ───────────────────────
  async function renderStudents(q = '') {
    const tbody = document.getElementById('students-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:28px">Loading…</td></tr>`;

    const url  = `/api/admin/students${q ? '?q=' + encodeURIComponent(q) : ''}`;
    const list = await EduFace.get(url);

    if (!Array.isArray(list)) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Failed to load.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(s => `
      <tr>
        <td>
          <div style="display:flex;align-items:center;gap:10px">
            ${s.photo_url
              ? `<img src="${s.photo_url}" class="avatar" style="object-fit:cover"/>`
              : `<div class="avatar">${EduFace.initials(s.name)}</div>`}
            <div>
              <div style="font-weight:600;color:var(--slate-900)">${s.name}</div>
              <div style="font-size:.75rem;color:var(--slate-400)">${s.email}</div>
            </div>
          </div>
        </td>
        <td><code style="background:var(--slate-100);padding:2px 8px;border-radius:4px;font-size:.8rem">${s.userid}</code></td>
        <td>
          <span class="pwd-mask">••••••••</span>
          <span onclick="this.previousElementSibling.textContent=this.previousElementSibling.textContent.includes('•')?'${s.password_hash.slice(0,18)}…':'••••••••'"
                style="cursor:pointer;font-size:.72rem;color:var(--indigo-600);margin-left:4px">👁</span>
        </td>
        <td>${s.dept}</td>
        <td>${s.rollno || '—'}</td>
        <td>${s.mobile}</td>
        <td><span class="badge badge-${s.status === 'approved' ? 'green' : 'amber'}">${s.status}</span></td>
        <td style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-ghost btn-sm" onclick="viewDetail(${s.id},'student')" title="View Details">👁 View</button>
          <button class="btn btn-outline btn-sm" onclick="openEditModal(${s.id},'student')" title="Edit">✏️ Edit</button>
          ${s.status === 'pending' ? `
            <button class="btn btn-success btn-sm" onclick="doApprove(${s.id},'student')" title="Approve">✓ Approve</button>` : ''}
          <button class="btn btn-danger btn-sm" onclick="doDelete(${s.id},'student','${s.name.replace(/'/g,"\\'")}')">🗑 Delete</button>
        </td>
      </tr>`).join('') || `<tr><td colspan="8" class="text-center text-muted" style="padding:28px">No students found.</td></tr>`;
  }

  document.getElementById('students-search')?.addEventListener('input', e =>
    renderStudents(e.target.value));

  // ── ATTENDANCE — /api/admin/attendance ───────────────────
  async function renderAttendance(q = '') {
    const tbody = document.getElementById('attendance-tbody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding:28px">Loading…</td></tr>`;

    const url     = `/api/admin/attendance${q ? '?q=' + encodeURIComponent(q) : ''}`;
    const records = await EduFace.get(url);

    if (!Array.isArray(records)) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Failed to load.</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(r => `
      <tr>
        <td style="font-weight:500">${r.student_name}</td>
        <td>${r.subject}</td>
        <td>${r.dept}</td>
        <td>${EduFace.fmtDate(r.date)} ${r.time || ''}</td>
        <td><span class="badge badge-${r.present ? 'green' : 'red'}">${r.present ? '✓ Present' : '✗ Absent'}</span></td>
      </tr>`).join('') || `<tr><td colspan="5" class="text-center text-muted" style="padding:28px">No records.</td></tr>`;
  }

  document.getElementById('attendance-search')?.addEventListener('input', e =>
    renderAttendance(e.target.value));

  // ── CHATS — /api/admin/chats ──────────────────────────────
  async function renderChats() {
    const container = document.getElementById('chats-admin-container');
    if (!container) return;
    container.innerHTML = '<p class="text-muted text-center" style="padding:28px">Loading…</p>';

    const chats = await EduFace.get('/api/admin/chats');

    if (!Array.isArray(chats) || !chats.length) {
      container.innerHTML = '<p class="text-muted text-center">No conversations yet.</p>';
      return;
    }

    container.innerHTML = chats.map(c => `
      <div class="panel mb-16">
        <div class="panel-header">
          <div>
            <div class="panel-title">🧑‍🏫 ${c.teacher_name} ↔ 👩‍🎓 ${c.student_name}</div>
            <div class="text-muted" style="margin-top:4px;font-size:.8rem">${(c.messages||[]).length} messages</div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;max-height:260px;overflow-y:auto">
          ${(c.messages||[]).map(m => `
            <div style="display:flex;gap:10px;align-items:flex-start">
              <div class="avatar" style="width:30px;height:30px;font-size:.68rem">
                ${EduFace.initials(m.sender_name || '?')}
              </div>
              <div>
                <div style="font-size:.73rem;color:var(--slate-400)">${m.sender_name} · ${m.created_at}</div>
                <div style="font-size:.87rem;background:var(--slate-50);padding:8px 12px;border-radius:10px;margin-top:2px">${m.text}</div>
              </div>
            </div>`).join('') || '<p class="text-muted" style="padding:8px">No messages yet.</p>'}
        </div>
      </div>`).join('');
  }

  // ── APPROVALS — combines pending from both lists ──────────
  async function renderApprovals() {
    const container = document.getElementById('approvals-container');
    if (!container) return;
    container.innerHTML = '<p class="text-muted text-center" style="padding:28px">Loading…</p>';

    const [tList, sList] = await Promise.all([
      EduFace.get('/api/admin/teachers'),
      EduFace.get('/api/admin/students')
    ]);

    const pendingT = Array.isArray(tList) ? tList.filter(t => t.status === 'pending').map(t => ({...t, _type:'teacher'})) : [];
    const pendingS = Array.isArray(sList) ? sList.filter(s => s.status === 'pending').map(s => ({...s, _type:'student'})) : [];
    const pending  = [...pendingT, ...pendingS];

    updateBadge(pending.length);

    if (!pending.length) {
      container.innerHTML = `
        <div class="text-center" style="padding:60px">
          <div style="font-size:3rem;margin-bottom:16px">✅</div>
          <h3>All caught up!</h3>
          <p class="text-muted">No pending approvals at this time.</p>
        </div>`;
      return;
    }

    container.innerHTML = pending.map(u => `
      <div class="approval-item">
        ${u.photo_url
          ? `<img src="${u.photo_url}" class="avatar avatar-lg" style="object-fit:cover"/>`
          : `<div class="avatar avatar-lg">${EduFace.initials(u.name)}</div>`}
        <div style="flex:1">
          <div style="font-weight:600;color:var(--slate-900)">${u.name}</div>
          <div class="text-muted" style="margin-top:3px">${u._type === 'teacher' ? '🧑‍🏫 Teacher' : '👩‍🎓 Student'} · ${u.dept}</div>
          <div style="font-size:.77rem;color:var(--slate-400);margin-top:2px">📧 ${u.email} · 📱 ${u.mobile}</div>
          <div style="font-size:.77rem;margin-top:4px">
            User ID: <code style="background:var(--slate-100);padding:1px 7px;border-radius:4px">${u.userid}</code>
          </div>
        </div>
        <div class="approval-actions">
          <button class="btn btn-success btn-sm" onclick="doApprove(${u.id},'${u._type}')">✓ Approve</button>
          <button class="btn btn-danger  btn-sm" onclick="doDelete(${u.id},'${u._type}','${u.name.replace(/'/g,"\\'")}')">🗑 Delete</button>
        </div>
      </div>`).join('');
  }

  // ── Approve / Reject (global window functions for inline onclick) ──
  window.doApprove = async (id, type) => {
    const url = type === 'teacher'
      ? `/api/admin/teachers/${id}/approve`
      : `/api/admin/students/${id}/approve`;
    const res = await EduFace.post(url);
    if (res.ok) {
      EduFace.toast(`${type === 'teacher' ? 'Teacher' : 'Student'} approved!`, 'success');
      renderApprovals();
      if (type === 'teacher') renderTeachers('');
      else                    renderStudents('');
    } else {
      EduFace.toast(res.msg || 'Failed.', 'error');
    }
  };

  window.doReject = async (id, type) => {
    // doReject still used in approvals panel — delegates to doDelete
    doDelete(id, type, '');
  };

  // ── doDelete: shows confirmation modal then calls API ─────
  window.doDelete = (id, type, name) => {
    // Fill confirmation modal
    const label = type === 'teacher' ? 'Teacher' : 'Student';
    document.getElementById('del-confirm-title').textContent   = `Delete ${label}`;
    document.getElementById('del-confirm-name').textContent    = name || `${label} #${id}`;
    document.getElementById('del-confirm-type').textContent    = label;
    document.getElementById('del-confirm-warning').textContent =
      type === 'teacher'
        ? 'All attendance records and chats linked to this teacher will also be deleted.'
        : 'All attendance records and chats linked to this student will also be deleted.';

    EduFace.openModal('delete-confirm-modal');

    // Wire confirm button (replace old listener)
    const confirmBtn = document.getElementById('del-confirm-btn');
    const newBtn = confirmBtn.cloneNode(true);          // remove old listeners
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

    newBtn.addEventListener('click', async () => {
      newBtn.disabled = true;
      newBtn.innerHTML = '<span class="spinner"></span> Deleting…';

      const url = type === 'teacher'
        ? `/api/admin/teachers/${id}/reject`
        : `/api/admin/students/${id}/reject`;
      const res = await EduFace.del(url);

      EduFace.closeModal('delete-confirm-modal');
      newBtn.disabled = false;
      newBtn.textContent = 'Yes, Delete';

      if (res.ok) {
        EduFace.toast(`${label} deleted successfully.`, 'success');
        renderApprovals();
        if (type === 'teacher') renderTeachers('');
        else                    renderStudents('');
        renderOverview();
      } else {
        EduFace.toast(res.msg || 'Delete failed.', 'error');
      }
    });
  };

  // ── Detail modal ──────────────────────────────────────────
  window.viewDetail = async (id, type) => {
    const url  = type === 'teacher' ? '/api/admin/teachers' : '/api/admin/students';
    const list = await EduFace.get(url);
    const u    = Array.isArray(list) ? list.find(x => x.id === id) : null;
    if (!u) return;

    document.getElementById('detail-modal-body').innerHTML = `
      <div style="text-align:center;margin-bottom:20px">
        ${u.photo_url
          ? `<img src="${u.photo_url}" style="width:90px;height:90px;border-radius:50%;object-fit:cover;border:4px solid var(--indigo-200)"/>`
          : `<div class="avatar avatar-xl" style="margin:0 auto">${EduFace.initials(u.name)}</div>`}
        <h3 style="margin-top:12px;font-family:var(--font-display)">${u.name}</h3>
        <span class="badge badge-indigo">${type === 'teacher' ? 'Teacher' : 'Student'}</span>
      </div>
      <div style="display:grid;gap:8px">
        ${[
          ['📧 Email',      u.email],
          ['📱 Mobile',     u.mobile],
          ['🏫 Department', u.dept],
          ...(u.rollno ? [['🎓 Roll No.', u.rollno]] : []),
          ['🪪 User ID',    u.userid],
          ['✅ Status',     u.status],
          ['📅 Joined',     EduFace.fmtDate(u.created_at)],
        ].map(([l,v]) => `
          <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--slate-50);border-radius:8px;font-size:.86rem">
            <span style="color:var(--slate-500)">${l}</span>
            <span style="font-weight:500;color:var(--slate-800)">${v}</span>
          </div>`).join('')}
      </div>
      <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--slate-100);display:flex;gap:10px;justify-content:flex-end">
        <button class="btn btn-outline btn-sm" onclick="EduFace.closeModal('detail-modal');openEditModal(${u.id},'${type}')">✏️ Edit</button>
        ${u.status === 'pending' ? `<button class="btn btn-success btn-sm" onclick="EduFace.closeModal('detail-modal');doApprove(${u.id},'${type}')">✓ Approve</button>` : ''}
        <button class="btn btn-danger btn-sm" onclick="EduFace.closeModal('detail-modal');doDelete(${u.id},'${type}','${u.name.replace(/'/g,"\\'")}')">🗑 Delete ${type === 'teacher' ? 'Teacher' : 'Student'}</button>
      </div>`;
    EduFace.openModal('detail-modal');
  };

  document.querySelector('[data-close-modal="detail-modal"]')
    ?.addEventListener('click', () => EduFace.closeModal('detail-modal'));
  document.getElementById('detail-modal')
    ?.addEventListener('click', e => { if (e.target.id === 'detail-modal') EduFace.closeModal('detail-modal'); });

  // ── EDIT MODAL ────────────────────────────────────────────
  // Opens pre-filled edit form for teacher or student
  window.openEditModal = async (id, type) => {
    const url  = type === 'teacher' ? '/api/admin/teachers' : '/api/admin/students';
    const list = await EduFace.get(url);
    const u    = Array.isArray(list) ? list.find(x => x.id === id) : null;
    if (!u) { EduFace.toast('Could not load record.', 'error'); return; }

    const isTeacher = type === 'teacher';
    const depts = ['Computer Science','Mathematics','Physics','Chemistry','Biology',
                   'English','History','Economics','Commerce','Arts'];

    // Build modal body
    document.getElementById('edit-modal-title').textContent = isTeacher ? '✏️ Edit Teacher' : '✏️ Edit Student';
    document.getElementById('edit-modal-body').innerHTML = `
      <form id="edit-record-form" autocomplete="off">
        <input type="hidden" id="edit-id"   value="${u.id}" />
        <input type="hidden" id="edit-type" value="${type}" />

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">

          <!-- Full Name -->
          <div class="form-group" style="grid-column:1/-1">
            <label class="form-label">Full Name *</label>
            <div class="input-group">
              <span class="input-icon">👤</span>
              <input type="text" id="edit-name" class="form-control" value="${u.name}" required />
            </div>
          </div>

          <!-- Email -->
          <div class="form-group">
            <label class="form-label">Email *</label>
            <div class="input-group">
              <span class="input-icon">📧</span>
              <input type="email" id="edit-email" class="form-control" value="${u.email}" required />
            </div>
          </div>

          <!-- Mobile -->
          <div class="form-group">
            <label class="form-label">Mobile *</label>
            <div class="input-group">
              <span class="input-icon">📱</span>
              <input type="tel" id="edit-mobile" class="form-control" value="${u.mobile}" required />
            </div>
          </div>

          <!-- Department -->
          <div class="form-group">
            <label class="form-label">Department *</label>
            <select id="edit-dept" class="form-control" required>
              ${depts.map(d => `<option value="${d}" ${d === u.dept ? 'selected' : ''}>${d}</option>`).join('')}
            </select>
          </div>

          ${!isTeacher ? `
          <!-- Roll No (students only) -->
          <div class="form-group">
            <label class="form-label">Roll Number</label>
            <div class="input-group">
              <span class="input-icon">🎓</span>
              <input type="text" id="edit-rollno" class="form-control" value="${u.rollno || ''}" />
            </div>
          </div>` : ''}

          <!-- User ID -->
          <div class="form-group">
            <label class="form-label">User ID *</label>
            <div class="input-group">
              <span class="input-icon">🪪</span>
              <input type="text" id="edit-userid" class="form-control" value="${u.userid}" required />
            </div>
          </div>

          <!-- New Password -->
          <div class="form-group">
            <label class="form-label">New Password <span style="color:var(--slate-400);font-weight:400">(leave blank to keep current)</span></label>
            <div class="input-group">
              <span class="input-icon">🔑</span>
              <input type="password" id="edit-password" class="form-control" placeholder="Enter new password…" />
              <span class="input-icon-right" onclick="EduFace.togglePwd(this)">👁️</span>
            </div>
          </div>

          <!-- Status -->
          <div class="form-group">
            <label class="form-label">Status</label>
            <select id="edit-status" class="form-control">
              <option value="approved" ${u.status === 'approved' ? 'selected' : ''}>✅ Approved</option>
              <option value="pending"  ${u.status === 'pending'  ? 'selected' : ''}>⏳ Pending</option>
            </select>
          </div>

          <!-- Photo -->
          <div class="form-group" style="grid-column:1/-1">
            <label class="form-label">Update Photo <span style="color:var(--slate-400);font-weight:400">(optional — leave blank to keep current)</span></label>
            <div class="file-upload-area" id="edit-photo-dropzone" style="min-height:80px;padding:16px">
              <input type="file" id="edit-photo" accept="image/*" />
              <div style="font-size:1.4rem">📷</div>
              <p style="margin:4px 0 0;font-size:.82rem;color:var(--slate-500)">Click or drag photo here</p>
              ${u.photo_url ? `<img src="${u.photo_url}" id="edit-photo-preview"
                style="max-width:80px;max-height:80px;border-radius:8px;margin-top:8px;border:2px solid var(--indigo-200);object-fit:cover" />` : `<img id="edit-photo-preview" src="" style="display:none;max-width:80px;max-height:80px;border-radius:8px;margin-top:8px;border:2px solid var(--indigo-200);object-fit:cover" />`}
            </div>
          </div>

        </div>

        <div id="edit-form-error" class="alert alert-error" style="display:none;margin-top:10px"></div>

        <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid var(--slate-100)">
          <button type="button" class="btn btn-outline" onclick="EduFace.closeModal('edit-modal')">Cancel</button>
          <button type="submit" class="btn btn-primary" id="edit-save-btn">💾 Save Changes</button>
        </div>
      </form>`;

    // Photo preview
    document.getElementById('edit-photo')?.addEventListener('change', function() {
      EduFace.previewImage(this, 'edit-photo-preview');
    });

    // Photo dropzone
    const dz = document.getElementById('edit-photo-dropzone');
    if (dz) {
      dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('dragover'); });
      dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
      dz.addEventListener('drop', e => {
        e.preventDefault(); dz.classList.remove('dragover');
        const fi = document.getElementById('edit-photo');
        if (fi && e.dataTransfer.files[0]) {
          fi.files = e.dataTransfer.files;
          EduFace.previewImage(fi, 'edit-photo-preview');
        }
      });
      dz.addEventListener('click', e => {
        if (e.target.tagName !== 'INPUT') document.getElementById('edit-photo')?.click();
      });
    }

    // Form submit — POST /api/admin/teachers/<id>/edit  or  /api/admin/students/<id>/edit
    document.getElementById('edit-record-form').addEventListener('submit', async e => {
      e.preventDefault();
      const errEl  = document.getElementById('edit-form-error');
      const saveBtn = document.getElementById('edit-save-btn');
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="spinner"></span> Saving…';

      const fd = new FormData();
      fd.append('name',     document.getElementById('edit-name').value.trim());
      fd.append('email',    document.getElementById('edit-email').value.trim());
      fd.append('mobile',   document.getElementById('edit-mobile').value.trim());
      fd.append('dept',     document.getElementById('edit-dept').value);
      fd.append('userid',   document.getElementById('edit-userid').value.trim());
      fd.append('status',   document.getElementById('edit-status').value);
      const pwd = document.getElementById('edit-password').value;
      if (pwd) fd.append('password', pwd);
      if (!isTeacher) {
        fd.append('rollno', document.getElementById('edit-rollno')?.value.trim() || '');
      }
      const photoFile = document.getElementById('edit-photo')?.files[0];
      if (photoFile) fd.append('photo', photoFile);

      const editUrl = isTeacher
        ? `/api/admin/teachers/${id}/edit`
        : `/api/admin/students/${id}/edit`;

      const res = await EduFace.postForm(editUrl, fd);

      saveBtn.disabled = false;
      saveBtn.textContent = '💾 Save Changes';

      if (res.ok) {
        EduFace.closeModal('edit-modal');
        EduFace.toast(res.msg || 'Saved successfully!', 'success');
        // Refresh the table
        if (isTeacher) renderTeachers('');
        else           renderStudents('');
        renderOverview();
      } else {
        if (errEl) {
          errEl.textContent  = res.msg || 'Save failed. Please check the fields.';
          errEl.style.display = 'block';
        }
      }
    });

    EduFace.openModal('edit-modal');
  };

  // ── Init ──────────────────────────────────────────────────
  showSection('overview');
});
