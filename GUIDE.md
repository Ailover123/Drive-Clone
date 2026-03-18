# 📂 CloudDrive: User Guide & Project Documentation

Welcome to **CloudDrive**, a mini Google Drive clone! This guide will help you set up, run, and explore the system.

---

## 🌟 What is CloudDrive?
CloudDrive is a minimal but powerful cloud storage web application. It allows different users (tenants) to upload, store, and access their files in total isolation from one another.

### **The Workflow**
1. **Login**: Just enter a "Tenant Name" (username) in the top bar. No password needed for this prototype!
2. **Upload**: Select any file from your computer and hit "Upload".
3. **Manage**: Use the sidebar to see your **Recent** files, **Starred** items, or move things to the **Trash**.
4. **Download**: Click "Download" on any file card to get it back onto your device.

---

## 🛠️ How to Set Up This Project

### 1. Install Dependencies
- Ensure you have **Python 3.x** installed.
- Open your terminal and run:
  ```bash
  pip install flask
  ```

### 2. Install ngrok (For Global Access)
To access your files from a different network or your phone, follow these steps:
1.  **Option A (Manual)**: Go to [ngrok.com](https://ngrok.com/), download the ZIP, and extract `ngrok.exe` to this folder.
2.  **Option B (Easiest)**: Install **ngrok** via the **Microsoft Store**. Once installed, just open it to get the command interface.
3.  **Connect Account**: Run your authorization command from the dashboard:
    ```bash
    ngrok config add-authtoken <YOUR_TOKEN>
    ```
    *(Note: See `image.png` in the project folder for a screenshot of where to find your token!)*

### 3. Start the Server
1. Open a terminal in this project folder.
2. Run: `python app.py`
3. Your drive is now live at `http://127.0.0.1:5050`

---

## 🌐 Global Access (Mobile & Remote)
**IMPORTANT**: If the server port changes (we are now using **5050**), you must **restart** ngrok.

1.  Open a **second** terminal window.
2.  Stop any old ngrok by pressing `Ctrl + C`.
3.  Run: `ngrok http 5050`
4.  Copy the new `Forwarding` URL.
4. Open that URL on your phone or any other device!

---

## 💡 Troubleshooting
*   **Filename Issue**: If files download as UUIDs, try **Right-clicking** the Download/Open button and selecting **"Save link as..."**. This is a known browser quirk in some versions of Chrome that this method fixes!
*   **Not Opening**: Ensure you have a PDF viewer or the correct app installed for the file type.

---

## ☁️ Cloud Computing Concepts
This project demonstrates four pillars of modern cloud systems:
- **Multi-Tenancy**: Data is logically isolated in folders (`storage/<username>/`).
- **Elasticity & Networking (ngrok)**: Bridging a local service to the global internet via tunnels.
- **Stateless Design**: The UI (`index.html`) is separate from the "persistence layer" (`storage/`).
- **Sanitization & Security**: Using `secure_filename` to manage file storage securely.

---

## 📁 Project Structure
- `app.py`: The "Brain" (Backend API).
- `index.html`: The "Face" (Frontend UI).
- `storage/`: Where all your files are actually saved (organized by username).
- `.metadata.json`: (Hidden inside user folders) Stores your stars and trash status.

---
**Developed as a Cloud Computing Prototype.**
