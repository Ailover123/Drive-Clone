# ☁️ SkyStore: Multi-Tenant Secure Storage

A high-performance, secure, and visually stunning private cloud storage solution built with Flask. Perfect for local network file sharing and demonstrations.

## ✨ Features
- **Multi-Tenant Isolation**: Completely separate storage spaces for each user.
- **Real-Time UI**: Modern, responsive interface with search and category filtering.
- **Smart Metadata**: Ability to "Star" important files and manage a "Trash" bin.
- **Premium Aesthetics**: Dark-mode inspired glassmorphism design.
- **Global Access Ready**: Pre-optimized for ngrok and HTTPS secure tunnels.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.x installed.
- Pip installed.

### 2. Installation
1. Clone this repository (or download the files).
2. Install dependencies:
   ```bash
   pip install flask werkzeug
   ```

### 3. Run the Server
```bash
python app.py
```
The server will start on **[http://localhost:5050](http://localhost:5050)**.

## 🛡️ Important for Live Demo: Preserving Filenames

Modern browsers (Chrome/Edge) often block correctly-named downloads from "untrusted" local connections (HTTP). To ensure your filenames are preserved 100% of the time during a live demo:

### **The Gold Standard (HTTPS)**
Use **ngrok** to create a secure tunnel. Secure links (HTTPS) tell the browser the connection is safe, which unlocks native filename preservation.
```bash
ngrok http 5050
```
Then use the `https://...` link provided by ngrok.

### **Manual Fallbacks**
If you are running locally without HTTPS:
1. **Click "Open"**: View the file in a new tab, then save from the browser's own viewer.
2. **Right-click Download**: Select "Save link as..." to manually confirm the filename.

## 📂 Project Structure
- `app.py`: Flask backend with secure file handling and metadata logic.
- `index.html`: Unified frontend with modern CSS and reactive JS.
- `storage/`: Root directory for tenant isolated folders.
- `GUIDE.md`: Deep-dive architectural guide and concepts.
