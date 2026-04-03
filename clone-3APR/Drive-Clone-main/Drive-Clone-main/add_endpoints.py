import re

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add specific /star and /trash endpoints
new_endpoints = """
@app.post('/star')
@login_required
def star_file_exact():
    data = request.json or {}
    file_id = data.get('file_id')
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE files SET is_starred = NOT is_starred, last_accessed = CURRENT_TIMESTAMP WHERE id=%s AND user_id=%s", (file_id, request.user_id))
        conn.commit()
        cur.execute("SELECT is_starred FROM files WHERE id=%s", (file_id,))
        starred = cur.fetchone()[0]
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
        cur.execute("UPDATE files SET is_trashed = TRUE, trashed_at = CURRENT_TIMESTAMP WHERE id=%s AND user_id=%s", (file_id, request.user_id))
        conn.commit()
        cur.close()
        conn.close()
        log_activity(request.user_id, 'trash')
        return jsonify({'message': 'Moved to trash'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Original files action handler
"""

code = code.replace("# Original files action handler", new_endpoints)

if "star_file_exact" not in code:
    code = code.replace("@app.post('/files/<int:file_id>/action')", new_endpoints + "\n@app.post('/files/<int:file_id>/action')")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

with open('app.js', 'r', encoding='utf-8') as f:
    jscode = f.read()

jscode = jscode.replace(
    "const res = await api('POST', `/files/${fileId}/action`, { action, ...extra });",
    """let res;
  if (action === 'star' || action === 'unstar') {
    res = await api('POST', '/star', { file_id: fileId });
  } else if (action === 'trash') {
    res = await api('POST', '/trash', { file_id: fileId });
  } else {
    res = await api('POST', `/files/${fileId}/action`, { action, ...extra });
  }"""
)

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(jscode)

print("Added /star and /trash")
