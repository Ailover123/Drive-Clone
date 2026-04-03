import re

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace API prefix
replacements = {
    "@app.post('/api/auth/register')": "@app.post('/register')",
    "@app.post('/api/auth/login')": "@app.post('/login')",
    "@app.post('/api/auth/logout')": "@app.post('/logout')",
    "@app.get('/api/auth/me')": "@app.get('/user')",
    "@app.post('/api/files/upload')": "@app.post('/upload')",
    "@app.get('/api/files')": "@app.get('/files')",
    "@app.get('/api/files/<int:file_id>')": "@app.get('/files/<int:file_id>')",
    "@app.post('/api/files/<int:file_id>/action')": "@app.post('/files/<int:file_id>/action')",
    "@app.get('/api/files/<int:file_id>/download')": "@app.get('/files/<int:file_id>/download')",
    "@app.get('/api/files/<int:file_id>/preview')": "@app.get('/files/<int:file_id>/preview')",
    "@app.post('/api/files/<int:file_id>/share')": "@app.post('/files/<int:file_id>/share')",
    "@app.post('/api/folders')": "@app.post('/create-folder')",
    "@app.get('/api/folders')": "@app.get('/folders')",
    "@app.post('/api/folders/<int:folder_id>/unlock')": "@app.post('/folders/<int:folder_id>/unlock')",
    "@app.delete('/api/folders/<int:folder_id>')": "@app.delete('/folders/<int:folder_id>')",
    "@app.get('/api/insights')": "@app.get('/insights')",
    "@app.get('/api/activity')": "@app.get('/activity')",
    "@app.post('/api/settings/theme')": "@app.post('/settings/theme')",
    "@app.post('/api/settings/password')": "@app.post('/settings/password')",
    "@app.get('/api/search')": "@app.get('/search')",
    "@app.get('/api/storage')": "@app.get('/storage')",
    "@app.get('/api/backup-reminder')": "@app.get('/backup-reminder')",
    "@app.post('/api/auto-organize')": "@app.post('/auto-organize')"
}

for old, new in replacements.items():
    code = code.replace(old, new)

# Update Login Token
code = code.replace(
    "session['user_id'] = user['id']\n        log_activity(user['id'], 'login')",
    "token = secrets.token_hex(32)\n        TOKENS[token] = user['id']\n        log_activity(user['id'], 'login')"
)

code = code.replace(
    "return jsonify({'message': 'Logged in successfully', 'user': {",
    "return jsonify({'message': 'Logged in successfully', 'token': token, 'user': {"
)

code = code.replace(
    "session.pop('user_id', None)",
    "auth = request.headers.get('Authorization')\n    if auth and auth.startswith('Bearer '):\n        TOKENS.pop(auth.split(' ')[1], None)"
)

# Fix 'me' user session handling
me_old = """@app.get('/user')
def me():
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        user_id = session['user_id']"""
me_new = """@app.get('/user')
def me():
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        return jsonify({'error': 'Authentication required'}), 401
    token = auth.split(' ')[1]
    if token not in TOKENS:
        return jsonify({'error': 'Invalid token'}), 401
    
    try:
        user_id = TOKENS[token]"""
code = code.replace(me_old, me_new)

# Replace remaining `session['user_id']` accesses
code = code.replace("session['user_id']", "request.user_id")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated app.py successfully!")
