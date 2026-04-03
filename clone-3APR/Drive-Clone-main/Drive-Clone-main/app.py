"""
SkyStore - Advanced Cloud Storage System
Flask Backend with MySQL Integration
"""

import os
import mimetypes
import json
import time
import hashlib
import secrets
import urllib.parse
import shutil
from datetime import datetime, timedelta
from functools import wraps

import sqlite3
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from flask_cors import CORS

# ─────────────────────────────────────────────────────────────────────────────
# APP CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Stable secret key (persisted so sessions survive restarts) ──────────────
_SECRET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')
if os.path.exists(_SECRET_FILE):
    with open(_SECRET_FILE, 'r') as _sf:
        app.secret_key = _sf.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(_SECRET_FILE, 'w') as _sf:
        _sf.write(app.secret_key)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload
app.config['USER_STORAGE_LIMIT'] = 100 * 1024 * 1024  # 100 MB per user
app.config['TRASH_AUTO_DELETE_DAYS'] = 30

# Global error handler — show errors as JSON for debugging
@app.errorhandler(405)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(error):
    import traceback
    print(f"ERROR: {error}")
    print(traceback.format_exc())
    return jsonify({'error': str(error), 'type': 'HTTP Error'}), getattr(error, 'code', 500)

ALLOWED_PREVIEW_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
    'application/pdf', 'text/plain', 'video/mp4', 'video/webm', 'audio/mpeg',
    'audio/wav', 'audio/ogg'
}

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE — SQLite (zero config, built-in Python)
# ─────────────────────────────────────────────────────────────────────────────
# Use absolute paths so the app works regardless of the working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'skystore.db')

def get_db():
    """Get a SQLite connection that returns real dicts (supports .get(), key access, etc)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    }
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    """Initialize the SQLite database schema."""
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            storage_used INTEGER DEFAULT 0,
            storage_limit INTEGER DEFAULT 104857600,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT,
            backup_reminder_sent TEXT,
            theme TEXT DEFAULT 'dark'
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            folder_id INTEGER DEFAULT NULL,
            size INTEGER NOT NULL,
            mime_type TEXT,
            is_starred INTEGER DEFAULT 0,
            is_trashed INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            trashed_at TEXT,
            uploaded_at TEXT DEFAULT (datetime('now')),
            last_accessed TEXT DEFAULT (datetime('now')),
            access_count INTEGER DEFAULT 0,
            notes TEXT,
            share_token TEXT,
            share_permission TEXT DEFAULT 'view',
            share_expires TEXT,
            private_folder INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            is_private INTEGER DEFAULT 0,
            private_password TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_name TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS share_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            permission TEXT DEFAULT 'view',
            expires_at TEXT,
            access_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()
    print('SQLite database ready.')


def row_to_dict(row):
    """Convert sqlite3.Row to plain dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows):
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

# ── Persistent token store ───────────────────────────────────────────────────
# TOKENS maps  token_hex_string -> user_id
# Persisted to tokens.json so Flask restarts don't invalidate active sessions.
TOKENS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tokens.json')

def _load_tokens():
    """Load tokens from disk on startup."""
    if os.path.exists(TOKENS_FILE):
        try:
            with open(TOKENS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_tokens():
    """Persist current TOKENS dict to disk."""
    try:
        with open(TOKENS_FILE, 'w') as f:
            json.dump(TOKENS, f)
    except Exception as e:
        print(f'Token save error: {e}')

TOKENS = _load_tokens()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401
        
        token = auth_header.split(' ')[1]
        user_id = TOKENS.get(token)
        if not user_id:
            return jsonify({'error': 'Invalid or expired token'}), 401
            
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def login_required_or_token(f):
    """Like login_required but also accepts ?token= query param.
    Used for file-serving routes opened directly in the browser (window.open),
    where custom Authorization headers cannot be sent.
    The existing login_required decorator is NOT modified.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Try Authorization header first (normal API calls)
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        else:
            # 2. Fallback: token passed as ?token= query param (browser tab / window.open)
            token = request.args.get('token', '')

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        user_id = TOKENS.get(token)
        if not user_id:
            return jsonify({'error': 'Invalid or expired token'}), 401

        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def get_user_storage_path(user_id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def log_activity(user_id, action, target_name=None, details=None):
    """Log a user action to the activity_log table."""
    try:
        conn = get_db()
        cur = conn.cursor()
        ip = request.remote_addr
        cur.execute(
            "INSERT INTO activity_log (user_id, action, target_name, details, ip_address) VALUES (?,?,?,?,?)",
            (user_id, action, target_name, details, ip)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Log error: {e}")

def get_mime_type(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime or 'application/octet-stream'

def bytes_to_mb(b):
    return round(b / (1024 * 1024), 2)

def get_file_category(mime_type):
    if not mime_type:
        return 'other'
    if mime_type.startswith('image/'):
        return 'images'
    if mime_type.startswith('video/'):
        return 'videos'
    if mime_type.startswith('audio/'):
        return 'audio'
    if mime_type in ('application/pdf',) or mime_type.startswith('text/'):
        return 'documents'
    if mime_type in ('application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed'):
        return 'archives'
    return 'other'

def auto_delete_trash():
    """Remove files from trash older than 30 days."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(days=app.config['TRASH_AUTO_DELETE_DAYS'])).isoformat()
        cur.execute(
            "SELECT id, user_id, name FROM files WHERE is_trashed=1 AND trashed_at < ?",
            (cutoff,)
        )
        old_files = cur.fetchall()
        for f in old_files:
            path = os.path.join(get_user_storage_path(f['user_id']), f['name'])
            if os.path.exists(path):
                os.remove(path)
            # Update storage used
            cur.execute("UPDATE users SET storage_used = MAX(0, storage_used - (SELECT size FROM files WHERE id=?)) WHERE id=?", (f['id'], f['user_id']))
            cur.execute("DELETE FROM files WHERE id=?", (f['id'],))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Auto-delete error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# STATIC & ROOT
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/style.css')
def serve_css():
    return send_from_directory('.', 'style.css', mimetype='text/css')

@app.route('/app.js')
def serve_js():
    return send_from_directory('.', 'app.js', mimetype='application/javascript')

# ─────────────────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/register')
def register():
    data = request.json or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'All fields are required', 'success': False}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters', 'success': False}), 400

    pw_hash = generate_password_hash(password)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            (username, email, pw_hash)
        )
        conn.commit()
        user_id = cur.lastrowid
        for folder_name in ['Images', 'Documents', 'Videos', 'Audio', 'Archives', 'Other']:
            cur.execute("INSERT INTO folders (user_id, name) VALUES (?,?)", (user_id, folder_name))
        conn.commit()
        cur.close()
        conn.close()
        log_activity(user_id, 'register', username)
        return jsonify({'message': 'Account created successfully', 'success': True}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists', 'success': False}), 409
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}', 'success': False}), 500

