/* ============================================================
   SkyStore – Frontend Application (app.js)
   ============================================================ */

// ─── State ───────────────────────────────────────────────────
const State = {
  user: null,
  currentSection: 'home',
  currentView: 'grid',      // 'grid' | 'list'
  sortBy: 'uploaded_at',
  sortOrder: 'DESC',
  uploadFiles: [],
  lastTrashedId: null,
  lastTrashedSection: 'home',
  currentPreviewFileId: null,
  currentShareFileId: null,
  currentNoteFileId: null,
  currentFolderId: null,
  pendingUnlockFolderId: null,
  folders: [],
};

// ─── ICONS ───────────────────────────────────────────────────
function getFileIcon(mime, name) {
  if (!mime) return '📄';
  if (mime.startsWith('image/')) return '🖼️';
  if (mime.startsWith('video/')) return '🎬';
  if (mime.startsWith('audio/')) return '🎵';
  if (mime === 'application/pdf') return '📕';
  if (mime.includes('word')) return '📝';
  if (mime.includes('excel') || mime.includes('spreadsheet')) return '📊';
  if (mime.includes('powerpoint') || mime.includes('presentation')) return '📢';
  if (mime.includes('zip') || mime.includes('rar') || mime.includes('7z') || mime.includes('tar')) return '🗜️';
  if (mime.startsWith('text/')) return '📄';
  if (mime.includes('javascript') || mime.includes('python') || mime.includes('html')) return '💻';
  return '📁';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  if (diff < 2592000) return Math.floor(diff / 86400) + 'd ago';
  return new Date(isoStr).toLocaleDateString();
}

// ─── API HELPERS ─────────────────────────────────────────────
async function api(method, path, body) {
  const token = localStorage.getItem('token');
  const opts = { method, headers: {} };

  if (token) {
    opts.headers['Authorization'] = `Bearer ${token}`;
  }

  if (body instanceof FormData) {
    opts.body = body;
  } else if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  try {
    const res = await fetch(path, opts);
    // Try to parse as JSON – if server returned HTML (crash), handle gracefully
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      // Server returned non-JSON (HTML error page)
      console.error('Non-JSON response:', text.substring(0, 200));
      return { error: `Server error (${res.status}): ${text.substring(0, 120) || 'Unexpected server response'}`, success: false };
    }
  } catch (err) {
    console.error('Fetch error:', err);
    return { error: 'Cannot reach server – make sure app.py is running on port 5050', success: false };
  }
}

// ─── AUTH ─────────────────────────────────────────────────────
function switchTab(tab) {
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  btn.textContent = 'Signing in...';
  btn.disabled = true;
  const res = await api('POST', '/login', {
    email: document.getElementById('login-username').value,
    password: document.getElementById('login-password').value
  });
  btn.textContent = 'Sign In'; btn.disabled = false;
  if (!res.success) { errEl.textContent = res.error || 'Login failed'; return; }

  // Store Token
  localStorage.setItem('token', res.token);
  State.user = res.user;
  enterApp();
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('reg-btn');
  const errEl = document.getElementById('reg-error');
  btn.textContent = 'Creating...'; btn.disabled = true;
  const res = await api('POST', '/register', {
    username: document.getElementById('reg-username').value,
    email: document.getElementById('reg-email').value,
    password: document.getElementById('reg-password').value
  });
  btn.textContent = 'Create Account'; btn.disabled = false;
  if (res.error) { errEl.textContent = res.error; return; }
  errEl.style.color = 'var(--success)';
  errEl.textContent = '✅ Account created! Please login.';
  setTimeout(() => switchTab('login'), 1200);
}

async function handleLogout() {
  await api('POST', '/logout');
  localStorage.removeItem('token');
  State.user = null;
  document.getElementById('app').classList.add('hidden');
  document.getElementById('auth-screen').classList.remove('hidden');
}

async function checkSession() {
  const token = localStorage.getItem('token');
  if (!token) return;
  const res = await api('GET', '/user');
  if (res.user) {
    State.user = res.user;
    enterApp();
  } else {
    localStorage.removeItem('token');
  }
}

function enterApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  updateSidebarUser();
  loadFolders();
  navigate('home');
  updateStorageBar();
  checkBackupReminder();
  applyTheme(State.user.theme || 'dark');
}

function updateSidebarUser() {
  const u = State.user;
  if (!u) return;
  const displayName = u.name || u.username || 'User';
  document.getElementById('sidebar-username').textContent = displayName;
  document.getElementById('sidebar-email').textContent = u.email;
  document.getElementById('sidebar-avatar').textContent = displayName[0].toUpperCase();
}

// ─── THEME ────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-toggle').textContent = theme === 'dark' ? '🌙' : '☀️';
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  api('POST', '/settings/theme', { theme: next });
  if (State.user) State.user.theme = next;
}

