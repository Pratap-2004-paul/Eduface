// ============================================================
// EDUFACE — Student Dashboard JS
// All fetch calls use /api/student/* and /api/chats/*
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {

  // ── Auth guard ─────────────────────────────────────────────
  const user = await EduFace.requireRole('student');
  if (!user) return;

  // ── Date ──────────────────────────────────────────────────
  const todayEl = document.getElementById('today-date');
  if (todayEl) todayEl.textContent =
    new Date().toLocaleDateString('en-IN', { weekday:'short', day:'numeric', month:'short' });

  // ── Populate profile ──────────────────────────────────────
  function fillProfile(u) {
    if (!u) return;
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '—'; };
    setText('profile-name',          u.name);
    setText('profile-dept',          u.dept);
    setText('profile-name-greeting', u.name?.split(' ')[0]);
    setText('pf-name',    u.name);
    setText('pf-email',   u.email);
    setText('pf-mobile',  u.mobile);
    setText('pf-dept',    u.dept);
    setText('pf-userid',  u.userid);
    setText('pf-rollno',  u.rollno || '—');
    setText('pf-joined',  EduFace.fmtDate(u.created_at));
    setText('sb-name',    u.name);
    setText('sb-dept',    u.dept);
    setText('sb-uid',     u.userid);

    if (u.photo_url) {
      const ph = document.getElementById('profile-photo');
      if (ph) { ph.src = u.photo_url; ph.style.display = 'block'; }
      const pi = document.getElementById('profile-initials');
      if (pi) pi.style.display = 'none';
      const sb = document.getElementById('sb-avatar');
      if (sb) sb.innerHTML = `<img src="${u.photo_url}" style="width:100%;height:100%;border-radius:50%;object-fit:cover"/>`;
    } else {
      const pi = document.getElementById('profile-initials');
      if (pi) pi.textContent = EduFace.initials(u.name);
      const sb = document.getElementById('sb-avatar');
      if (sb) sb.textContent = EduFace.initials(u.name);
    }
  }

  // GET /api/student/profile
  try {
    const p = await EduFace.get('/api/student/profile');
    fillProfile(p.id ? p : user);
  } catch { fillProfile(user); }

  // ── Home summary stats ─────────────────────────────────────
  // Load attendance for home stats
  try {
    const records = await EduFace.get('/api/student/attendance');
    if (Array.isArray(records)) {
      const total   = records.length;
      const present = records.filter(r => r.present).length;
      const pct     = total ? Math.round((present / total) * 100) : 0;
      const statPct = document.getElementById('home-stat-pct');
      const statSes = document.getElementById('home-stat-sessions');
      if (statPct) statPct.textContent = pct + '%';
      if (statSes) statSes.textContent = total;
    }
  } catch {}
  try {
    const chats = await EduFace.get('/api/chats');
    const statChats = document.getElementById('home-stat-chats');
    if (statChats && Array.isArray(chats)) statChats.textContent = chats.length;
  } catch {}

  // ── Section navigation ────────────────────────────────────
  const titles = { home: 'Dashboard', attendance: 'My Attendance', chat: 'Messages' };

  function showSection(id) {
    document.querySelectorAll('.student-section').forEach(s =>
      s.classList.toggle('hidden', s.id !== `section-${id}`));
    document.querySelectorAll('.nav-item[data-section]').forEach(n =>
      n.classList.toggle('active', n.dataset.section === id));
    const titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = titles[id] || id;
    if (id === 'attendance') renderAttendance();
    if (id === 'chat')       initChat();
  }

  document.querySelectorAll('.nav-item[data-section]').forEach(n =>
    n.addEventListener('click', () => showSection(n.dataset.section)));
  document.getElementById('action-attendance')?.addEventListener('click', () => showSection('attendance'));
  document.getElementById('action-chat')?.addEventListener('click', () => showSection('chat'));

  document.getElementById('logout-btn')?.addEventListener('click', async () => {
    await EduFace.post('/api/auth/logout');
    EduFace.navigate('/');
  });

  // ── ATTENDANCE — GET /api/student/attendance ──────────────
  async function renderAttendance() {
    const container = document.getElementById('attend-subjects');
    if (!container) return;
    container.innerHTML = '<p class="text-muted text-center" style="padding:28px">Loading…</p>';

    const records = await EduFace.get('/api/student/attendance');

    if (!Array.isArray(records) || !records.length) {
      container.innerHTML = `
        <div class="text-center" style="padding:60px">
          <div style="font-size:3rem;margin-bottom:16px">📋</div>
          <h3>No attendance records yet.</h3>
          <p class="text-muted">Your teacher hasn't marked any sessions yet.</p>
        </div>`;
      updateSummaryBar(0, 0);
      return;
    }

    const total   = records.length;
    const present = records.filter(r => r.present).length;
    updateSummaryBar(total, present);

    // Group by subject
    const bySubject = {};
    records.forEach(r => {
      if (!bySubject[r.subject]) bySubject[r.subject] = [];
      bySubject[r.subject].push(r);
    });

    container.innerHTML = Object.entries(bySubject).map(([subject, rows]) => {
      const p    = rows.filter(r => r.present).length;
      const pPct = Math.round((p / rows.length) * 100);
      return `
        <div class="subject-attend-block">
          <div class="subject-attend-title">
            ${subject}
            <span class="badge badge-${pPct >= 75 ? 'green' : pPct >= 50 ? 'amber' : 'red'}" style="margin-left:8px">${pPct}%</span>
          </div>
          <div class="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Name</th><th>Date</th><th>Dept / Class</th><th>Subject</th><th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                ${rows.map(r => `
                  <tr>
                    <td style="font-weight:500">${r.student_name}</td>
                    <td>${EduFace.fmtDate(r.date)} ${r.time || ''}</td>
                    <td>${r.dept}</td>
                    <td>${r.subject}</td>
                    <td><span class="badge badge-${r.present ? 'green' : 'red'}">${r.present ? '✓ Present' : '✗ Absent'}</span></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    }).join('');
  }

  function updateSummaryBar(total, present) {
    const absent = total - present;
    const pct    = total ? Math.round((present / total) * 100) : 0;
    const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setText('attend-total',   total);
    setText('attend-present', present);
    setText('attend-absent',  absent);
    setText('attend-pct',     pct + '%');
    const bar = document.getElementById('attend-pct-bar');
    if (bar) {
      bar.style.width      = pct + '%';
      bar.style.background = pct >= 75 ? 'var(--green-500)' : pct >= 50 ? 'var(--amber-500)' : 'var(--red-500)';
    }
  }

  // ── CHAT ──────────────────────────────────────────────────
  let activeChat = null;
  let pollTimer  = null;

  async function initChat() {
    await renderChatList();
  }

  // GET /api/chats
  async function renderChatList() {
    const list = document.getElementById('chat-list');
    if (!list) return;

    const chats = await EduFace.get('/api/chats');

    list.innerHTML = `
      <div class="chat-item" id="new-chat-btn" style="border-bottom:2px solid var(--indigo-100)">
        <div class="chat-item-avatar" style="background:var(--indigo-100);color:var(--indigo-700);font-size:1.2rem">+</div>
        <div>
          <div class="chat-item-name" style="color:var(--indigo-700)">New Chat</div>
          <div class="chat-item-preview">Message a teacher</div>
        </div>
      </div>` +
      (Array.isArray(chats) ? chats : []).map(c => `
        <div class="chat-item ${activeChat?.id === c.id ? 'active' : ''}" data-chat-id="${c.id}">
          ${c.other_photo
            ? `<img src="${c.other_photo}" class="chat-item-avatar" style="object-fit:cover"/>`
            : `<div class="chat-item-avatar">${EduFace.initials(c.teacher_name || '')}</div>`}
          <div style="flex:1;min-width:0">
            <div style="display:flex;justify-content:space-between">
              <div class="chat-item-name">${c.teacher_name || '—'}</div>
              <div class="chat-item-time">${c.last_time ? c.last_time.slice(11,16) : ''}</div>
            </div>
            <div class="chat-item-preview">${c.last_message || 'No messages yet'}</div>
          </div>
        </div>`).join('');

    list.querySelectorAll('.chat-item[data-chat-id]').forEach(item =>
      item.addEventListener('click', () => openChat(parseInt(item.dataset.chatId), chats)));
    document.getElementById('new-chat-btn')?.addEventListener('click', showNewChatDialog);
  }

  async function openChat(chatId, chatsCache = null) {
    clearInterval(pollTimer);
    const chats = chatsCache || await EduFace.get('/api/chats').then(r => Array.isArray(r) ? r : []);
    activeChat = chats.find(c => c.id === chatId);
    if (!activeChat) return;

    document.getElementById('chat-other-name').textContent = activeChat.teacher_name || '—';
    document.getElementById('chat-other-role').textContent = activeChat.other_dept   || 'Teacher';
    document.getElementById('chat-placeholder').style.display = 'none';
    document.getElementById('chat-active').style.display     = 'flex';

    await loadMessages(chatId);
    renderChatList();
    pollTimer = setInterval(() => loadMessages(chatId), 5000);
  }

  // GET /api/chats/<id>/messages
  async function loadMessages(chatId) {
    const msgs = await EduFace.get(`/api/chats/${chatId}/messages`);
    const el   = document.getElementById('chat-messages');
    if (!el) return;
    el.innerHTML = (Array.isArray(msgs) ? msgs : []).map(m => {
      const mine = m.sender_type === 'student';
      return `<div class="message-bubble message-${mine ? 'outgoing' : 'incoming'}">
        ${m.text}
        <div class="message-time">${(m.created_at || '').slice(11,16)}</div>
      </div>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
  }

  // POST /api/chats/<id>/messages
  async function sendMsg() {
    if (!activeChat) return;
    const input = document.getElementById('chat-input');
    const text  = (input?.value || '').trim();
    if (!text) return;
    input.value = '';
    const res = await EduFace.post(`/api/chats/${activeChat.id}/messages`, { text });
    if (res.ok) { await loadMessages(activeChat.id); renderChatList(); }
    else EduFace.toast(res.msg || 'Send failed.', 'error');
  }

  document.getElementById('send-msg-btn')?.addEventListener('click', sendMsg);
  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  });

  // New chat dialog — GET /api/teachers/list
  async function showNewChatDialog() {
    const teachers = await EduFace.get('/api/teachers/list');
    const chats    = await EduFace.get('/api/chats');
    const existIds = new Set((Array.isArray(chats) ? chats : []).map(c => c.teacher_id));

    document.getElementById('new-chat-list').innerHTML =
      (Array.isArray(teachers) ? teachers : []).map(t => `
        <div class="chat-item" data-tid="${t.id}" style="cursor:pointer">
          ${t.photo_url ? `<img src="${t.photo_url}" class="chat-item-avatar" style="object-fit:cover"/>` : `<div class="chat-item-avatar">${EduFace.initials(t.name)}</div>`}
          <div>
            <div class="chat-item-name">${t.name}</div>
            <div class="chat-item-preview">${t.dept}</div>
          </div>
          ${existIds.has(t.id) ? '<span class="badge badge-indigo" style="margin-left:auto">Existing</span>' : ''}
        </div>`).join('') || '<p class="text-muted" style="padding:16px">No teachers available.</p>';

    EduFace.openModal('new-chat-modal');

    // POST /api/chats
    document.querySelectorAll('#new-chat-list .chat-item[data-tid]').forEach(item => {
      item.addEventListener('click', async () => {
        EduFace.closeModal('new-chat-modal');
        const res = await EduFace.post('/api/chats', { other_id: parseInt(item.dataset.tid) });
        if (res.ok) await openChat(res.chat_id);
      });
    });
  }

  document.querySelector('[data-close-modal="new-chat-modal"]')
    ?.addEventListener('click', () => EduFace.closeModal('new-chat-modal'));

  // ── Init ──────────────────────────────────────────────────
  showSection('home');
});
