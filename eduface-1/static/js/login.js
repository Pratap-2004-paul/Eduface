// ============================================================
// EDUFACE — Login Page JS
// API URLs: /api/auth/login  /api/auth/me  /api/auth/send-otp  etc.
// Redirects: /pages/admin.html  /pages/teacher.html  /pages/student.html
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {

  // ── If already logged in, redirect straight to dashboard ──
  try {
    const me = await EduFace.get('/api/auth/me');
    if (me.ok) {
      if (me.role === 'admin')   return EduFace.navigate('/pages/admin.html');
      if (me.role === 'teacher') return EduFace.navigate('/pages/teacher.html');
      if (me.role === 'student') return EduFace.navigate('/pages/student.html');
    }
  } catch (_) { /* not logged in, stay on login page */ }

  // ── Drag & drop init ──────────────────────────────────────
  EduFace.initDropzones();

  // ── Error display helper ──────────────────────────────────
  function showError(id, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
  }

  // ── Generic login function ────────────────────────────────
  async function doLogin(role, userid, password, errorId, submitBtn) {
    submitBtn.disabled = true;
    const origLabel = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner"></span> Logging in…';

    // Correct URL: /api/auth/login
    const res = await EduFace.post('/api/auth/login', { role, userid, password });

    submitBtn.disabled = false;
    submitBtn.innerHTML = origLabel;

    if (res.ok) {
      const name = res.user?.name || res.name || role;
      EduFace.toast(`Welcome, ${name}! 👋`, 'success');
      setTimeout(() => {
        // Correct redirect URLs — Flask serves these via /pages/<page>
        if (role === 'admin')   EduFace.navigate('/pages/admin.html');
        if (role === 'teacher') EduFace.navigate('/pages/teacher.html');
        if (role === 'student') EduFace.navigate('/pages/student.html');
      }, 700);
    } else {
      showError(errorId, res.msg || 'Login failed. Please check your credentials.');
    }
  }

  // ── Admin form ────────────────────────────────────────────
  document.getElementById('admin-login-form')?.addEventListener('submit', e => {
    e.preventDefault();
    doLogin(
      'admin',
      document.getElementById('admin-uid').value.trim(),
      document.getElementById('admin-pwd').value,
      'admin-error',
      e.target.querySelector('button[type=submit]')
    );
  });

  // ── Teacher form ──────────────────────────────────────────
  document.getElementById('teacher-login-form')?.addEventListener('submit', e => {
    e.preventDefault();
    doLogin(
      'teacher',
      document.getElementById('teacher-uid').value.trim(),
      document.getElementById('teacher-pwd').value,
      'teacher-error',
      e.target.querySelector('button[type=submit]')
    );
  });

  // ── Student form ──────────────────────────────────────────
  document.getElementById('student-login-form')?.addEventListener('submit', e => {
    e.preventDefault();
    doLogin(
      'student',
      document.getElementById('student-uid').value.trim(),
      document.getElementById('student-pwd').value,
      'student-error',
      e.target.querySelector('button[type=submit]')
    );
  });

  // ── Modal open/close ──────────────────────────────────────
  document.querySelectorAll('[data-open-modal]').forEach(btn =>
    btn.addEventListener('click', () => EduFace.openModal(btn.dataset.openModal)));
  document.querySelectorAll('[data-close-modal]').forEach(btn =>
    btn.addEventListener('click', () => {
      EduFace.closeModal(btn.dataset.closeModal);
      if (btn.dataset.closeModal === 'forgot-modal') resetForgot();
    }));
  document.querySelectorAll('.open-forgot').forEach(btn =>
    btn.addEventListener('click', () => EduFace.openModal('forgot-modal')));
  document.querySelectorAll('.modal-overlay').forEach(overlay =>
    overlay.addEventListener('click', e => {
      if (e.target === overlay) {
        EduFace.closeModal(overlay.id);
        if (overlay.id === 'forgot-modal') resetForgot();
      }
    }));

  // ── Forgot Password / OTP ─────────────────────────────────
  let _forgotIdentifier = '';

  // Tab switching (email / mobile)
  document.querySelectorAll('.recovery-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.recovery-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const type = tab.dataset.tab;
      document.getElementById('forgot-email-block').style.display  = type === 'email'  ? 'block' : 'none';
      document.getElementById('forgot-mobile-block').style.display = type === 'mobile' ? 'block' : 'none';
    });
  });

  // Send OTP — calls /api/auth/send-otp
  document.getElementById('send-otp-btn')?.addEventListener('click', async () => {
    const method = document.querySelector('.recovery-tab.active')?.dataset.tab || 'email';
    const identifier = method === 'email'
      ? document.getElementById('forgot-email').value.trim()
      : document.getElementById('forgot-mobile').value.trim();

    if (!identifier) { EduFace.toast('Please enter your ' + method + '.', 'error'); return; }
    _forgotIdentifier = identifier;

    const btn = document.getElementById('send-otp-btn');
    btn.disabled = true; btn.textContent = 'Sending…';

    const res = await EduFace.post('/api/auth/send-otp', { method, identifier });

    btn.disabled = false; btn.textContent = 'Send OTP 📨';

    if (res.ok) {
      EduFace.toast(res.msg || 'OTP sent!', 'success');
      if (res.otp_demo) EduFace.toast(`Demo OTP: ${res.otp_demo}`, 'info', 8000);
      document.getElementById('forgot-step-1').style.display = 'none';
      document.getElementById('forgot-step-2').style.display = 'block';
    } else {
      EduFace.toast(res.msg || 'Failed to send OTP.', 'error');
    }
  });

  // Verify OTP — calls /api/auth/verify-otp
  document.getElementById('verify-otp-btn')?.addEventListener('click', async () => {
    const otp = document.getElementById('forgot-otp').value.trim();
    if (!otp) { EduFace.toast('Please enter the OTP.', 'error'); return; }

    const btn = document.getElementById('verify-otp-btn');
    btn.disabled = true; btn.textContent = 'Verifying…';

    const res = await EduFace.post('/api/auth/verify-otp', { identifier: _forgotIdentifier, otp });

    btn.disabled = false; btn.textContent = 'Verify OTP ✓';

    if (res.ok) {
      document.getElementById('forgot-step-2').style.display = 'none';
      document.getElementById('forgot-step-3').style.display = 'block';
      document.getElementById('recovered-userid').textContent  = res.userid || '—';
      document.getElementById('recovered-hint').textContent    = res.password_hint || '—';
    } else {
      EduFace.toast(res.msg || 'Invalid OTP.', 'error');
    }
  });

  function resetForgot() {
    document.getElementById('forgot-step-1').style.display = 'block';
    document.getElementById('forgot-step-2').style.display = 'none';
    document.getElementById('forgot-step-3').style.display = 'none';
    ['forgot-email','forgot-mobile','forgot-otp'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    _forgotIdentifier = '';
  }

  // ── Teacher Registration — calls /api/teachers/register ───
  const tStep = EduFace.setupMultiStep('teacher-reg', 3);

  document.getElementById('teacher-reg-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('[type=submit]');
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Submitting…';

    const fd = new FormData();
    fd.append('name',     document.getElementById('treg-name').value.trim());
    fd.append('mobile',   document.getElementById('treg-mobile').value.trim());
    fd.append('email',    document.getElementById('treg-email').value.trim());
    fd.append('dept',     document.getElementById('treg-dept').value);
    fd.append('userid',   document.getElementById('treg-userid').value.trim());
    fd.append('password', document.getElementById('treg-password').value);
    const photo = document.getElementById('treg-photo')?.files[0];
    if (photo) fd.append('photo', photo);

    const res = await EduFace.postForm('/api/teachers/register', fd);

    btn.disabled = false; btn.textContent = 'Submit for Approval 🚀';

    if (res.ok) {
      EduFace.closeModal('teacher-reg-modal');
      tStep.reset();
      e.target.reset();
      document.getElementById('treg-photo-preview').style.display = 'none';
      EduFace.openModal('pending-modal');
    } else {
      EduFace.toast(res.msg || 'Registration failed.', 'error');
    }
  });

  // ── Student Registration — calls /api/students/register ───
  const sStep = EduFace.setupMultiStep('student-reg', 3);

  document.getElementById('student-reg-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('[type=submit]');
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Submitting…';

    const fd = new FormData();
    fd.append('name',     document.getElementById('sreg-name').value.trim());
    fd.append('mobile',   document.getElementById('sreg-mobile').value.trim());
    fd.append('email',    document.getElementById('sreg-email').value.trim());
    fd.append('dept',     document.getElementById('sreg-dept').value);
    fd.append('rollno',   document.getElementById('sreg-rollno').value.trim());
    fd.append('userid',   document.getElementById('sreg-userid').value.trim());
    fd.append('password', document.getElementById('sreg-password').value);

    // Add profile photo (required)
    const photo = document.getElementById('sreg-photo')?.files[0];
    if (photo) {
      fd.append('photo', photo);
    } else {
      EduFace.toast('Profile photo is required.', 'error');
      btn.disabled = false;
      btn.textContent = 'Submit for Approval 🚀';
      return;
    }

    // Add captured face photos if available
    if (window.capturedFacePhotos && window.capturedFacePhotos.formData) {
      const faceFormData = window.capturedFacePhotos.formData;
      // Copy all face photos to main form data
      for (let pair of faceFormData.entries()) {
        fd.append(pair[0], pair[1]);
      }
      console.log(`Submitting with ${window.capturedFacePhotos.count} face photos`);
    } else {
      console.log('No face photos captured - proceeding without them');
    }

    const res = await EduFace.postForm('/api/students/register', fd);

    btn.disabled = false;
    btn.textContent = 'Submit for Approval 🚀';

    if (res.ok) {
      EduFace.closeModal('student-reg-modal');
      sStep.reset();
      e.target.reset();
      document.getElementById('sreg-photo-preview').style.display = 'none';
      document.getElementById('sreg-face-capture-status').style.display = 'none';
      window.capturedFacePhotos = null;  // Clear captured photos
      EduFace.openModal('pending-modal');
      EduFace.toast(res.msg || 'Registration submitted successfully!', 'success');
    } else {
      EduFace.toast(res.msg || 'Registration failed.', 'error');
    }
  });

  // ── Update captured face photos count display ─────────────
  // This is called from student_face_enrollment.js after capture completes
  window.updateFaceCaptureStatus = function(count) {
    if (count > 0) {
      document.getElementById('sreg-face-capture-status').style.display = 'block';
      document.getElementById('sreg-face-count').textContent = count;
    }
  };

  // ── Photo previews ────────────────────────────────────────
  document.getElementById('treg-photo')?.addEventListener('change', function() {
    EduFace.previewImage(this, 'treg-photo-preview');
  });
  document.getElementById('sreg-photo')?.addEventListener('change', function() {
    EduFace.previewImage(this, 'sreg-photo-preview');
  });

});