// ─── NAVIGATION ───────────────────────────────────────────────
function navigate(section) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const el = document.getElementById('section-' + section);
  if (el) el.classList.add('active');
  const navEl = document.querySelector(`.nav-item[data-section="${section}"]`);
  if (navEl) navEl.classList.add('active');
  State.currentSection = section;

  // Close sidebar on mobile
  document.getElementById('sidebar').classList.remove('open');

  switch (section) {
    case 'home': loadHome(); break;
    case 'recent': loadFiles('recent', 'recent-files-container'); break;
    case 'starred': loadFiles('starred', 'starred-files-container'); break;
    case 'pinned': loadFiles('pinned', 'pinned-page-container'); break;
    case 'folders': State.currentFolderId = null; loadFolders(); break;
    case 'images': loadFiles('images', 'images-files-container'); break;
    case 'documents': loadFiles('documents', 'documents-files-container'); break;
    case 'videos': loadFiles('videos', 'videos-files-container'); break;
    case 'trash': loadFiles('trash', 'trash-files-container'); break;
    case 'insights': loadInsights(); break;
    case 'activity': loadActivity(); break;
    case 'settings': renderSettings(); break;
  }
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ─── STORAGE BAR ──────────────────────────────────────────────
async function updateStorageBar() {
  const res = await api('GET', '/storage');
  if (res.storage_used === undefined) return;
  const pct = Math.min(res.percentage || 0, 100);
  document.getElementById('sidebar-storage-text').textContent = `${res.storage_used_mb} / ${res.storage_limit_mb} MB`;
  const fill = document.getElementById('sidebar-storage-fill');
  fill.style.width = pct + '%';
  fill.style.background = pct > 80 ? 'linear-gradient(90deg,#ef4444,#f87171)' : 'linear-gradient(90deg,#6366f1,#a78bfa)';
  if (State.user) { State.user.storage_used = res.storage_used; State.user.storage_limit = res.storage_limit; }
}

// ─── HOME ─────────────────────────────────────────────────────
async function loadHome() {
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  document.getElementById('home-greeting').textContent = `${greet}, ${State.user?.username || ''}! 👋`;

  loadQuickStats();
  loadPinnedFiles();
  loadFiles('all', 'home-files-container', { sort_by: State.sortBy, sort_order: State.sortOrder });
}

async function loadQuickStats() {
  const res = await api('GET', '/storage');
  const ins = await api('GET', '/insights');
  document.getElementById('quick-stats').innerHTML = `
    <div class="stat-card"><span class="stat-icon">📁</span><div><div class="stat-label">Total Files</div><div class="stat-value">${ins.total_files || 0}</div></div></div>
    <div class="stat-card"><span class="stat-icon">💾</span><div><div class="stat-label">Used Storage</div><div class="stat-value">${res.storage_used_mb || 0} MB</div></div></div>
    <div class="stat-card"><span class="stat-icon">⭐</span><div><div class="stat-label">Starred</div><div class="stat-value">${ins.most_accessed?.length || 0}</div></div></div>
    <div class="stat-card"><span class="stat-icon">🧹</span><div><div class="stat-label">Unused Files</div><div class="stat-value">${ins.unused_files?.length || 0}</div></div></div>
  `;
}

async function loadPinnedFiles() {
  const res = await api('GET', '/files?category=pinned');
  const grid = document.getElementById('pinned-files-grid');
  const section = document.getElementById('pinned-section');
  if (!res.files || res.files.length === 0) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');
  grid.innerHTML = res.files.map(f => renderFileCard(f)).join('');
}

function changeSortHome() {
  const [by, order] = document.getElementById('sort-select').value.split('-');
  State.sortBy = by; State.sortOrder = order;
  loadFiles('all', 'home-files-container', { sort_by: by, sort_order: order });
}

// ─── FILES ────────────────────────────────────────────────────
async function loadFiles(category, containerId, extra = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading...</p></div>';
  let url = `/files?category=${category}`;
  for (const [k, v] of Object.entries(extra)) url += `&${k}=${encodeURIComponent(v)}`;
  const res = await api('GET', url);
  if (res.error || !res.files) { container.innerHTML = renderEmpty(res.error || 'Error loading files'); return; }
  if (res.files.length === 0) { container.innerHTML = renderEmpty(category === 'trash' ? 'Trash is empty' : 'No files found'); return; }
  container.className = State.currentView === 'list' ? 'files-list' : 'files-grid';
  container.innerHTML = res.files.map(f => renderFileCard(f, category === 'trash')).join('');
}

function renderFileCard(f, isTrashed = false) {
  const icon = getFileIcon(f.mime_type, f.original_name);
  const isImage = f.mime_type && f.mime_type.startsWith('image/');
  const isVideo = f.mime_type && f.mime_type.startsWith('video/');
  const _tk = encodeURIComponent(localStorage.getItem('token') || '');
  const thumb = isImage
    ? `<img src="/files/${f.id}/preview?token=${_tk}" alt="preview" loading="lazy" onerror="this.parentNode.textContent='${icon}'">`
    : isVideo
      ? `<video src="/files/${f.id}/preview?token=${_tk}" muted></video>`
      : `<span class="file-thumb-icon">${icon}</span>`;

  const badges = [
    f.is_starred ? '<span class="badge badge-star">⭐ Starred</span>' : '',
    f.is_pinned ? '<span class="badge badge-pin">📌 Pinned</span>' : '',
    f.notes ? '<span class="badge badge-note">📝 Note</span>' : ''
  ].join('');

  const isSelected = selectedFileIds.has(f.id) ? 'selected' : '';
  const canSummarize = f.original_name.toLowerCase().endsWith('.pdf') || f.original_name.toLowerCase().endsWith('.txt');

  if (isTrashed) {
    return `<div class="file-card" data-id="${f.id}" oncontextmenu="showCtxMenu(event,${f.id},true)">
      <div class="file-badges">${badges}</div>
      <div class="file-thumb">${thumb}</div>
      <div class="file-name" title="${esc(f.original_name)}">${esc(f.original_name)}</div>
      <div class="file-meta"><span>${formatSize(f.size)}</span><span>${timeAgo(f.trashed_at)}</span></div>
      <div class="file-actions">
        <button class="btn-icon" onclick="event.stopPropagation();fileAction(${f.id},'restore')" title="Restore">↩ Restore</button>
        <button class="btn-icon" onclick="event.stopPropagation();confirmDelete(${f.id})" title="Delete Forever" style="color:var(--danger)">🗑 Delete</button>
      </div>
    </div>`;
  }

  return `<div class="file-card ${isSelected}" data-id="${f.id}" 
               onclick="handleFileClick(event, ${f.id}, '${esc(f.original_name)}','${f.mime_type || ''}')" 
               oncontextmenu="showCtxMenu(event,${f.id},false)">
    
    <!-- Selection Indicator -->
    <div class="file-select-indicator" onclick="event.stopPropagation(); toggleSelectFile(${f.id}, this.closest('.file-card'))">
      <div class="checkbox-tick"></div>
    </div>

    <div class="file-badges">${badges}</div>
    <div class="file-thumb">${thumb}</div>
    <div class="file-name" title="${esc(f.original_name)}">${esc(f.original_name)}</div>
    <div class="file-meta">
      <span>${formatSize(f.size)}</span>
      <span>${timeAgo(f.uploaded_at)}</span>
    </div>
    
    <div class="file-actions" onclick="event.stopPropagation()">
      <button class="btn-icon" onclick="downloadFile(${f.id})" title="Download">⬇</button>
      
      <!-- Summarize Button (Only for .txt and .pdf) -->
      ${canSummarize ? `<button class="btn-icon" onclick="openSummarizeModal(${f.id})" title="AI Summarize" style="color:var(--accent)">🤖</button>` : ''}
      
      <!-- Move Button -->
      <button class="btn-icon" onclick="openMoveModal(${f.id})" title="Move to Folder">📂</button>
      
      <button class="btn-icon" onclick="fileAction(${f.id},'${f.is_starred ? 'unstar' : 'star'}')" title="${f.is_starred ? 'Unstar' : 'Star'}" style="color:${f.is_starred ? 'var(--warning)' : ''}">⭐</button>
      <button class="btn-icon" onclick="openShareModal(${f.id})" title="Share">🔗</button>
      <button class="btn-icon" onclick="fileAction(${f.id},'trash')" title="Trash" style="color:var(--danger)">🗑</button>
    </div>
  </div>`;
}