@app.post('/login')
def login():
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email/username and password required', 'success': False}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? OR username=?", (email, email))
        user = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': f'Database connection failed: {str(e)}', 'success': False}), 503

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials', 'success': False}), 401

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user['id'],))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass  # Non-critical, don't block login

    token = secrets.token_hex(32)
    TOKENS[token] = user['id']
    _save_tokens()  # persist so token survives Flask restarts
    log_activity(user['id'], 'login', user['username'])
    
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['username'],
            'username': user['username'],
            'email': user['email'],
            'storage_used': user.get('storage_used', 0),
            'storage_limit': user.get('storage_limit', 104857600),
            'theme': user.get('theme', 'dark')
        }
    })

@app.post('/logout')
@login_required
def logout():
    log_activity(request.user_id, 'logout')
    
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        TOKENS.pop(token, None)
        _save_tokens()  # persist removal

    return jsonify({'message': 'Logged out'})

@app.get('/user')
@login_required
def me():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, storage_used, storage_limit, theme, created_at FROM users WHERE id=?", (request.user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user and user.get('created_at') and not isinstance(user['created_at'], str):
        user['created_at'] = user['created_at'].isoformat()
    return jsonify({'user': user})

# ─────────────────────────────────────────────────────────────────────────────
# FILE ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/upload')
@login_required
def upload_file():
    auto_delete_trash()
    user_id = request.user_id

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    files = request.files.getlist('file')
    folder_id = request.form.get('folder_id') or None
    auto_organize = request.form.get('auto_organize', 'false') == 'true'
    results = []

    # Check storage
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT storage_used, storage_limit FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    for file in files:
        if file.filename == '':
            continue

        original_name = file.filename
        filename = secure_filename(original_name)
        if not filename:
            continue

        # Read file to get size
        file_data = file.read()
        file_size = len(file_data)

        if user['storage_used'] + file_size > user['storage_limit']:
            return jsonify({'error': f'Storage limit exceeded. You have {bytes_to_mb(user["storage_limit"] - user["storage_used"])} MB remaining.'}), 413

        mime_type = get_mime_type(filename)

        # Auto-organize: assign folder based on type
        if auto_organize and not folder_id:
            cat = get_file_category(mime_type)
            cat_map = {'images': 'Images', 'videos': 'Videos', 'audio': 'Audio', 'documents': 'Documents', 'archives': 'Archives', 'other': 'Other'}
            folder_name = cat_map.get(cat, 'Other')
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM folders WHERE user_id=? AND name=? AND parent_id IS NULL", (user_id, folder_name))
            folder_row = cur.fetchone()
            cur.close()
            conn.close()
            if folder_row:
                folder_id = folder_row['id']

        # Save to disk
        storage_path = get_user_storage_path(user_id)
        
        # Make filename unique if exists
        base, ext = os.path.splitext(filename)
        counter = 1
        unique_filename = filename
        while os.path.exists(os.path.join(storage_path, unique_filename)):
            unique_filename = f"{base}_{counter}{ext}"
            counter += 1

        file_path = os.path.join(storage_path, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(file_data)

        # Insert into DB
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO files (user_id, name, original_name, folder_id, size, mime_type)
               VALUES (?,?,?,?,?,?)""",
            (user_id, unique_filename, original_name, folder_id, file_size, mime_type)
        )
        file_id = cur.lastrowid
        cur.execute("UPDATE users SET storage_used = storage_used + ? WHERE id=?", (file_size, user_id))
        # Update backup reminder
        cur.execute("UPDATE users SET backup_reminder_sent=NULL WHERE id=?", (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        log_activity(user_id, 'upload', original_name, f'Size: {bytes_to_mb(file_size)} MB')
        user['storage_used'] += file_size
        results.append({'id': file_id, 'name': original_name, 'size': file_size})

    return jsonify({'message': f'{len(results)} file(s) uploaded', 'files': results}), 201

@app.get('/files')
@login_required
def list_files():
    auto_delete_trash()
    user_id = request.user_id
    category = request.args.get('category', 'all')
    folder_id = request.args.get('folder_id')
    search = request.args.get('search', '').strip()
    file_type = request.args.get('file_type', '')
    sort_by = request.args.get('sort_by', 'uploaded_at')
    sort_order = request.args.get('sort_order', 'DESC')

    conn = get_db()
    cur = conn.cursor()

    base_query = "SELECT f.*, fo.name as folder_name FROM files f LEFT JOIN folders fo ON f.folder_id=fo.id WHERE f.user_id=?"
    params = [user_id]

    if category == 'starred':
        base_query += " AND f.is_starred=1 AND f.is_trashed=0"
    elif category == 'trash':
        base_query += " AND f.is_trashed=1"
    elif category == 'recent':
        base_query += " AND f.is_trashed=0"
        sort_by = 'last_accessed'
        sort_order = 'DESC'
    elif category == 'pinned':
        base_query += " AND f.is_pinned=1 AND f.is_trashed=0"
    elif category == 'images':
        base_query += " AND f.is_trashed=0 AND f.mime_type LIKE 'image/%'"
    elif category == 'documents':
        base_query += " AND f.is_trashed=0 AND (f.mime_type='application/pdf' OR f.mime_type LIKE 'text/%')"
    elif category == 'videos':
        base_query += " AND f.is_trashed=0 AND f.mime_type LIKE 'video/%'"
    else:
        base_query += " AND f.is_trashed=0"

    if folder_id:
        base_query += " AND f.folder_id=?"
        params.append(int(folder_id))
    elif category not in ('trash', 'starred', 'recent', 'pinned', 'images', 'documents', 'videos'):
        pass  # Show all files regardless of folder for home

    if search:
        base_query += " AND f.original_name LIKE ?"
        params.append(f'%{search}%')

    if file_type:
        type_map = {
            'image': 'image/%', 'video': 'video/%', 'audio': 'audio/%',
            'pdf': 'application/pdf', 'text': 'text/%'
        }
        if file_type in type_map:
            base_query += " AND f.mime_type LIKE ?"
            params.append(type_map[file_type])

    allowed_sorts = ['uploaded_at', 'last_accessed', 'size', 'original_name', 'access_count']
    if sort_by not in allowed_sorts:
        sort_by = 'uploaded_at'
    sort_order = 'ASC' if sort_order == 'ASC' else 'DESC'

    if category == 'recent':
        base_query += f" ORDER BY f.{sort_by} {sort_order} LIMIT 20"
    else:
        base_query += f" ORDER BY f.{sort_by} {sort_order}"

    cur.execute(base_query, params)
    files = cur.fetchall()
    cur.close()
    conn.close()

    # Serialize datetime objects
    for f in files:
        for key in ['uploaded_at', 'last_accessed', 'trashed_at', 'share_expires']:
            if f.get(key) and not isinstance(f[key], str):
                f[key] = f[key].isoformat()

    return jsonify({'files': files})

@app.get('/files/<int:file_id>')
@login_required
def get_file(file_id):
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=?", (file_id, user_id))
    f = cur.fetchone()
    cur.close()
    conn.close()
    if not f:
        return jsonify({'error': 'File not found'}), 404
    for key in ['uploaded_at', 'last_accessed', 'trashed_at', 'share_expires']:
        if f.get(key) and not isinstance(f[key], str):
            f[key] = f[key].isoformat()
    return jsonify({'file': f})


@app.post('/star')
@login_required
def star_file_exact():
    data = request.json or {}
    file_id = data.get('file_id')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE files SET is_starred = 1 - is_starred, last_accessed = datetime('now') WHERE id=? AND user_id=?", (file_id, request.user_id))
        conn.commit()
        cur.execute("SELECT is_starred FROM files WHERE id=?", (file_id,))
        starred = cur.fetchone()['is_starred']
        cur.close()
        conn.close()
        log_activity(request.user_id, 'star' if starred else 'unstar')
        return jsonify({'message': 'Star updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.post('/trash')
@login_required
def trash_file_exact():
    data = request.json or {}
    file_id = data.get('file_id')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE files SET is_trashed = 1, trashed_at = datetime('now') WHERE id=? AND user_id=?", (file_id, request.user_id))
        conn.commit()
        cur.close()
        conn.close()
        log_activity(request.user_id, 'trash')
        return jsonify({'message': 'Moved to trash'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Original files action handler

@app.post('/files/<int:file_id>/action')
@login_required
def file_action(file_id):
    user_id = request.user_id
    data = request.json or {}
    action = data.get('action')

    valid_actions = {'star', 'unstar', 'pin', 'unpin', 'trash', 'restore', 'delete_permanent', 'add_note', 'rename'}
    if not action or action not in valid_actions:
        return jsonify({'error': 'Invalid or missing action'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=?", (file_id, user_id))
    f = cur.fetchone()
    if not f:
        cur.close()
        conn.close()
        return jsonify({'error': 'File not found'}), 404

    if action == 'star':
        cur.execute("UPDATE files SET is_starred=1 WHERE id=?", (file_id,))
    elif action == 'unstar':
        cur.execute("UPDATE files SET is_starred=0 WHERE id=?", (file_id,))
    elif action == 'pin':
        cur.execute("UPDATE files SET is_pinned=1 WHERE id=?", (file_id,))
    elif action == 'unpin':
        cur.execute("UPDATE files SET is_pinned=0 WHERE id=?", (file_id,))
    elif action == 'trash':
        cur.execute("UPDATE files SET is_trashed=1, trashed_at=datetime('now') WHERE id=?", (file_id,))
    elif action == 'restore':
        cur.execute("UPDATE files SET is_trashed=0, trashed_at=NULL WHERE id=?", (file_id,))
    elif action == 'delete_permanent':
        file_path = os.path.join(get_user_storage_path(user_id), f['name'])
        if os.path.exists(file_path):
            os.remove(file_path)
        cur.execute("UPDATE users SET storage_used = MAX(0, storage_used - ?) WHERE id=?", (f['size'], user_id))
        cur.execute("DELETE FROM files WHERE id=?", (file_id,))
    elif action == 'add_note':
        note = data.get('note', '')
        cur.execute("UPDATE files SET notes=? WHERE id=?", (note, file_id))
    elif action == 'rename':
        new_name = data.get('name', '').strip()
        if new_name:
            cur.execute("UPDATE files SET original_name=? WHERE id=?", (new_name, file_id))

    conn.commit()
    log_activity(user_id, action, f['original_name'])
    cur.close()
    conn.close()
    return jsonify({'message': f'Action {action} completed'})

@app.get('/files/<int:file_id>/download')
@login_required_or_token
def download_file(file_id):
    """Download a file safely with correct headers to prevent corruption."""
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=? AND is_trashed=0", (file_id, user_id))
    f = cur.fetchone()
    if not f:
        cur.close()
        conn.close()
        return jsonify({'error': 'File not found'}), 404
        
    cur.execute("UPDATE files SET access_count=access_count+1, last_accessed=datetime('now') WHERE id=?", (file_id,))
    conn.commit()
    cur.close()
    conn.close()

    storage_path = get_user_storage_path(user_id)
    file_path = os.path.abspath(os.path.join(storage_path, f['name']))
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    # Determine reliable MIME type
    mime_type = f.get('mime_type') or get_mime_type(f['original_name'])
    
    # Text files need charset to prevent browser corruption/misinterpretation
    if mime_type.startswith('text/') and 'charset' not in mime_type:
        mime_type += '; charset=utf-8'

    log_activity(user_id, 'download', f['original_name'])
    
    # send_file correctly handles binary data, Content-Length, and RFC 5987 filename encoding
    return send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=True,
        download_name=f['original_name']
    )

@app.get('/files/<int:file_id>/preview')
@login_required_or_token
def preview_file(file_id):
    """Enable browser preview for images, PDFs, text, and media with proper headers."""
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=? AND is_trashed=0", (file_id, user_id))
    f = cur.fetchone()
    if not f:
        cur.close()
        conn.close()
        return jsonify({'error': 'File not found'}), 404

    # Reliable MIME detection
    mime_type = f.get('mime_type') or get_mime_type(f['original_name'])
    mime_base = mime_type.split(';')[0].strip()

    if mime_base not in ALLOWED_PREVIEW_TYPES:
        cur.close()
        conn.close()
        return jsonify({'error': f'Preview not available for this file type ({mime_base})'}), 415

    cur.execute("UPDATE files SET access_count=access_count+1, last_accessed=datetime('now') WHERE id=?", (file_id,))
    conn.commit()
    cur.close()
    conn.close()

    storage_path = get_user_storage_path(user_id)
    file_path = os.path.abspath(os.path.join(storage_path, f['name']))
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    # Add charset for text so browser displays correctly instead of downloading
    if mime_type.startswith('text/') and 'charset' not in mime_type:
        mime_type += '; charset=utf-8'

    log_activity(user_id, 'preview', f['original_name'])

    # Use make_response to add media-specific headers like Accept-Ranges
    response = make_response(send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=False
    ))
    # Required for video/audio seeking
    response.headers['Accept-Ranges'] = 'bytes'
    # Force inline disposition to ensure browser doesn't try to download
    response.headers['Content-Disposition'] = 'inline'
    return response

# 📁 FOLDER SYSTEM ROUTES

@app.get('/folders')
@login_required
def list_folders():
    """Retrieve all folders belonging to the user, including file counts."""
    user_id = request.user_id
    parent_id = request.args.get('parent_id')
    conn = get_db()
    cur = conn.cursor()
    
    # Fetch either root folders or children of a specific folder
    if parent_id:
        cur.execute("SELECT * FROM folders WHERE user_id=? AND parent_id=?", (user_id, int(parent_id)))
    else:
        cur.execute("SELECT * FROM folders WHERE user_id=? AND parent_id IS NULL", (user_id,))
    
    folders = cur.fetchall()
    
    # For each folder, count how many files are inside (excluding trashed files)
    for folder in folders:
        cur.execute("SELECT COUNT(*) as cnt FROM files WHERE folder_id=? AND is_trashed=0", (folder['id'],))
        folder['file_count'] = cur.fetchone()['cnt']
        
        # Ensure timestamp is in string format for JSON
        if folder.get('created_at') and not isinstance(folder['created_at'], str):
            folder['created_at'] = folder['created_at'].isoformat()
            
    cur.close()
    conn.close()
    return jsonify({'folders': folders})

@app.post('/create-folder')
@login_required
def create_folder():
    """Create a new folder. Supports private password-protected folders."""
    user_id = request.user_id
    data = request.json or {}
    name = data.get('name', '').strip()
    parent_id = data.get('parent_id')
    is_private = data.get('is_private', False)
    private_password = data.get('private_password')

    if not name:
        return jsonify({'error': 'Folder name is required'}), 400

    # If it's a private folder, we hash the password for security
    pw_hash = generate_password_hash(private_password) if is_private and private_password else None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO folders (user_id, name, parent_id, is_private, private_password) VALUES (?,?,?,?,?)",
        (user_id, name, parent_id, is_private, pw_hash)
    )
    conn.commit()
    folder_id = cur.lastrowid
    cur.close()
    conn.close()
    
    log_activity(user_id, 'create_folder', name)
    return jsonify({'message': 'Folder created successfully', 'folder_id': folder_id}), 201

@app.post('/folders/<int:folder_id>/unlock')
@login_required
def unlock_folder(folder_id):
    user_id = request.user_id
    data = request.json or {}
    password = data.get('password', '')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM folders WHERE id=? AND user_id=?", (folder_id, user_id))
    folder = cur.fetchone()
    cur.close()
    conn.close()
    if not folder:
        return jsonify({'error': 'Folder not found'}), 404
    if folder['is_private'] and folder.get('private_password') and check_password_hash(folder['private_password'], password):
        return jsonify({'success': True})
    return jsonify({'error': 'Incorrect password'}), 403

@app.delete('/folders/<int:folder_id>')
@login_required
def delete_folder(folder_id):
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM folders WHERE id=? AND user_id=?", (folder_id, user_id))
    folder = cur.fetchone()
    if not folder:
        cur.close()
        conn.close()
        return jsonify({'error': 'Folder not found'}), 404
    # Trash all files in this folder
    cur.execute("UPDATE files SET is_trashed=1, trashed_at=datetime('now') WHERE folder_id=?", (folder_id,))
    cur.execute("DELETE FROM folders WHERE id=?", (folder_id,))
    conn.commit()
    cur.close()
    conn.close()
    log_activity(user_id, 'delete_folder', folder['name'])
    return jsonify({'message': 'Folder deleted'})

# ─────────────────────────────────────────────────────────────────────────────
# SHARING ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/files/<int:file_id>/share')
@login_required
def create_share_link(file_id):
    user_id = request.user_id
    data = request.json or {}
    permission = data.get('permission', 'view')
    expiry_hours = data.get('expiry_hours')  # None = no expiry

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=? AND is_trashed=0", (file_id, user_id))
    f = cur.fetchone()
    if not f:
        cur.close()
        conn.close()
        return jsonify({'error': 'File not found'}), 404

    token = secrets.token_urlsafe(32)
    expires_at = None
    if expiry_hours:
        expires_at = datetime.utcnow() + timedelta(hours=int(expiry_hours))

    cur.execute(
        "INSERT INTO share_links (file_id, token, permission, expires_at) VALUES (?,?,?,?)",
        (file_id, token, permission, expires_at)
    )
    conn.commit()
    cur.close()
    conn.close()

    share_url = f"{request.host_url}share/{token}"
    log_activity(user_id, 'share', f['original_name'], f'Permission: {permission}')
    return jsonify({
        'share_url': share_url,
        'token': token,
        'expires_at': expires_at.isoformat() if expires_at else None,
        'public_download_url': f"{request.host_url}public/download/{file_id}"
    })

@app.get('/share/<token>')
def access_shared_file(token):
    """Public share page — shows file info and a clickable download link (works for ALL permissions)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT sl.*, f.original_name, f.name as stored_name, f.size, f.mime_type, f.user_id
           FROM share_links sl JOIN files f ON sl.file_id=f.id
           WHERE sl.token=?""",
        (token,)
    )
    link = cur.fetchone()
    cur.close()
    conn.close()

    if not link:
        return "Link not found or expired", 404

    if link.get('expires_at') and str(link['expires_at']) < datetime.utcnow().isoformat():
        return "This share link has expired", 410

    # Return a minimal HTML page for shared file
    html = f"""<!DOCTYPE html>
<html><head><title>SkyStore – {link['original_name']}</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#e2e8f0}}
.card{{background:#1e293b;padding:2rem;border-radius:1rem;text-align:center;max-width:400px}}
h2{{margin-bottom:0.5rem}}p{{color:#94a3b8}}
a{{display:inline-block;margin-top:1rem;padding:.75rem 1.5rem;background:#6366f1;color:#fff;border-radius:.5rem;text-decoration:none}}</style>
</head><body><div class="card">
<h2>📁 {link['original_name']}</h2>
<p>Size: {bytes_to_mb(link['size'])} MB</p>
<p>Type: {link['mime_type'] or 'Unknown'}</p>
<a href="/share-download/{token}" class="btn" style="display:inline-block;margin-top:1rem;padding:.75rem 1.5rem;background:#6366f1;color:#fff;border-radius:.5rem;text-decoration:none">⬇ Download File</a>
</div></body></html>"""
    return html

@app.get('/share-download/<token>')
def download_shared_file(token):
    """Serve shared file download correctly."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT sl.*, f.name as stored_name, f.original_name, f.mime_type, f.user_id FROM share_links sl JOIN files f ON sl.file_id=f.id WHERE sl.token=?",
        (token,)
    )
    link = cur.fetchone()
    if not link:
        cur.close()
        conn.close()
        return "Link not found", 404
    if link.get('expires_at') and str(link['expires_at']) < datetime.utcnow().isoformat():
        cur.close()
        conn.close()
        return "Link expired", 410
        
    cur.execute("UPDATE share_links SET access_count=access_count+1 WHERE token=?", (token,))
    conn.commit()
    cur.close()
    conn.close()
    
    storage_path = get_user_storage_path(link['user_id'])
    file_path = os.path.abspath(os.path.join(storage_path, link['stored_name']))
    if not os.path.exists(file_path):
        return "File not found on server", 404
        
    mime_type = link.get('mime_type') or get_mime_type(link['original_name'])
    if mime_type.startswith('text/') and 'charset' not in mime_type:
        mime_type += '; charset=utf-8'

    return send_file(
        file_path,
        as_attachment=True,
        download_name=link['original_name'],
        mimetype=mime_type
    )


@app.get('/share-preview/<token>')
def preview_shared_file(token):
    """Inline browser preview for a shared file."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT sl.*, f.name as stored_name, f.original_name, f.mime_type, f.user_id FROM share_links sl JOIN files f ON sl.file_id=f.id WHERE sl.token=?",
        (token,)
    )
    link = cur.fetchone()
    if not link:
        cur.close()
        conn.close()
        return "Link not found", 404
    if link.get('expires_at') and str(link['expires_at']) < datetime.utcnow().isoformat():
        cur.close()
        conn.close()
        return "Link expired", 410

    mime_type = link.get('mime_type') or get_mime_type(link['original_name'])
    mime_base = mime_type.split(';')[0].strip()

    if mime_base not in ALLOWED_PREVIEW_TYPES:
        cur.close()
        conn.close()
        return "Preview not available for this file type", 415

    cur.execute("UPDATE share_links SET access_count=access_count+1 WHERE token=?", (token,))
    conn.commit()
    cur.close()
    conn.close()

    storage_path = get_user_storage_path(link['user_id'])
    file_path = os.path.abspath(os.path.join(storage_path, link['stored_name']))
    if not os.path.exists(file_path):
        return "File not found on server", 404

    if mime_type.startswith('text/') and 'charset' not in mime_type:
        mime_type += '; charset=utf-8'

    response = make_response(send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=False
    ))
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Disposition'] = 'inline'
    return response

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC DOWNLOAD ROUTE (no login required) — for shareable links
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/public/download/<int:file_id>')
def public_download(file_id):
    """Public download route securely serves files."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM files WHERE id=? AND is_trashed=0", (file_id,))
        f = cur.fetchone()
        if not f:
            cur.close()
            conn.close()
            return jsonify({'error': 'File not found'}), 404

        cur.execute("UPDATE files SET access_count=access_count+1, last_accessed=datetime('now') WHERE id=?", (file_id,))
        conn.commit()
        cur.close()
        conn.close()

        storage_path = get_user_storage_path(f['user_id'])
        file_path = os.path.abspath(os.path.join(storage_path, f['name']))

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on disk'}), 404

        mime_type = f.get('mime_type') or get_mime_type(f['original_name'])

        return send_file(
            file_path,
            as_attachment=True,
            download_name=f['original_name'],
            mimetype=mime_type
        )
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# ─────────────────────────────────────────────────────────────────────────────
# MOVE FILE ROUTE
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/move-file')
@login_required
def move_file():
    """Move a file into a folder. Set folder_id to null to move to root."""
    user_id = request.user_id
    data = request.json or {}
    file_id = data.get('file_id')
    folder_id = data.get('folder_id')  # If this is None, the file moves to root (Home)

    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400

    conn = get_db()
    cur = conn.cursor()
    # Verify the file exists and belongs to this user
    cur.execute("SELECT id FROM files WHERE id=? AND user_id=? AND is_trashed=0", (file_id, user_id))
    f = cur.fetchone()
    if not f:
        cur.close()
        conn.close()
        return jsonify({'error': 'File not found'}), 404

    # If moving to a folder, check that the folder belongs to the user
    if folder_id:
        cur.execute("SELECT id FROM folders WHERE id=? AND user_id=?", (int(folder_id), user_id))
        folder = cur.fetchone()
        if not folder:
            cur.close()
            conn.close()
            return jsonify({'error': 'Destination folder not found'}), 404
        cur.execute("UPDATE files SET folder_id=? WHERE id=?", (int(folder_id), file_id))
    else:
        # No folder_id means move to the main (root) directory
        cur.execute("UPDATE files SET folder_id=NULL WHERE id=?", (file_id,))

    conn.commit()
    cur.close()
    conn.close()
    
    log_activity(user_id, 'move_file', f'Moved file {file_id}')
    return jsonify({'message': 'File moved successfully'})

# 📥 DOWNLOAD AS ZIP ROUTE

@app.post('/download-zip')
@login_required
def download_zip():
    """Bundle multiple files into a single ZIP archive for easy download."""
    import zipfile
    import io
    user_id = request.user_id
    data = request.json or {}
    file_ids = data.get('file_ids', [])

    if not file_ids:
        return jsonify({'error': 'No files selected'}), 400

    conn = get_db()
    cur = conn.cursor()
    # Fetch all requested files to get their disk names and original names
    placeholders = ','.join('?' * len(file_ids))
    cur.execute(
        f"SELECT * FROM files WHERE id IN ({placeholders}) AND user_id=? AND is_trashed=0",
        (*file_ids, user_id)
    )
    files = cur.fetchall()
    cur.close()
    conn.close()

    if not files:
        return jsonify({'error': 'No valid files found'}), 404

    # We build the ZIP file entirely in memory using BytesIO
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            storage_path = get_user_storage_path(user_id)
            file_path = os.path.join(storage_path, f['name'])
            if os.path.exists(file_path):
                # When adding to ZIP, we use the original filename (e.g. "report.pdf")
                zf.write(file_path, arcname=f['original_name'])
    
    # Seek to start of buffer before sending
    zip_buffer.seek(0)

    log_activity(user_id, 'download_zip', f'Bundled {len(files)} files')
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='skystore_archive.zip'
    )

# 🤖 AI FILE SUMMARIZER ROUTE

@app.post('/summarize')
@login_required
def summarize_file():
    """
    Generate an AI-powered summary using an extractive algorithm.
    Supported types: Plain text (.txt) and PDF documents.
    No external API calls are made—everything runs locally on your server.
    """
    user_id = request.user_id
    data = request.json or {}
    file_id = data.get('file_id')

    if not file_id:
        return jsonify({'error': 'file_id is required'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM files WHERE id=? AND user_id=? AND is_trashed=0", (file_id, user_id))
    f = cur.fetchone()
    cur.close()
    conn.close()

    if not f:
        return jsonify({'error': 'File not found'}), 404

    mime = f.get('mime_type', '')
    storage_path = get_user_storage_path(user_id)
    file_path = os.path.join(storage_path, f['name'])

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    text = ''
    try:
        # Read text content based on file type
        if mime == 'text/plain' or f['original_name'].lower().endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                text = fh.read()
        elif mime == 'application/pdf' or f['original_name'].lower().endswith('.pdf'):
            import PyPDF2
            with open(file_path, 'rb') as fh:
                reader = PyPDF2.PdfReader(fh)
                pages = []
                # Read up to 10 pages to generate a good summary without being too slow
                for page in reader.pages[:10]:
                    pages.append(page.extract_text() or '')
                text = '\n'.join(pages)
        else:
            return jsonify({'error': 'Summarization only supports .txt and .pdf files'}), 415
    except ImportError:
        return jsonify({'error': 'Missing dependency: PyPDF2. Run "pip install PyPDF2" to enable PDF support.'}), 500
    except Exception as e:
        return jsonify({'error': f'Could not process file: {str(e)}'}), 500

    if not text.strip():
        return jsonify({'summary': 'This file appears to be empty or contains no readable text.'})

    # --- ADVANCED SUMMARY LOGIC (Beginner-Friendly Extractive NLP) ---
    import re
    # 1. Split text into clean sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

    # 2. Pick representative sentences (First 3 + Last 2)
    if len(sentences) <= 5:
        summary_sentences = sentences
    else:
        summary_sentences = sentences[:3] + ['... [Content Snipped] ...'] + sentences[-2:]

    # 3. Basic keyword extraction: Find most frequent long words
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text.lower())
    stop_words = {'could','should','would','their','there','about','which','through'}
    freq = {}
    for word in words:
        if word not in stop_words:
            freq[word] = freq.get(word, 0) + 1
    
    # Sort by frequency and take top 8
    top_words = sorted(freq.items(), key=lambda x: -x[1])[:8]
    keywords = ', '.join(w.capitalize() for w, _ in top_words)

    log_activity(user_id, 'summarize', f['original_name'])
    
    return jsonify({
        'summary': ' '.join(summary_sentences),
        'stats': {
            'word_count': len(text.split()),
            'character_count': len(text),
            'sentence_count': len(sentences)
        },
        'keywords': keywords if keywords else 'None detected'
    })

# ─────────────────────────────────────────────────────────────────────────────
# INSIGHTS ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/insights')
@login_required
def get_insights():
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()

    # Storage breakdown by type
    cur.execute("""
        SELECT mime_type, SUM(size) as total_size, COUNT(*) as file_count
        FROM files WHERE user_id=? AND is_trashed=0
        GROUP BY mime_type
    """, (user_id,))
    raw_breakdown = cur.fetchall()

    breakdown = {'images': 0, 'videos': 0, 'audio': 0, 'documents': 0, 'archives': 0, 'other': 0}
    for row in raw_breakdown:
        cat = get_file_category(row['mime_type'])
        breakdown[cat] = breakdown.get(cat, 0) + row['total_size']

    # Most accessed files
    cur.execute("""
        SELECT id, original_name, access_count, size, mime_type, last_accessed
        FROM files WHERE user_id=? AND is_trashed=0 AND access_count > 0
        ORDER BY access_count DESC LIMIT 5
    """, (user_id,))
    most_accessed = cur.fetchall()

    # Largest files
    cur.execute("""
        SELECT id, original_name, size, mime_type FROM files
        WHERE user_id=? AND is_trashed=0 ORDER BY size DESC LIMIT 5
    """, (user_id,))
    largest = cur.fetchall()

    # Unused files (not accessed in 30 days)
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    cur.execute("""
        SELECT id, original_name, size, mime_type, last_accessed FROM files
        WHERE user_id=? AND is_trashed=0 AND last_accessed < ?
        ORDER BY last_accessed ASC LIMIT 10
    """, (user_id, cutoff))
    unused = cur.fetchall()

    # Cleanup suggestions: large (>10MB) or unused
    cur.execute("SELECT storage_used, storage_limit FROM users WHERE id=?", (user_id,))
    user_data = cur.fetchone()

    # Total files count
    cur.execute("SELECT COUNT(*) as total FROM files WHERE user_id=? AND is_trashed=0", (user_id,))
    total_files = cur.fetchone()['total']

    cur.close()
    conn.close()

    # Serialize datetimes (SQLite returns strings, so only convert if not already a string)
    for item in most_accessed + largest + unused:
        for key in ['last_accessed', 'uploaded_at']:
            if item.get(key) and not isinstance(item[key], str):
                item[key] = item[key].isoformat()

    return jsonify({
        'storage_breakdown': breakdown,
        'most_accessed': most_accessed,
        'largest_files': largest,
        'unused_files': unused,
        'storage_used': user_data['storage_used'],
        'storage_limit': user_data['storage_limit'],
        'total_files': total_files
    })

# ─────────────────────────────────────────────────────────────────────────────
# ACTIVITY LOG
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/activity')
@login_required
def get_activity():
    user_id = request.user_id
    limit = int(request.args.get('limit', 50))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT action, target_name, details, ip_address, created_at FROM activity_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    logs = cur.fetchall()
    cur.close()
    conn.close()
    for log in logs:
        if log.get('created_at') and not isinstance(log['created_at'], str):
            log['created_at'] = log['created_at'].isoformat()
    return jsonify({'activity': logs})

# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS & PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/settings/theme')
@login_required
def update_theme():
    data = request.json or {}
    theme = data.get('theme', 'dark')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET theme=? WHERE id=?", (theme, request.user_id))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Theme updated'})

@app.post('/settings/password')
@login_required
def change_password():
    data = request.json or {}
    current = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE id=?", (request.user_id,))
    user = cur.fetchone()
    if not check_password_hash(user['password_hash'], current):
        cur.close()
        conn.close()
        return jsonify({'error': 'Current password is incorrect'}), 400
    if len(new_pw) < 6:
        cur.close()
        conn.close()
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    new_hash = generate_password_hash(new_pw)
    cur.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, request.user_id))
    conn.commit()
    cur.close()
    conn.close()
    log_activity(request.user_id, 'change_password')
    return jsonify({'message': 'Password updated successfully'})

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/search')
@login_required
def search_files():
    user_id = request.user_id
    query = request.args.get('q', '').strip()
    file_type = request.args.get('type', '')

    if not query:
        return jsonify({'files': []})

    conn = get_db()
    cur = conn.cursor()
    sql = "SELECT * FROM files WHERE user_id=? AND is_trashed=0 AND original_name LIKE ?"
    params = [user_id, f'%{query}%']

    if file_type:
        type_map = {'image': 'image/%', 'video': 'video/%', 'audio': 'audio/%', 'pdf': 'application/pdf', 'text': 'text/%'}
        if file_type in type_map:
            sql += " AND mime_type LIKE ?"
            params.append(type_map[file_type])

    sql += " ORDER BY last_accessed DESC LIMIT 30"
    cur.execute(sql, params)
    files = cur.fetchall()
    cur.close()
    conn.close()
    for f in files:
        for key in ['uploaded_at', 'last_accessed', 'trashed_at']:
            if f.get(key) and not isinstance(f[key], str):
                f[key] = f[key].isoformat()
    return jsonify({'files': files})

# ─────────────────────────────────────────────────────────────────────────────
# STORAGE INFO
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/storage')
@login_required
def storage_info():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT storage_used, storage_limit FROM users WHERE id=?", (request.user_id,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify({
        'storage_used': data['storage_used'],
        'storage_limit': data['storage_limit'],
        'storage_used_mb': bytes_to_mb(data['storage_used']),
        'storage_limit_mb': bytes_to_mb(data['storage_limit']),
        'percentage': round((data['storage_used'] / data['storage_limit']) * 100, 1) if data['storage_limit'] else 0
    })

# ─────────────────────────────────────────────────────────────────────────────
# BACKUP REMINDER
# ─────────────────────────────────────────────────────────────────────────────
@app.get('/backup-reminder')
@login_required
def backup_reminder():
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT last_login, backup_reminder_sent FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    # Check if user has uploaded anything recently (within 7 days)
    conn = get_db()
    cur = conn.cursor()
    cutoff = datetime.utcnow() - timedelta(days=7)
    cur.execute("SELECT COUNT(*) as cnt FROM files WHERE user_id=? AND uploaded_at > ?", (user_id, cutoff))
    recent_uploads = cur.fetchone()['cnt']
    cur.close()
    conn.close()

    if recent_uploads == 0:
        # Check if reminder not already sent today
        if not user['backup_reminder_sent'] or str(user['backup_reminder_sent']) < (datetime.utcnow() - timedelta(days=1)).isoformat():
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE users SET backup_reminder_sent=datetime('now') WHERE id=?", (user_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'show_reminder': True, 'message': '⚠️ You haven\'t uploaded any files in the last 7 days. Consider backing up your important files!'})
    return jsonify({'show_reminder': False})

# ─────────────────────────────────────────────────────────────────────────────
# AUTO-ORGANIZE
# ─────────────────────────────────────────────────────────────────────────────
@app.post('/auto-organize')
@login_required
def auto_organize():
    user_id = request.user_id
    conn = get_db()
    cur = conn.cursor()

    # Get all non-organized, non-trashed files
    cur.execute("SELECT * FROM files WHERE user_id=? AND is_trashed=0 AND folder_id IS NULL", (user_id,))
    files = cur.fetchall()

    cat_map = {'images': 'Images', 'videos': 'Videos', 'audio': 'Audio', 'documents': 'Documents', 'archives': 'Archives', 'other': 'Other'}
    organized = 0
    for f in files:
        cat = get_file_category(f['mime_type'])
        folder_name = cat_map.get(cat, 'Other')
        cur.execute("SELECT id FROM folders WHERE user_id=? AND name=? AND parent_id IS NULL", (user_id, folder_name))
        folder = cur.fetchone()
        if folder:
            cur.execute("UPDATE files SET folder_id=? WHERE id=?", (folder['id'], f['id']))
            organized += 1

    conn.commit()
    cur.close()
    conn.close()
    log_activity(user_id, 'auto_organize', f'{organized} files')
    return jsonify({'message': f'Organized {organized} files into folders'})

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs('storage', exist_ok=True)
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")
    app.run(debug=True, host='0.0.0.0', port=5050)
