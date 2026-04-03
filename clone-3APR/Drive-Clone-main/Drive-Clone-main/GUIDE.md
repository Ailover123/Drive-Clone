# ☁️ SkyStore – Advanced Cloud Storage System

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- MySQL Server running on port `3306` (or update `DB_CONFIG` in `app.py`)

### 2. Set MySQL Password
Open `app.py` and find `DB_CONFIG`. Set your MySQL root password:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_PASSWORD_HERE',
    ...
}
```

### 3. Install Dependencies
```bash
pip install flask werkzeug mysql-connector-python
```

### 4. Run the App
```bash
python app.py
```
Open: **http://localhost:5050**

The database (`skystore`) is created automatically on first run.

---

## ✨ Features

| Feature | Description |
|---|---|
| Auth | Register / Login with hashed passwords |
| Upload | Drag & drop, multi-file, progress bar |
| File Management | View, star, pin, rename, note, trash, restore |
| Folders | Nested folders + 🔒 private password folders |
| Sharing | Generate links with view/download permission + expiry |
| Search | Search by name, filter by file type |
| Insights | Storage chart, most accessed, largest, unused files |
| Activity Log | Full audit trail of actions |
| Auto-Organizer | Sort files into Images/Videos/Documents/etc |
| Dark/Light Mode | Toggle in topbar or settings |
| Cleanup Suggestions | One-click trash for unused files |
| Undo Delete | 5-second undo bar after trashing |
| File Preview | Images, PDFs, video, audio, text inline |
| Backup Reminder | Notifies if no uploads in 7 days |
| Per-user Storage | 100 MB limit with live usage bar |
| Trash | Auto-delete after 30 days + manual empty |

---

## 📁 Project Structure

```
Drive-Clone-main/
├── app.py          ← Flask backend (all API routes)
├── index.html      ← App shell (HTML)
├── style.css       ← Full UI styles
├── app.js          ← Frontend logic
├── requirements.txt
├── storage/        ← Uploaded files (per-user folders)
└── GUIDE.md        ← This file
```

---

## 🌐 Global Access via ngrok
```bash
ngrok http 5050
```
Share the ngrok URL for remote access.