/** 
 * Handle card click - Preview on simple click, Toggle select on Ctrl/Cmd click.
 */
function handleFileClick(event, fileId, name, mime) {
  if (event.ctrlKey || event.metaKey) {
    toggleSelectFile(fileId, event.currentTarget);
  } else {
    previewFile(fileId, name, mime);
  }
}

function renderEmpty(msg = 'No files here') {
  return `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">📭</div><p>${msg}</p></div>`;
}

function esc(str) { return String(str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;'); }

// ─── FILE ACTIONS ─────────────────────────────────────────────
async function fileAction(fileId, action, extra = {}) {
  const res = await api('POST', `/files/${fileId}/action`, { action, ...extra });
  if (action === 'trash') {
    State.lastTrashedId = fileId;
    showUndoBar('File moved to trash');
  }
  refreshCurrentSection();
  updateStorageBar();
  return res;
}

async function confirmDelete(fileId) {
  if (!confirm('Permanently delete this file? This cannot be undone.')) return;
  await fileAction(fileId, 'delete_permanent');
}

async function emptyTrash() {
  if (!confirm('Empty all trash? This cannot be undone.')) return;
  const res = await api('GET', '/files?category=trash');
  if (!res.files) return;
  for (const f of res.files) await api('POST', `/files/${f.id}/action`, { action: 'delete_permanent' });
  refreshCurrentSection();
  updateStorageBar();
}

async function downloadFile(fileId) {
  // window.open() cannot send Authorization headers, so we append the token as a query param.
  // The backend login_required_or_token decorator accepts both header and ?token= forms.
  const token = localStorage.getItem('token') || '';
  window.open(`/files/${fileId}/download?token=${encodeURIComponent(token)}`, '_blank');
}

let _currentPreviewFileId = null;
async function previewFile(fileId, name, mime) {
  _currentPreviewFileId = fileId;
  document.getElementById('preview-title').textContent = name;
  const content = document.getElementById('preview-content');
  content.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading preview...</p></div>';
  openModal('preview-modal');

  // Browsers set <img>/<video>/<audio>/<iframe> src as plain GET — no custom headers allowed.
  // Append the token so the backend's login_required_or_token decorator can authenticate.
  const token = encodeURIComponent(localStorage.getItem('token') || '');
  const url = `/files/${fileId}/preview?token=${token}`;
  let html = '';
  if (mime.startsWith('image/')) {
    html = `<img src="${url}" alt="${esc(name)}"/>`;
  } else if (mime.startsWith('video/')) {
    html = `<video controls src="${url}"></video>`;
  } else if (mime.startsWith('audio/')) {
    html = `<audio controls src="${url}"></audio>`;
  } else if (mime === 'application/pdf') {
    html = `<iframe src="${url}" title="${esc(name)}"></iframe>`;
  } else if (mime.startsWith('text/')) {
    try {
      const r = await fetch(`/files/${fileId}/preview`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      const text = await r.text();
      html = `<pre>${esc(text.substring(0, 5000))}</pre>`;
    } catch { html = '<p style="padding:1rem;color:var(--text-muted)">Cannot preview this file.</p>'; }
  } else {
    html = '<p style="padding:2rem;color:var(--text-muted)">Preview not available for this file type.</p>';
  }
  content.innerHTML = html;
}

function downloadCurrentFile() {
  if (_currentPreviewFileId) downloadFile(_currentPreviewFileId);
}

// ─── CONTEXT MENU ─────────────────────────────────────────────
let _ctxFileId = null;
function showCtxMenu(event, fileId, isTrashed) {
  event.preventDefault();
  _ctxFileId = fileId;
  const menu = document.getElementById('ctx-menu');
  menu.innerHTML = isTrashed ? `
    <div class="ctx-item" onclick="fileAction(${fileId},'restore')">↩ Restore</div>
    <div class="ctx-item danger" onclick="confirmDelete(${fileId})">🗑 Delete Forever</div>
  ` : `
    <div class="ctx-item" onclick="previewFile(${fileId},'','')">👁 Preview</div>
    <div class="ctx-item" onclick="downloadFile(${fileId})">⬇ Download</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item" onclick="fileAction(${fileId},'star')">⭐ Star</div>
    <div class="ctx-item" onclick="fileAction(${fileId},'pin')">📌 Pin to Dashboard</div>
    <div class="ctx-item" onclick="openNotesModal(${fileId})">📝 Add Note</div>
    <div class="ctx-item" onclick="openShareModal(${fileId})">🔗 Share</div>
    <div class="ctx-sep"></div>
    <div class="ctx-item danger" onclick="fileAction(${fileId},'trash')">🗑 Move to Trash</div>
  `;
  menu.style.left = Math.min(event.clientX, window.innerWidth - 200) + 'px';
  menu.style.top = Math.min(event.clientY, window.innerHeight - 200) + 'px';
  menu.classList.remove('hidden');
}
document.addEventListener('click', () => document.getElementById('ctx-menu').classList.add('hidden'));

// ─── UPLOAD ───────────────────────────────────────────────────
function openUploadModal() {
  State.uploadFiles = [];
  document.getElementById('upload-queue').innerHTML = '';
  document.getElementById('do-upload-btn').disabled = true;
  populateFolderSelect();
  openModal('upload-modal');
}

async function populateFolderSelect() {
  const sel = document.getElementById('upload-folder-select');
  sel.innerHTML = '<option value="">No folder (root)</option>';
  const res = await api('GET', '/folders');
  if (res.folders) {
    res.folders.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.id; opt.textContent = (f.is_private ? '🔒 ' : '📁 ') + f.name;
      sel.appendChild(opt);
    });
  }
}

function handleDrop(event) {
  event.preventDefault();
  document.getElementById('drop-zone').classList.remove('dragging');
  addFilesToQueue([...event.dataTransfer.files]);
}

function handleFileSelect(input) {
  addFilesToQueue([...input.files]);
  input.value = '';
}

function addFilesToQueue(files) {
  State.uploadFiles.push(...files);
  renderUploadQueue();
}

function renderUploadQueue() {
  const queue = document.getElementById('upload-queue');
  if (State.uploadFiles.length === 0) { queue.innerHTML = ''; document.getElementById('do-upload-btn').disabled = true; return; }
  document.getElementById('do-upload-btn').disabled = false;
  queue.innerHTML = State.uploadFiles.map((f, i) => `
    <div class="upload-item" id="uitem-${i}">
      <span>${getFileIcon(f.type, f.name)}</span>
      <span class="upload-item-name">${esc(f.name)}</span>
      <span class="upload-item-size">${formatSize(f.size)}</span>
    </div>
  `).join('');
}

async function startUpload() {
  if (State.uploadFiles.length === 0) return;
  const btn = document.getElementById('do-upload-btn');
  btn.textContent = 'Uploading...'; btn.disabled = true;

  const folderId = document.getElementById('upload-folder-select').value;
  const autoOrg = document.getElementById('auto-organize-check').checked;

  const formData = new FormData();
  State.uploadFiles.forEach(f => formData.append('file', f));
  if (folderId) formData.append('folder_id', folderId);
  formData.append('auto_organize', autoOrg ? 'true' : 'false');

  // Show progress
  const queue = document.getElementById('upload-queue');
  queue.innerHTML = `<div class="upload-item"><span>⏫</span><div style="flex:1"><div class="upload-progress-bar"><div class="upload-progress-fill" id="upload-prog"></div></div></div></div>`;
  let prog = 0;
  const interval = setInterval(() => { prog = Math.min(prog + 8, 90); document.getElementById('upload-prog').style.width = prog + '%'; }, 150);

  const res = await api('POST', '/upload', formData);
  clearInterval(interval);
  const progEl = document.getElementById('upload-prog');
  if (progEl) progEl.style.width = '100%';

  setTimeout(() => {
    closeModal('upload-modal');
    State.uploadFiles = [];
    btn.textContent = 'Upload'; btn.disabled = true;
    refreshCurrentSection();
    updateStorageBar();
    if (res.error) showNotif('❌ ' + res.error, 'danger');
    else showToast('✅ ' + (res.message || 'Uploaded!'));
  }, 500);
}

// ─── FOLDERS ──────────────────────────────────────────────────
async function loadFolders() {
  const container = document.getElementById('folders-container');
  const filesTitle = document.getElementById('folder-files-title');
  const filesContainer = document.getElementById('folder-files-container');
  filesTitle.style.display = 'none';
  filesContainer.innerHTML = '';

  const res = await api('GET', '/folders');
  State.folders = res.folders || [];
  if (State.folders.length === 0) { container.innerHTML = '<div class="empty-state"><div class="empty-icon">📁</div><p>No folders yet</p></div>'; return; }
  container.innerHTML = res.folders.map(f => `
    <div class="folder-card" onclick="openFolder(${f.id},${f.is_private})">
      <div class="folder-icon">${f.is_private ? '🔒' : '📁'}</div>
      <div class="folder-name">${esc(f.name)}</div>
      <div class="folder-count">${f.file_count} file${f.file_count !== 1 ? 's' : ''}</div>
      ${f.is_private ? '<div class="folder-private-badge">Private</div>' : ''}
      <div style="margin-top:.6rem;font-size:.8rem" onclick="event.stopPropagation();deleteFolder(${f.id})" style="color:var(--danger);cursor:pointer">🗑 Delete</div>
    </div>
  `).join('');
}

async function openFolder(folderId, isPrivate) {
  if (isPrivate) {
    State.pendingUnlockFolderId = folderId;
    document.getElementById('unlock-password').value = '';
    document.getElementById('unlock-error').textContent = '';
    openModal('unlock-modal');
    return;
  }
  showFolderFiles(folderId);
}

async function submitUnlock() {
  const pw = document.getElementById('unlock-password').value;
  const res = await api('POST', `/folders/${State.pendingUnlockFolderId}/unlock`, { password: pw });
  if (res.success) {
    closeModal('unlock-modal');
    showFolderFiles(State.pendingUnlockFolderId);
  } else {
    document.getElementById('unlock-error').textContent = res.error || 'Incorrect password';
  }
}

async function showFolderFiles(folderId) {
  State.currentFolderId = folderId;
  const filesTitle = document.getElementById('folder-files-title');
  const filesContainer = document.getElementById('folder-files-container');
  const folder = State.folders.find(f => f.id === folderId);
  filesTitle.textContent = '📂 ' + (folder ? folder.name : 'Folder');
  filesTitle.style.display = 'block';
  filesContainer.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading...</p></div>';
  const res = await api('GET', `/files?folder_id=${folderId}&category=all`);
  if (!res.files || res.files.length === 0) { filesContainer.innerHTML = renderEmpty('This folder is empty'); return; }
  filesContainer.innerHTML = res.files.map(f => renderFileCard(f)).join('');
}

function openCreateFolder() {
  document.getElementById('folder-name-input').value = '';
  document.getElementById('folder-private-check').checked = false;
  document.getElementById('folder-password-input').value = '';
  document.getElementById('folder-private-fields').classList.add('hidden');
  openModal('folder-modal');
}

async function createFolder() {
  const name = document.getElementById('folder-name-input').value.trim();
  const isPrivate = document.getElementById('folder-private-check').checked;
  const pw = document.getElementById('folder-password-input').value;
  if (!name) return;
  await api('POST', '/create-folder', { name, is_private: isPrivate, private_password: isPrivate ? pw : null });
  closeModal('folder-modal');
  loadFolders();
}

async function deleteFolder(folderId) {
  if (!confirm('Delete this folder? Files will be moved to trash.')) return;
  await api('DELETE', `/folders/${folderId}`);
  loadFolders();
}

function togglePrivateFields() {
  const show = document.getElementById('folder-private-check').checked;
  document.getElementById('folder-private-fields').classList.toggle('hidden', !show);
}

// ─── SEARCH ───────────────────────────────────────────────────
let searchTimeout = null;
function handleSearch(value) {
  clearTimeout(searchTimeout);
  if (!value.trim()) { if (State.currentSection === 'search') navigate('home'); return; }
  searchTimeout = setTimeout(async () => {
    navigate('search');
    const type = document.getElementById('search-type-filter').value;
    const container = document.getElementById('search-files-container');
    container.innerHTML = renderEmpty('Searching...');
    const res = await api('GET', `/search?q=${encodeURIComponent(value)}&type=${type}`);
    if (!res.files || res.files.length === 0) { container.innerHTML = renderEmpty('No results found'); return; }
    container.innerHTML = res.files.map(f => renderFileCard(f)).join('');
  }, 350);
}

// ─── INSIGHTS ─────────────────────────────────────────────────
async function loadInsights() {
  const container = document.getElementById('insights-container');
  container.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading insights...</p></div>';
  const res = await api('GET', '/insights');
  if (res.error || !res.storage_breakdown) { container.innerHTML = '<p style="color:var(--danger)">Failed to load insights.</p>'; return; }

  const pct = Math.min(res.storage_limit ? Math.round((res.storage_used / res.storage_limit) * 100) : 0, 100);
  const colors = { images: '#6366f1', videos: '#8b5cf6', audio: '#06b6d4', documents: '#10b981', archives: '#f59e0b', other: '#64748b' };
  const svgParts = buildDonut(res.storage_breakdown, res.storage_limit, colors);

  const mostAccessed = res.most_accessed?.length
    ? res.most_accessed.map(f => `<li>${getFileIcon(f.mime_type)} <span>${esc(f.original_name)}</span><span>${f.access_count} opens</span></li>`).join('')
    : '<li><span>No data yet</span></li>';

  const largest = res.largest_files?.length
    ? res.largest_files.map(f => `<li>${getFileIcon(f.mime_type)} <span>${esc(f.original_name)}</span><span>${formatSize(f.size)}</span></li>`).join('')
    : '<li><span>No files</span></li>';

  const unused = res.unused_files?.length
    ? res.unused_files.map(f => `<li>${getFileIcon(f.mime_type)} <span>${esc(f.original_name)}</span><button class="btn-sm cleanup-btn" onclick="fileAction(${f.id},'trash')">🗑</button></li>`).join('')
    : '<li><span>No unused files – great!</span></li>';

  container.innerHTML = `<div class="insights-grid">
    <div class="insight-card">
      <h3>💾 Storage Overview</h3>
      <div style="margin-bottom:.8rem"><strong>${pct}% used</strong> – ${formatSize(res.storage_used)} of ${formatSize(res.storage_limit)}</div>
      <div class="storage-bar" style="height:12px;margin-bottom:1rem"><div class="storage-fill" style="width:${pct}%;background:${pct > 80 ? 'linear-gradient(90deg,#ef4444,#f87171)' : ''}"></div></div>
      <div class="storage-donut-wrap">
        <svg class="donut-svg" width="120" height="120" viewBox="0 0 120 120">${svgParts.svg}</svg>
        <div class="donut-legend">${svgParts.legend}</div>
      </div>
    </div>
    <div class="insight-card">
      <h3>🔥 Most Accessed</h3>
      <ul class="insight-list">${mostAccessed}</ul>
    </div>
    <div class="insight-card">
      <h3>📦 Largest Files</h3>
      <ul class="insight-list">${largest}</ul>
    </div>
    <div class="insight-card">
      <h3>🧹 Unused Files (30+ days)</h3>
      <p style="font-size:.83rem;color:var(--text-muted);margin-bottom:.8rem">Files not accessed in 30 days – consider cleaning up.</p>
      <ul class="insight-list">${unused}</ul>
    </div>
  </div>`;
}

function buildDonut(breakdown, total, colors) {
  const cx = 60, cy = 60, r = 48, stroke = 18;
  const circ = 2 * Math.PI * r;
  const entries = Object.entries(breakdown).filter(([, v]) => v > 0);
  let offset = 0;
  let svgPaths = '';
  let legendHtml = '';
  entries.forEach(([key, val]) => {
    const frac = total ? val / total : 0;
    const dash = frac * circ;
    const color = colors[key] || '#94a3b8';
    svgPaths += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-dasharray="${dash} ${circ - dash}" stroke-dashoffset="${-offset}" transform="rotate(-90 ${cx} ${cy})"/>`;
    offset += dash;
    legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span>${key.charAt(0).toUpperCase() + key.slice(1)}: ${formatSize(val)}</span></div>`;
  });
  if (!entries.length) svgPaths = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--border)" stroke-width="${stroke}"/>`;
  return { svg: svgPaths, legend: legendHtml || '<span style="color:var(--text-muted)">No data</span>' };
}

