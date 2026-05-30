# 🏥 Multi-Disease Diagnostic System (MDDS)

> AI-powered health screening for Heart Disease, Diabetes, Brain Tumors, Kidney Disease, and Liver Disease — built with Flask, scikit-learn, TensorFlow & Vanilla JS.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Backend-black?logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ✨ Features

- 🫀 **Heart Disease** prediction (13 clinical parameters)
- 🩸 **Diabetes** screening (8 diagnostic markers)
- 🧠 **Brain Tumor** detection from MRI images (TensorFlow CNN)
- 🫘 **Kidney Disease** classification (10 lab values)
- 🟠 **Liver Disease** analysis (10 biochemical indicators)
- 🤖 **AI Chatbot** powered by Google Gemini
- 📄 **PDF Report** generation (full patient history or single result)
- 🌐 Premium dark glassmorphism UI with animated background

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
pip install tensorflow   # needed locally for Brain Tumor detection
```

> ⚠️ `tensorflow` is excluded from `requirements.txt` for Vercel deployment (size limit).
> Install it manually to enable the Brain Tumor page locally.

### 4. Run the server

```bash
python server.py
```

### 5. Open in your browser

```
http://127.0.0.1:5000
```

The ML models are downloaded automatically from Google Drive on first use — no manual setup needed.

---

## 📁 Project Structure

```
MDDS_NEW/
├── server.py           # Flask backend & all API routes
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel deployment config
├── templates/          # Jinja2 HTML pages
│   ├── base.html
│   ├── index.html
│   ├── heart.html
│   ├── diabetes.html
│   ├── brain.html
│   ├── kidney.html
│   ├── liver.html
│   ├── chatbot.html
│   ├── report.html
│   └── contact.html
├── static/
│   ├── css/style.css
│   └── js/app.js
└── models/             # Auto-downloaded at runtime (git-ignored)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| ML Models | scikit-learn, TensorFlow/Keras |
| PDF Reports | fpdf2 |
| AI Chatbot | Google Gemini (google-genai) |
| Frontend | Vanilla JS, CSS Glassmorphism |
| Hosting | Vercel |

---

## ⚠️ Disclaimer

This system is for **AI-assisted screening only** and does **not** constitute a medical diagnosis. Always consult a qualified healthcare professional before making any medical decisions.

---

## 👥 Team

| Name | Role |
|---|---|
| Manohar | Project Lead |
| Miduna Virshni | Tech Lead |
| Keerthi Vaasan | Tech Lead |

**Supported by RAHONAM** ⚡
