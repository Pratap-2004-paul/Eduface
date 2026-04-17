// ============================================================
// EDUFACE — Teacher Dashboard JS
// All fetch calls use /api/teacher/* and /api/chats/*
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {

  // ── Auth guard ─────────────────────────────────────────────
  const user = await EduFace.requireRole('teacher');
  if (!user) return;

  // ── Date ──────────────────────────────────────────────────
  const todayEl = document.getElementById('today-date');
  if (todayEl) todayEl.textContent =
    new Date().toLocaleDateString('en-IN', { weekday:'short', day:'numeric', month:'short' });

  // ── Populate profile ──────────────────────────────────────
  function fillProfile(u) {
    if (!u) return;
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '—'; };
    setText('profile-name',         u.name);
    setText('profile-dept',         u.dept);
    setText('profile-name-greeting', u.name?.split(' ')[0]);
    setText('pf-name',    u.name);
    setText('pf-email',   u.email);
    setText('pf-mobile',  u.mobile);
    setText('pf-dept',    u.dept);
    setText('pf-userid',  u.userid);
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

  // Load full profile from server — /api/teacher/profile
  try {
    const profile = await EduFace.get('/api/teacher/profile');
    fillProfile(profile.id ? profile : user);
  } catch { fillProfile(user); }

  // ── Section navigation ────────────────────────────────────
  const titles = { home: 'Dashboard', attendance: 'Mark Attendance', chat: 'Messages' };

  function showSection(id) {
    document.querySelectorAll('.teacher-section').forEach(s =>
      s.classList.toggle('hidden', s.id !== `section-${id}`));
    document.querySelectorAll('.nav-item[data-section]').forEach(n =>
      n.classList.toggle('active', n.dataset.section === id));
    const titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = titles[id] || id;
    if (id === 'attendance') initAttendance();
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

  // ── ATTENDANCE ────────────────────────────────────────────
  let cameraStream = null;

  function initAttendance() {
    const dateEl = document.getElementById('attend-date');
    const timeEl = document.getElementById('attend-time');
    if (dateEl) dateEl.value = EduFace.todayStr();
    if (timeEl) timeEl.value = EduFace.fmtTime();
  }

  document.getElementById('start-camera-btn')?.addEventListener('click', async () => {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = document.getElementById('camera-video');
      video.srcObject = cameraStream;
      video.style.display = 'block';
      document.getElementById('camera-placeholder').style.display = 'none';
      document.getElementById('capture-btn').style.display  = 'inline-flex';
      document.getElementById('start-camera-btn').style.display = 'none';
    } catch { EduFace.toast('Camera access denied. Upload a photo instead.', 'error'); }
  });

  document.getElementById('capture-btn')?.addEventListener('click', () => {
    const video  = document.getElementById('camera-video');
    const canvas = document.getElementById('capture-canvas');
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.style.display = 'block';
    video.style.display  = 'none';
    if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
    document.getElementById('capture-btn').style.display  = 'none';
    document.getElementById('retake-btn').style.display   = 'inline-flex';
    EduFace.toast('Photo captured!', 'success');
    // Store captured blob for upload
    canvas.toBlob(blob => { window._capturedBlob = blob; }, 'image/jpeg');
  });

  document.getElementById('retake-btn')?.addEventListener('click', () => {
    document.getElementById('capture-canvas').style.display = 'none';
    document.getElementById('camera-placeholder').style.display = 'flex';
    document.getElementById('retake-btn').style.display   = 'none';
    document.getElementById('start-camera-btn').style.display = 'inline-flex';
    window._capturedBlob = null;
  });

  document.getElementById('photo-upload-input')?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const img = document.getElementById('uploaded-preview');
    if (img) { img.src = URL.createObjectURL(file); img.style.display = 'block'; }
    const ph = document.getElementById('camera-placeholder');
    if (ph) ph.style.display = 'none';
  });

  // Submit attendance — POST /api/teacher/attendance
  document.getElementById('attend-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('mark-attend-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Processing face recognition…';

    const fd = new FormData();
    fd.append('date',    document.getElementById('attend-date').value);
    fd.append('time',    document.getElementById('attend-time').value);
    fd.append('dept',    document.getElementById('attend-dept').value);
    fd.append('subject', document.getElementById('attend-subject').value.trim());

    // Attach photo
    if (window._capturedBlob) {
      fd.append('photo', new File([window._capturedBlob], 'capture.jpg', { type: 'image/jpeg' }));
    } else {
      const uploadInput = document.getElementById('photo-upload-input');
      if (uploadInput?.files[0]) fd.append('photo', uploadInput.files[0]);
    }

    const res = await EduFace.postForm('/api/teacher/attendance', fd);

    btn.disabled = false;
    btn.innerHTML = '🎯 Mark Attendance Now';

    if (res.ok) {
      showAttendanceResult(res.results, res.summary,
        document.getElementById('attend-subject').value,
        document.getElementById('attend-date').value);
      EduFace.toast(`Attendance marked! ${res.summary?.present} present, ${res.summary?.absent} absent.`, 'success');
    } else {
      EduFace.toast(res.msg || 'Failed to mark attendance.', 'error');
    }
  });

  function showAttendanceResult(results, summary, subject, date) {
    const area = document.getElementById('attendance-result-area');
    if (!area) return;
    area.style.display = 'block';
    area.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <h4 style="font-family:var(--font-display)">${subject} — ${EduFace.fmtDate(date)}</h4>
        <div>
          <span class="badge badge-green">✓ ${summary?.present ?? 0} Present</span>
          <span class="badge badge-red" style="margin-left:6px">✗ ${summary?.absent ?? 0} Absent</span>
        </div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead><tr><th>Student</th><th>Dept</th><th>Status</th></tr></thead>
          <tbody>
            ${(results || []).map(r => `
              <tr>
                <td>
                  <div style="display:flex;align-items:center;gap:10px">
                    ${r.photo_url
                      ? `<img src="${r.photo_url}" class="avatar" style="object-fit:cover"/>`
                      : `<div class="avatar">${EduFace.initials(r.student_name)}</div>`}
                    <span style="font-weight:500">${r.student_name}</span>
                  </div>
                </td>
                <td>${r.dept}</td>
                <td><span class="badge badge-${r.present ? 'green' : 'red'}">${r.present ? '✓ Present' : '✗ Absent'}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  // ── CHAT ──────────────────────────────────────────────────
  let activeChat    = null;
  let pollTimer     = null;

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
          <div class="chat-item-preview">Message a student</div>
        </div>
      </div>` +
      (Array.isArray(chats) ? chats : []).map(c => `
        <div class="chat-item ${activeChat?.id === c.id ? 'active' : ''}" data-chat-id="${c.id}">
          ${c.other_photo
            ? `<img src="${c.other_photo}" class="chat-item-avatar" style="object-fit:cover"/>`
            : `<div class="chat-item-avatar">${EduFace.initials(c.student_name || '')}</div>`}
          <div style="flex:1;min-width:0">
            <div style="display:flex;justify-content:space-between">
              <div class="chat-item-name">${c.student_name || '—'}</div>
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

    document.getElementById('chat-other-name').textContent = activeChat.student_name || '—';
    document.getElementById('chat-other-role').textContent = activeChat.other_dept   || 'Student';
    document.getElementById('chat-placeholder').style.display = 'none';
    document.getElementById('chat-active').style.display     = 'flex';

    await loadMessages(chatId);
    renderChatList();
    // Poll every 5 s for new messages
    pollTimer = setInterval(() => loadMessages(chatId), 5000);
  }

  // GET /api/chats/<id>/messages
  async function loadMessages(chatId) {
    const msgs = await EduFace.get(`/api/chats/${chatId}/messages`);
    const el   = document.getElementById('chat-messages');
    if (!el) return;
    el.innerHTML = (Array.isArray(msgs) ? msgs : []).map(m => {
      const mine = m.sender_type === 'teacher';
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

  // New chat dialog — GET /api/students/list
  async function showNewChatDialog() {
    const students = await EduFace.get('/api/students/list');
    const chats    = await EduFace.get('/api/chats');
    const existIds = new Set((Array.isArray(chats) ? chats : []).map(c => c.student_id));

    document.getElementById('new-chat-list').innerHTML =
      (Array.isArray(students) ? students : []).map(s => `
        <div class="chat-item" data-sid="${s.id}" style="cursor:pointer">
          ${s.photo_url ? `<img src="${s.photo_url}" class="chat-item-avatar" style="object-fit:cover"/>` : `<div class="chat-item-avatar">${EduFace.initials(s.name)}</div>`}
          <div>
            <div class="chat-item-name">${s.name}</div>
            <div class="chat-item-preview">${s.dept}</div>
          </div>
          ${existIds.has(s.id) ? '<span class="badge badge-indigo" style="margin-left:auto">Existing</span>' : ''}
        </div>`).join('') || '<p class="text-muted" style="padding:16px">No students available.</p>';

    EduFace.openModal('new-chat-modal');

    // POST /api/chats
    document.querySelectorAll('#new-chat-list .chat-item[data-sid]').forEach(item => {
      item.addEventListener('click', async () => {
        EduFace.closeModal('new-chat-modal');
        const res = await EduFace.post('/api/chats', { other_id: parseInt(item.dataset.sid) });
        if (res.ok) await openChat(res.chat_id);
      });
    });
  }

  document.querySelector('[data-close-modal="new-chat-modal"]')
    ?.addEventListener('click', () => EduFace.closeModal('new-chat-modal'));

  // ── Init ──────────────────────────────────────────────────
  showSection('home');
});