// ─── ACTIVITY ─────────────────────────────────────────────────
const ACTION_ICONS = { upload: '⬆', download: '⬇', preview: '👁', login: '🔑', logout: '🚪', share: '🔗', trash: '🗑', restore: '↩', delete_permanent: '💀', star: '⭐', pin: '📌', create_folder: '📁', delete_folder: '🗂', rename: '✏', add_note: '📝', auto_organize: '🤖', change_password: '🔒', register: '🎉' };

async function loadActivity() {
  const container = document.getElementById('activity-container');
  container.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Loading...</p></div>';
  const res = await api('GET', '/activity?limit=50');
  if (!res.activity || res.activity.length === 0) { container.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><p>No activity yet</p></div>'; return; }
  container.innerHTML = `<div class="activity-list">${res.activity.map(a => `
    <div class="activity-item">
      <span class="activity-icon">${ACTION_ICONS[a.action] || '📌'}</span>
      <div class="activity-info">
        <div class="activity-action">${a.action.replace(/_/g, ' ')}</div>
        ${a.target_name ? `<div class="activity-target">${esc(a.target_name)}</div>` : ''}
      </div>
      <span class="activity-time">${timeAgo(a.created_at)}</span>
    </div>
  `).join('')}</div>`;
}

// ─── SHARE MODAL ──────────────────────────────────────────────
function openShareModal(fileId) {
  State.currentShareFileId = fileId;
  document.getElementById('share-result').classList.add('hidden');
  openModal('share-modal');
}

async function generateShareLink() {
  const perm = document.getElementById('share-perm').value;
  const expiry = document.getElementById('share-expiry').value;
  const res = await api('POST', `/files/${State.currentShareFileId}/share`, { permission: perm, expiry_hours: expiry || null });
  if (res.share_url) {
    // Use token-based share page URL (/share/<token>) so anyone can access without login.
    // If public_download_url is also returned, prefer the /share/<token> page for a nicer UX.
    const linkToShow = res.share_url || res.public_download_url;
    document.getElementById('share-url-input').value = linkToShow;
    document.getElementById('share-result').classList.remove('hidden');
    // Also show public direct-download link if available
    const pubEl = document.getElementById('share-public-link');
    if (pubEl && res.public_download_url) {
      pubEl.href = res.public_download_url;
      pubEl.textContent = '⬇ Direct Download Link (no login required)';
      pubEl.style.display = 'block';
    }
  } else if (res.error) {
    showNotif('❌ ' + res.error, 'danger');
  }
}

function copyShareUrl() {
  const url = document.getElementById('share-url-input').value;
  navigator.clipboard.writeText(url).then(() => showToast('✅ Link copied!'));
}

// ─── NOTES MODAL ──────────────────────────────────────────────
async function openNotesModal(fileId) {
  State.currentNoteFileId = fileId;
  const res = await api('GET', `/files/${fileId}`);
  document.getElementById('notes-textarea').value = res.file?.notes || '';
  openModal('notes-modal');
}

async function saveNote() {
  const note = document.getElementById('notes-textarea').value;
  await fileAction(State.currentNoteFileId, 'add_note', { note });
  closeModal('notes-modal');
  showToast('📝 Note saved!');
}

// ─── SETTINGS ─────────────────────────────────────────────────
function renderSettings() {
  const container = document.getElementById('settings-container');
  const u = State.user || {};
  container.innerHTML = `
    <div class="settings-section">
      <h3>Appearance</h3>
      <div class="settings-row">
        <label>Dark Mode</label>
        <label class="toggle">
          <input type="checkbox" id="theme-toggle-settings" ${document.documentElement.getAttribute('data-theme') === 'dark' ? 'checked' : ''} onchange="toggleTheme()"/>
          <span class="toggle-slider"></span>
        </label>
      </div>
    </div>
    <div class="settings-section">
      <h3>Account</h3>
      <div class="settings-row"><label>Username</label><strong>${esc(u.username)}</strong></div>
      <div class="settings-row"><label>Email</label><span>${esc(u.email)}</span></div>
      <div class="settings-row"><label>Member since</label><span>${u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}</span></div>
    </div>
    <div class="settings-section">
      <h3>Change Password</h3>
      <input class="settings-input" type="password" id="cp-current" placeholder="Current password"/>
      <input class="settings-input" type="password" id="cp-new" placeholder="New password (min 6)"/>
      <button class="btn-primary" onclick="changePassword()">Update Password</button>
      <p id="cp-msg" style="margin-top:.5rem;font-size:.85rem"></p>
    </div>
    <div class="settings-section">
      <h3>Storage</h3>
      <div class="settings-row"><label>Used</label><span>${formatSize(u.storage_used || 0)}</span></div>
      <div class="settings-row"><label>Limit</label><span>${formatSize(u.storage_limit || 104857600)}</span></div>
      <div class="storage-bar" style="height:10px;margin-top:.8rem"><div class="storage-fill" style="width:${u.storage_limit ? Math.min((u.storage_used / u.storage_limit) * 100, 100).toFixed(1) : 0}%"></div></div>
    </div>
  `;
}

async function changePassword() {
  const cur = document.getElementById('cp-current').value;
  const nw = document.getElementById('cp-new').value;
  const msg = document.getElementById('cp-msg');
  const res = await api('POST', '/settings/password', { current_password: cur, new_password: nw });
  msg.style.color = res.error ? 'var(--danger)' : 'var(--success)';
  msg.textContent = res.error || res.message;
}

// ─── AUTO ORGANIZE ────────────────────────────────────────────
async function runAutoOrganize() {
  const res = await api('POST', '/auto-organize');
  showToast('🤖 ' + (res.message || 'Organized!'));
  document.getElementById('organize-banner').classList.add('hidden');
  refreshCurrentSection();
}

// ─── BACKUP REMINDER ──────────────────────────────────────────
async function checkBackupReminder() {
  const res = await api('GET', '/backup-reminder');
  if (res.show_reminder) {
    const banner = document.getElementById('notif-banner');
    banner.textContent = res.message;
    banner.classList.remove('hidden');
    document.getElementById('notif-dot').classList.remove('hidden');
  }
}

function toggleNotifications() {
  const banner = document.getElementById('notif-banner');
  banner.classList.toggle('hidden');
}

// ─── UNDO BAR ─────────────────────────────────────────────────
let undoTimer = null;
function showUndoBar(msg) {
  document.getElementById('undo-msg').textContent = msg;
  document.getElementById('undo-bar').classList.remove('hidden');
  clearTimeout(undoTimer);
  undoTimer = setTimeout(() => document.getElementById('undo-bar').classList.add('hidden'), 5000);
}

async function undoLastAction() {
  if (State.lastTrashedId) {
    await fileAction(State.lastTrashedId, 'restore');
    State.lastTrashedId = null;
    showToast('↩ Restored!');
  }
  closeUndoBar();
}

function closeUndoBar() {
  clearTimeout(undoTimer);
  document.getElementById('undo-bar').classList.add('hidden');
}

// ─── TOAST ────────────────────────────────────────────────────
function showToast(msg) {
  const el = document.createElement('div');
  el.className = 'undo-bar';
  el.style.cssText = 'z-index:9999;pointer-events:none';
  el.innerHTML = `<span>${msg}</span>`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2800);
}

