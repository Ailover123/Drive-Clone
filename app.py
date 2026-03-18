import os
import mimetypes
import json
import time
import io
import zipfile
import urllib.parse
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'storage'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure storage directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_user_path(username):
    """Sanitize username and return the absolute path to the user's storage."""
    safe_username = secure_filename(username)
    if not safe_username:
        return None
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], safe_username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "index.html not found", 404

@app.post('/upload')
def upload_file():
    if 'file' not in request.files or 'username' not in request.form:
        return jsonify({"error": "File and username are required"}), 400
    
    file = request.files['file']
    username = request.form['username']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user_dir = get_user_path(username)
    filename = secure_filename(file.filename)
    
    if '.' not in filename:
        ext = mimetypes.guess_extension(file.content_type)
        if ext:
            filename += ext
    
    file_path = os.path.join(user_dir, filename)
    file.save(file_path)
    
    update_metadata(username, filename, 'starred', False)
    update_metadata(username, filename, 'trashed', False)
    
    return jsonify({"message": f"File '{filename}' uploaded successfully"}), 201

def get_metadata(username):
    user_dir = get_user_path(username)
    meta_path = os.path.join(user_dir, '.metadata.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_metadata(username, metadata):
    user_dir = get_user_path(username)
    meta_path = os.path.join(user_dir, '.metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(metadata, f)

def update_metadata(username, filename, key, value):
    metadata = get_metadata(username)
    if filename not in metadata:
        metadata[filename] = {}
    metadata[filename][key] = value
    save_metadata(username, metadata)

@app.get('/files')
def list_files():
    username = request.args.get('username')
    category = request.args.get('category', 'all')
    
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    user_dir = get_user_path(username)
    metadata = get_metadata(username)
    
    all_files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f)) and f != '.metadata.json']
    
    result_files = []
    if category == 'all':
        result_files = [f for f in all_files if not metadata.get(f, {}).get('trashed', False)]
    elif category == 'starred':
        result_files = [f for f in all_files if metadata.get(f, {}).get('starred', False) and not metadata.get(f, {}).get('trashed', False)]
    elif category == 'trash':
        result_files = [f for f in all_files if metadata.get(f, {}).get('trashed', False)]
    elif category == 'recent':
        non_trashed = [f for f in all_files if not metadata.get(f, {}).get('trashed', False)]
        non_trashed.sort(key=lambda x: os.path.getmtime(os.path.join(user_dir, x)), reverse=True)
        result_files = non_trashed[:10]

    file_list = []
    for f in result_files:
        file_list.append({
            "name": f,
            "starred": metadata.get(f, {}).get('starred', False),
            "trashed": metadata.get(f, {}).get('trashed', False),
            "size": os.path.getsize(os.path.join(user_dir, f)),
            "mtime": os.path.getmtime(os.path.join(user_dir, f))
        })
    return jsonify({"files": file_list})

@app.post('/action')
def file_action():
    data = request.json
    username = data.get('username')
    filename = data.get('filename')
    action = data.get('action')
    
    if not username or not filename or not action:
        return jsonify({"error": "Missing parameters"}), 400
        
    user_dir = get_user_path(username)
    if action == 'star':
        update_metadata(username, filename, 'starred', True)
    elif action == 'unstar':
        update_metadata(username, filename, 'starred', False)
    elif action == 'trash':
        update_metadata(username, filename, 'trashed', True)
    elif action == 'restore':
        update_metadata(username, filename, 'trashed', False)
    elif action == 'delete':
        file_path = os.path.join(user_dir, secure_filename(filename))
        if os.path.exists(file_path):
            os.remove(file_path)
            metadata = get_metadata(username)
            if filename in metadata:
                del metadata[filename]
                save_metadata(username, metadata)
                
    return jsonify({"message": f"Action {action} completed"})

@app.get('/download/<username>/<filename>')
def download_file(username, filename):
    user_dir = get_user_path(username)
    if not user_dir: return jsonify({"error": "Invalid username"}), 404
    
    safe_fn = secure_filename(filename)
    path = os.path.join(user_dir, safe_fn)
    if not os.path.exists(path): return jsonify({"error": "File not found"}), 404

    # The most robust header set for modern browsers
    filename_quoted = urllib.parse.quote(safe_fn)
    
    response = make_response(send_file(path))
    response.headers['Content-Disposition'] = f"attachment; filename=\"{safe_fn}\"; filename*=UTF-8''{filename_quoted}"
    response.headers['Content-Type'] = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
    return response

@app.get('/view/<username>/<filename>')
def view_file(username, filename):
    user_dir = get_user_path(username)
    if not user_dir: return jsonify({"error": "Invalid username"}), 404
    
    safe_fn = secure_filename(filename)
    return send_from_directory(user_dir, safe_fn)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
