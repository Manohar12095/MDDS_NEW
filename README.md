Visit At : https://mdds-new-rnrp.vercel.app

# 🏥 Multi-Disease Diagnostic System (MDDS)

> **Developed by IN NET CREATIONS · Created by S. Manohar**  
> AI-powered health screening portal for Heart Disease, Diabetes, Brain Tumors, Kidney Disease, and Liver Disease — built with Flask, scikit-learn, TensorFlow & Vanilla JS.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Backend-black?logo=flask)](https://flask.palletsprojects.com)
[![Security](https://img.shields.io/badge/Security-Hardened%20(CSP%20%2B%20Rate%20Limit)-brightgreen)](https://owasp.org)
[![Deployment](https://img.shields.io/badge/Deployment-Vercel%20%7C%20Gunicorn-success)](https://vercel.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

🌐 **Live Website:** [https://mdds-new-rnrp.vercel.app/](https://mdds-new-rnrp.vercel.app/)

---

## ✨ Features

- 🫀 **Heart Disease** prediction (13 clinical parameters via Random Forest / Decision Trees)
- 🩸 **Diabetes** screening (8 diagnostic markers with standardized scaling)
- 🧠 **Brain Tumor** detection from MRI images (TensorFlow CNN model)
- 🫘 **Kidney Disease** classification (10 key renal function markers)
- 🟠 **Liver Disease** analysis (10 biochemical hepatic indicators)
- 🤖 **AI Chatbot** conversational health screening assistant
- 📄 **PDF Medical Report** generation (complete multi-prediction health summary with downloadable base64 PDF)
- 📬 **Live Contact & Email Delivery System**:
  - **Tier 1 (Direct Gmail SMTP SSL)**: Instant notifications via Google's secure SMTP (`smtp.gmail.com:465`).
  - **Tier 2 (Cloud HTTPS Email Gateway)**: Serverless-compatible delivery routing directly to `innetcreations@gmail.com`.
  - **Tier 3 (Browser-to-Gateway Fallback)**: Direct dispatch fail-safe so customer messages never get lost.
- 🎨 **Modern Glassmorphism UI**: Interactive animated star canvas, floating particle connections, 3D cursor-tracking card tilt, and smooth navigation.

---

## 🛡️ Cybersecurity & Anti-Malware Hardening

- **Content Security Policy (CSP)**: Blocks Cross-Site Scripting (XSS), malicious injections, and rogue external resources.
- **Clickjacking & MIME Protection**: Enforces `X-Frame-Options: SAMEORIGIN` and `X-Content-Type-Options: nosniff`.
- **CSRF & Origin Guard**: Rejects unauthorized cross-origin `POST`/`PUT`/`DELETE` attempts.
- **Automated Scanner Blocker**: Automatically detects and drops requests from vulnerability scanners (`sqlmap`, `nikto`, `masscan`, `nmap`, `burpsuite`) and sensitive file attacks (`.env`, `.git`, `.php`, `wp-admin`).
- **Input Sanitization & Bounds Checking**: Strips HTML tags and verifies all medical metrics against physiological boundaries.
- **Upload Malware Shield**: Brain MRI uploads are limited to 10 MB, restricted to valid image MIME types, and validated in-memory via PIL to reject disguised executable polyglots.
- **DDoS & Flood Shield**: Sliding-window rate limiting per IP on all API endpoints with automatic temporary IP bans for abusive requests.

---

## ⚡ Concurrency & Performance Optimization

- **In-Memory Pre-Warming**: ML models are preloaded into RAM on startup with thread locks, reducing prediction latency to **under 20 milliseconds**.
- **Multi-Threaded Serving**: Thread-safe architecture allows multiple users to run simultaneous diagnostic screenings without blocking or overloading.
- **Response Compression**: Gzip compression via `flask-compress` minimizes payload sizes for HTML, CSS, JS, and JSON.
- **Static Asset Caching**: 24-hour immutable cache headers on images, CSS, and JS files.
- **Multi-View Responsiveness**: Fluid layouts optimized for mobile devices (≤480px), tablets (481px–768px), laptops, and large desktop screens.

---

## 🚀 Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/Manohar12095/MDDS_NEW.git
cd MDDS_NEW
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install tensorflow   # optional locally for Brain Tumor MRI detection
```

### 4. Configure Environment Variables (Optional for Direct Gmail SMTP)

Create a `.env` file in the root directory (or use `.env.example`):

```ini
GMAIL_USER=innetcreations@gmail.com
GMAIL_APP_PASSWORD=your_16_character_google_app_password
CONTACT_RECIPIENT=innetcreations@gmail.com
```

> **Note:** If `GMAIL_APP_PASSWORD` is omitted, the contact form automatically uses the HTTPS Cloud Email Gateway to deliver messages to `innetcreations@gmail.com`.

### 5. Run the server

```bash
python server.py
```

Open your browser at:
```
http://127.0.0.1:5000
```

---

## 🌐 Production Deployment

### Deploying on Vercel
1. Import this repository into [Vercel](https://vercel.com).
2. The project includes [vercel.json](file:///c:/Users/manoh/Desktop/Temp%203%20%5BTools%5D/Temp%205/Projects/Mdds/vercel.json) pre-configured with Python Serverless runtime and static edge caching.
3. (Optional) In **Project Settings** → **Environment Variables**, add `GMAIL_USER` and `GMAIL_APP_PASSWORD` for direct SMTP delivery.

### Deploying on Render / Railway / Heroku
The project includes a production [Procfile](file:///c:/Users/manoh/Desktop/Temp%203%20%5BTools%5D/Temp%205/Projects/Mdds/Procfile) and [gunicorn.conf.py](file:///c:/Users/manoh/Desktop/Temp%203%20%5BTools%5D/Temp%205/Projects/Mdds/gunicorn.conf.py):
```bash
gunicorn -c gunicorn.conf.py server:app
```

---

## 📁 Project Structure

```
MDDS_NEW/
├── server.py              # Flask backend, security middleware & prediction APIs
├── requirements.txt       # Dependencies with security & compression libraries
├── vercel.json            # Vercel deployment configuration
├── Procfile               # Production WSGI process configuration
├── gunicorn.conf.py       # High-concurrency Gunicorn configuration
├── .env.example           # Environment variables template
├── static/
│   ├── css/style.css      # Dark glassmorphism & responsive stylesheet
│   ├── js/app.js          # Core frontend application scripts
│   └── img/               # Brand logos and high-res diagnostic module cards
├── templates/             # Jinja2 HTML templates
│   ├── base.html          # Base layout with IN NET CREATIONS branding
│   ├── index.html         # Landing page with smooth scroll & 3D cards
│   ├── heart.html         # Heart disease diagnostic screening
│   ├── diabetes.html      # Diabetes diagnostic screening
│   ├── brain.html         # Brain tumor MRI deep learning detection
│   ├── kidney.html        # Kidney disease diagnostic screening
│   ├── liver.html         # Liver disease diagnostic screening
│   ├── chatbot.html       # AI health assistant
│   ├── report.html        # Multi-disease PDF report generator
│   └── contact.html       # Multi-tier email contact form
└── models/                # ML model files (auto-loaded in memory)
```

---

## ⚠️ Disclaimer

This system is designed for **AI-assisted screening and educational purposes only**. It does **not** provide a definitive medical diagnosis. Always seek the advice of a qualified physician or healthcare professional with any questions regarding medical conditions.

---

## 🏢 Organization & Author

- **Organization:** **IN NET CREATIONS**  
- **Lead Developer & Creator:** **S. Manohar**  
- **Contact:** [innetcreations@gmail.com](mailto:innetcreations@gmail.com)