function showNotif(msg) {
  const banner = document.getElementById('notif-banner');
  banner.textContent = msg;
  banner.classList.remove('hidden');
  setTimeout(() => banner.classList.add('hidden'), 4000);
}

// ─── MODALS ───────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => m.classList.add('hidden'));
  }
});
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.add('hidden');
});

// ─── VIEW TOGGLE ──────────────────────────────────────────────
function setView(view) {
  State.currentView = view;
  document.getElementById('view-grid').classList.toggle('active-view', view === 'grid');
  document.getElementById('view-list').classList.toggle('active-view', view === 'list');
  refreshCurrentSection();
}

// ─── REFRESH ──────────────────────────────────────────────────
function refreshCurrentSection() {
  navigate(State.currentSection);
}

// ─── DRAG TO UPLOAD FROM ANYWHERE ────────────────────────────
document.addEventListener('dragover', e => { e.preventDefault(); });
document.addEventListener('drop', e => {
  e.preventDefault();
  const target = e.target.closest('#drop-zone');
  if (!target && e.dataTransfer.files.length > 0) {
    State.uploadFiles = [...e.dataTransfer.files];
    populateFolderSelect();
    renderUploadQueue();
    openModal('upload-modal');
  }
});

// ─── INIT ─────────────────────────────────────────────────────
checkSession();

// ─────────────────────────────────────────────────────────────
// ✅ FILE SELECTION & ZIP DOWNLOAD
// ─────────────────────────────────────────────────────────────
const selectedFileIds = new Set();

/** Toggle selection on a file card. */
function toggleSelectFile(fileId, el) {
  // el is the file-card element
  if (!el.classList.contains('file-card')) {
    el = el.closest('.file-card');
  }

  if (selectedFileIds.has(fileId)) {
    selectedFileIds.delete(fileId);
    el.classList.remove('selected');
  } else {
    selectedFileIds.add(fileId);
    el.classList.add('selected');
  }
  updateZipBar();
}

function updateZipBar() {
  const bar = document.getElementById('zip-bar');
  const msg = document.getElementById('zip-bar-msg');
  if (selectedFileIds.size > 0) {
    bar.classList.remove('hidden');
    msg.textContent = `${selectedFileIds.size} file${selectedFileIds.size !== 1 ? 's' : ''} selected`;
  } else {
    bar.classList.add('hidden');
  }
}

function clearSelection() {
  selectedFileIds.clear();
  document.querySelectorAll('.file-card.selected').forEach(el => el.classList.remove('selected'));
  updateZipBar();
}

/** Download all selected files as a single ZIP. */
async function downloadSelectedZip() {
  if (selectedFileIds.size === 0) { showToast('⚠ No files selected'); return; }
  const token = localStorage.getItem('token');
  showToast('⏳ Preparing ZIP download...');

  // Use fetch so we can send Authorization header
  const res = await fetch('/download-zip', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ file_ids: [...selectedFileIds] })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    showToast('❌ ' + (err.error || 'ZIP download failed'));
    return;
  }

  // Trigger browser download from blob
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'skystore_files.zip';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  clearSelection();
  showToast('✅ ZIP downloaded!');
}

// ─────────────────────────────────────────────────────────────
// 📂 MOVE FILE TO FOLDER
// ─────────────────────────────────────────────────────────────
let _moveFileId = null;

async function openMoveModal(fileId) {
  _moveFileId = fileId;
  // Populate the folder dropdown
  const sel = document.getElementById('move-folder-select');
  sel.innerHTML = '<option value="">📁 Root (no folder)</option>';
  const res = await api('GET', '/folders');
  if (res.folders) {
    res.folders.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.id;
      opt.textContent = (f.is_private ? '🔒 ' : '📁 ') + f.name;
      sel.appendChild(opt);
    });
  }
  openModal('move-modal');
}

async function confirmMoveFile() {
  if (!_moveFileId) return;
  const folderId = document.getElementById('move-folder-select').value;
  const res = await api('POST', '/move-file', {
    file_id: _moveFileId,
    folder_id: folderId ? parseInt(folderId) : null
  });
  closeModal('move-modal');
  if (res.error) { showToast('❌ ' + res.error); return; }
  showToast('✅ File moved!');
  refreshCurrentSection();
  _moveFileId = null;
}

// ─────────────────────────────────────────────────────────────
// 🤖 AI FILE SUMMARIZER
// ─────────────────────────────────────────────────────────────
async function openSummarizeModal(fileId) {
  const content = document.getElementById('summarize-content');
  content.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Analyzing file...</p></div>';
  openModal('summarize-modal');

  const res = await api('POST', '/summarize', { file_id: fileId });

  if (res.error) {
    content.innerHTML = `<p style="color:var(--danger);padding:.5rem">❌ ${esc(res.error)}</p>`;
    return;
  }

  const stats = res.stats || {};
  content.innerHTML = `
    <div style="margin-bottom:1rem">
      <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.8rem">
        <span style="background:var(--surface);padding:.3rem .8rem;border-radius:.4rem;font-size:.82rem">📝 ${stats.word_count || 0} words</span>
        <span style="background:var(--surface);padding:.3rem .8rem;border-radius:.4rem;font-size:.82rem">📖 ${stats.sentence_count || 0} sentences</span>
        <span style="background:var(--surface);padding:.3rem .8rem;border-radius:.4rem;font-size:.82rem">🔤 ${stats.character_count || 0} chars</span>
      </div>
      ${res.keywords ? `<div style="margin-bottom:.8rem"><strong style="font-size:.85rem;color:var(--text-muted)">🔑 Key Topics:</strong>
        <span style="color:var(--primary);font-size:.9rem"> ${esc(res.keywords)}</span></div>` : ''}
      <strong style="font-size:.9rem;color:var(--text-muted)">📄 Summary:</strong>
      <div style="margin-top:.5rem;line-height:1.7;font-size:.93rem;max-height:220px;overflow-y:auto;
           background:var(--surface);padding:.8rem;border-radius:.5rem;border:1px solid var(--border)">
        ${esc(res.summary || 'No summary available.')}
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────
// EXTEND CONTEXT MENU with new actions
// ─────────────────────────────────────────────────────────────
// Override showCtxMenu to add the new options
const _origShowCtxMenu = showCtxMenu;
function showCtxMenu(event, fileId, isTrashed) {
  event.preventDefault();
  _ctxFileId = fileId;
  const menu = document.getElementById('ctx-menu');
  if (isTrashed) {
    menu.innerHTML = `
      <div class="ctx-item" onclick="fileAction(${fileId},'restore')">↩ Restore</div>
      <div class="ctx-item danger" onclick="confirmDelete(${fileId})">🗑 Delete Forever</div>
    `;
  } else {
    menu.innerHTML = `
      <div class="ctx-item" onclick="previewFile(${fileId},'','')">👁 Preview</div>
      <div class="ctx-item" onclick="downloadFile(${fileId})">⬇ Download</div>
      <div class="ctx-item" onclick="toggleSelectFile(${fileId}, document.querySelector('[data-id=\\'${fileId}\\']'))">☑ Select for ZIP</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item" onclick="fileAction(${fileId},'star')">⭐ Star</div>
      <div class="ctx-item" onclick="fileAction(${fileId},'pin')">📌 Pin to Dashboard</div>
      <div class="ctx-item" onclick="openNotesModal(${fileId})">📝 Add Note</div>
      <div class="ctx-item" onclick="openShareModal(${fileId})">🔗 Share</div>
      <div class="ctx-item" onclick="openMoveModal(${fileId})">📂 Move to Folder</div>
      <div class="ctx-item" onclick="openSummarizeModal(${fileId})">🤖 Summarize</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item danger" onclick="fileAction(${fileId},'trash')">🗑 Move to Trash</div>
    `;
  }
  menu.style.left = Math.min(event.clientX, window.innerWidth - 220) + 'px';
  menu.style.top = Math.min(event.clientY, window.innerHeight - 260) + 'px';
  menu.classList.remove('hidden');
}

