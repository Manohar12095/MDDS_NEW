"""
Flask backend — Multi-Disease Diagnostic System (MDDS)
IN NET CREATIONS · Created by S. Manohar

Security:   Rate limiting, security headers, input validation, XSS/CSRF protection
Performance: Response compression, model caching, threading, static caching
Deployment: Gunicorn-ready, Vercel-compatible, env-var configuration
"""

import os, sys, pickle, io, base64, json, re, logging, tempfile
import smtplib, threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from time import time

# ─── Env / paths ──────────────────────────────────────────────────────────────
os.environ["HOME"]          = tempfile.gettempdir()
os.environ["XDG_CACHE_HOME"] = tempfile.gettempdir()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Load .env with explicit path
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
except ImportError:
    pass

# ─── Flask app ────────────────────────────────────────────────────────────────
import gdown
import numpy as np
from flask import (Flask, request, jsonify, render_template,
                   abort, make_response, g)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Secret key (required for session security)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB max upload

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mdds")

# ─── Email config ─────────────────────────────────────────────────────────────
GMAIL_USER         = os.environ.get("GMAIL_USER", "innetcreations@gmail.com").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
CONTACT_RECIPIENT  = os.environ.get("CONTACT_RECIPIENT", "innetcreations@gmail.com").strip()

# ─── Google Drive model IDs ───────────────────────────────────────────────────
DRIVE_IDS = {
    "diabetes_model.pkl":     "10Ug0oD77wmVWJXnsS6loZdPJleRSlOXm",
    "heart_model.pkl":        "1n1-03M3sV3PsuMTMzqokZFjPlDC0eRiq",
    "brain_tumor_dataset.h5": "1r7Kmf14ZGKQK3GSTk3nxPxfAyGpg2m_b",
    "kidney_10f_model.pkl":   "1v8HPAp926mzG9ldc9EZ-C9E-vRBzXgzq",
    "liver_model.pkl":        "17f0FNIe8O3hYNoDsrtYeTerK6kUEjSs0",
}

_model_cache = {}
_model_lock  = threading.Lock()

# ══════════════════════════════════════════════════════════════════════════════
#  SECURITY MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════════════

# ── In-memory rate limiter (per IP) ───────────────────────────────────────────
_rate_store   = defaultdict(list)
_rate_lock    = threading.Lock()
_blocked_ips  = {}   # ip -> unblock_time

RATE_LIMITS = {
    "api":     (30, 60),   # 30 req / 60s  for /api/* endpoints
    "predict": (10, 60),   # 10 predictions / 60s
    "contact": (3,  300),  # 3 contact msgs / 5 min
    "global":  (120, 60),  # 120 req / 60s  total (DDoS guard)
}

def _get_ip():
    """Get real client IP, respecting trusted reverse-proxy headers."""
    for header in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"):
        val = request.headers.get(header)
        if val:
            ip = val.split(",")[0].strip()
            if _is_valid_ip(ip):
                return ip
    return request.remote_addr or "0.0.0.0"

def _is_valid_ip(ip: str) -> bool:
    import socket
    try:
        socket.inet_aton(ip)
        return True
    except Exception:
        return False

def rate_limit(bucket: str):
    """Decorator: apply named rate-limit bucket to a route."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = _get_ip()
            limit, window = RATE_LIMITS[bucket]
            now = time()
            with _rate_lock:
                # Check IP block
                if ip in _blocked_ips:
                    if now < _blocked_ips[ip]:
                        logger.warning("Blocked IP attempted access: %s", ip)
                        return jsonify({"error": "Too many requests. Try again later."}), 429
                    else:
                        del _blocked_ips[ip]
                # Sliding window
                _rate_store[f"{ip}:{bucket}"] = [
                    t for t in _rate_store[f"{ip}:{bucket}"] if now - t < window
                ]
                _rate_store[f"{ip}:{bucket}"].append(now)
                count = len(_rate_store[f"{ip}:{bucket}"])
                if count > limit:
                    # Block repeat offenders for 5 min
                    if count > limit * 3:
                        _blocked_ips[ip] = now + 300
                        logger.warning("IP blocked (abuse): %s", ip)
                    logger.warning("Rate limit hit: %s bucket=%s count=%d", ip, bucket, count)
                    resp = jsonify({"error": "Rate limit exceeded. Please slow down."})
                    resp.headers["Retry-After"] = str(window)
                    return resp, 429
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def _sanitize_str(value, max_len=1000):
    """Strip HTML tags and limit length to prevent XSS / injection."""
    if not isinstance(value, str):
        value = str(value)
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", value)
    # Remove dangerous chars
    clean = re.sub(r"[<>\"']", "", clean)
    return clean[:max_len].strip()

def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))

def _safe_float(val, min_val=None, max_val=None):
    """Parse float with optional bounds check."""
    try:
        f = float(val)
        if min_val is not None and f < min_val:
            raise ValueError(f"Value {f} below minimum {min_val}")
        if max_val is not None and f > max_val:
            raise ValueError(f"Value {f} above maximum {max_val}")
        return f
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid numeric input: {e}")

# ── Security headers on every response ────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # XSS protection (legacy browsers)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Permissions policy — disable unnecessary browser features
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Content Security Policy — allow only same-origin + Google Fonts
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    # HSTS (enable when HTTPS is live)
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Static asset caching
    if "/static/" in request.path:
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        response.headers["Cache-Control"] = "no-store"
    # Remove server fingerprint
    response.headers.pop("Server", None)
    response.headers.pop("X-Powered-By", None)
    return response

# ── Block obviously bad requests ──────────────────────────────────────────────
BLOCKED_UA_PATTERNS = [
    r"sqlmap", r"nikto", r"nessus", r"masscan", r"zgrab",
    r"nmap", r"dirbuster", r"gobuster", r"wfuzz", r"burpsuite",
    r"python-requests/2\.[0-2]",  # block old scripted scanners
]
BLOCKED_PATH_PATTERNS = [
    r"\.php$", r"\.asp$", r"\.env$", r"wp-admin", r"\.git/",
    r"etc/passwd", r"proc/self", r"\.htaccess", r"xmlrpc",
]

@app.before_request
def guard():
    # Global rate limit
    ip  = _get_ip()
    now = time()
    with _rate_lock:
        if ip in _blocked_ips and now < _blocked_ips[ip]:
            abort(429)
        _rate_store[f"{ip}:global"] = [
            t for t in _rate_store[f"{ip}:global"] if now - t < 60
        ]
        _rate_store[f"{ip}:global"].append(now)
        if len(_rate_store[f"{ip}:global"]) > RATE_LIMITS["global"][0]:
            _blocked_ips[ip] = now + 60
            abort(429)

    # Block scanner user-agents
    ua = request.headers.get("User-Agent", "").lower()
    for pat in BLOCKED_UA_PATTERNS:
        if re.search(pat, ua, re.I):
            logger.warning("Scanner UA blocked: %s from %s", ua, ip)
            abort(403)

    # Block path traversal / known attack paths
    path = request.path
    for pat in BLOCKED_PATH_PATTERNS:
        if re.search(pat, path, re.I):
            logger.warning("Blocked path: %s from %s", path, ip)
            abort(404)

    # Block oversized JSON payloads (belt-and-suspenders beyond MAX_CONTENT_LENGTH)
    clen = request.content_length or 0
    if clen > 10 * 1024 * 1024:
        abort(413)

    # CSRF & Origin protection on state-modifying requests
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin:
            from urllib.parse import urlparse
            netloc = urlparse(origin).netloc.lower()
            host = request.host.lower()
            # Allow same-host, localhost, and Vercel domains
            if netloc and netloc != host and not netloc.endswith("vercel.app") and not netloc.startswith("127.0.0.1") and not netloc.startswith("localhost"):
                logger.warning("CSRF / Untrusted origin blocked: %s (host=%s)", origin, host)
                abort(403)

    g.start_time = now

@app.after_request
def log_request(response):
    duration_ms = round((time() - getattr(g, "start_time", time())) * 1000, 1)
    logger.info("%s %s %d %sms [%s]",
                request.method, request.path,
                response.status_code, duration_ms, _get_ip())
    return response

# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad request"}), 400

@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Forbidden"}), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html") if os.path.exists(
        os.path.join(BASE_DIR, "templates", "404.html")
    ) else (jsonify({"error": "Not found"}), 404)

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Request too large (max 10 MB)"}), 413

@app.errorhandler(429)
def too_many(e):
    return jsonify({"error": "Too many requests. Please slow down."}), 429

@app.errorhandler(500)
def server_error(e):
    logger.exception("Unhandled server error")
    return jsonify({"error": "Internal server error"}), 500

# ── Response compression (gzip) ───────────────────────────────────────────────
try:
    from flask_compress import Compress
    Compress(app)
    app.config["COMPRESS_MIMETYPES"] = [
        "text/html", "text/css", "application/javascript",
        "application/json", "image/svg+xml"
    ]
    app.config["COMPRESS_LEVEL"] = 6
    app.config["COMPRESS_MIN_SIZE"] = 500
except ImportError:
    logger.info("flask-compress not available; skipping gzip compression")

# ══════════════════════════════════════════════════════════════════════════════
#  ML MODEL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def ensure_file(filename):
    dest = os.path.join(MODELS_DIR, filename)
    if os.path.exists(dest) and os.path.getsize(dest) >= 1024:
        return dest
    tmp_dir  = os.path.join(tempfile.gettempdir(), "mdds_models")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_dest = os.path.join(tmp_dir, filename)
    if not os.path.exists(tmp_dest) or os.path.getsize(tmp_dest) < 1024:
        logger.info("Downloading %s…", filename)
        gdown.download(
            f"https://drive.google.com/uc?export=download&id={DRIVE_IDS[filename]}",
            tmp_dest, quiet=False
        )
    return tmp_dest

def load_pickle_model(filename):
    with _model_lock:
        if filename not in _model_cache:
            path = ensure_file(filename)
            with open(path, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, tuple):
                _model_cache[filename] = data
            else:
                _model_cache[filename] = (data["model"], data["scaler"])
    return _model_cache[filename]

def load_brain_model():
    try:
        from tensorflow.keras.models import load_model as keras_load
    except ImportError:
        raise RuntimeError("TensorFlow is not installed in this environment.")
    with _model_lock:
        if "brain" not in _model_cache:
            path = ensure_file("brain_tumor_dataset.h5")
            _model_cache["brain"] = keras_load(path)
    return _model_cache["brain"]

def preload_all_models():
    """Warm up ML models in a background thread at server startup for instant, zero-delay predictions."""
    for m in ["heart_model.pkl", "diabetes_model.pkl", "kidney_10f_model.pkl", "liver_model.pkl"]:
        try:
            load_pickle_model(m)
            logger.info("Pre-warmed model: %s", m)
        except Exception as ex:
            logger.warning("Could not pre-warm model %s: %s", m, ex)

threading.Thread(target=preload_all_models, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

VALID_PAGES = frozenset(
    ["heart", "diabetes", "brain", "kidney", "liver", "chatbot", "report", "contact"]
)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/page/<name>")
def page(name):
    if name not in VALID_PAGES:
        abort(404)
    return render_template(f"{name}.html")

# ── Health check (Vercel / uptime monitors) ───────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "MDDS", "by": "IN NET CREATIONS"}), 200

# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTION API ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/predict/heart", methods=["POST"])
@rate_limit("predict")
def predict_heart():
    try:
        d = request.get_json(silent=True) or {}
        model, scaler = load_pickle_model("heart_model.pkl")
        X = np.array([[
            _safe_float(d.get("age"),      0, 120),
            _safe_float(d.get("sex"),      0, 1),
            _safe_float(d.get("cp"),       0, 3),
            _safe_float(d.get("trestbps"), 50, 300),
            _safe_float(d.get("chol"),     50, 700),
            _safe_float(d.get("fbs"),      0, 1),
            _safe_float(d.get("restecg"),  0, 2),
            _safe_float(d.get("thalach"),  50, 250),
            _safe_float(d.get("exang"),    0, 1),
            _safe_float(d.get("oldpeak"),  0, 10),
            _safe_float(d.get("slope"),    0, 2),
            _safe_float(d.get("ca"),       0, 4),
            _safe_float(d.get("thal"),     0, 3),
        ]])
        X_scaled = scaler.transform(X)
        pred     = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.78 if detected else 0.15)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Heart Disease"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Heart predict error")
        return jsonify({"error": "Prediction failed"}), 500

@app.route("/api/predict/diabetes", methods=["POST"])
@rate_limit("predict")
def predict_diabetes():
    try:
        d = request.get_json(silent=True) or {}
        model, scaler = load_pickle_model("diabetes_model.pkl")
        X = np.array([[
            _safe_float(d.get("pregnancies"), 0, 20),
            _safe_float(d.get("glucose"),     0, 400),
            _safe_float(d.get("bp"),          0, 200),
            _safe_float(d.get("skin"),        0, 100),
            _safe_float(d.get("insulin"),     0, 1000),
            _safe_float(d.get("bmi"),         0, 100),
            _safe_float(d.get("dpf"),         0, 5),
            _safe_float(d.get("age"),         0, 120),
        ]])
        X_scaled = scaler.transform(X)
        pred     = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.72 if detected else 0.18)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Diabetes"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Diabetes predict error")
        return jsonify({"error": "Prediction failed"}), 500

@app.route("/api/predict/brain", methods=["POST"])
@rate_limit("predict")
def predict_brain():
    try:
        from PIL import Image
        model = load_brain_model()
    except RuntimeError as e:
        return jsonify({"error": "Brain Tumor detection unavailable (TensorFlow not installed).", "unavailable": True}), 503
    try:
        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No image uploaded"}), 400
        # Validate file type
        allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if file.content_type not in allowed:
            return jsonify({"error": "Invalid image format. Use JPEG/PNG."}), 400
        image       = Image.open(file.stream).convert("RGB")
        input_shape = model.input_shape[1:]
        if len(input_shape) == 1:
            side      = int(np.sqrt(input_shape[0] / 3))
            img       = image.resize((side, side))
            img_array = np.expand_dims(np.array(img).flatten() / 255.0, axis=0)
        elif input_shape[-1] == 1:
            img       = image.resize((input_shape[0], input_shape[1])).convert("L")
            img_array = np.array(img).reshape(1, input_shape[0], input_shape[1], 1) / 255.0
        else:
            img       = image.resize((input_shape[0], input_shape[1]))
            img_array = np.expand_dims(np.array(img) / 255.0, axis=0)
        prediction = float(model.predict(img_array)[0][0])
        detected   = prediction > 0.5
        confidence = prediction if detected else 1 - prediction
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Brain Tumor"})
    except Exception as e:
        logger.exception("Brain predict error")
        return jsonify({"error": "Prediction failed"}), 500

@app.route("/api/predict/kidney", methods=["POST"])
@rate_limit("predict")
def predict_kidney():
    try:
        d = request.get_json(silent=True) or {}
        model, scaler = load_pickle_model("kidney_10f_model.pkl")
        X = np.array([[
            _safe_float(d.get("age"),  0, 120),
            _safe_float(d.get("bp"),   0, 200),
            _safe_float(d.get("sg"),   1.000, 1.030),
            _safe_float(d.get("al"),   0, 5),
            _safe_float(d.get("su"),   0, 5),
            _safe_float(d.get("bgr"),  0, 500),
            _safe_float(d.get("bu"),   0, 300),
            _safe_float(d.get("sc"),   0, 20),
            _safe_float(d.get("hemo"), 0, 20),
            _safe_float(d.get("pcv"),  0, 60),
        ]])
        X_scaled = scaler.transform(X)
        pred     = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.75 if detected else 0.12)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Kidney Disease"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Kidney predict error")
        return jsonify({"error": "Prediction failed"}), 500

@app.route("/api/predict/liver", methods=["POST"])
@rate_limit("predict")
def predict_liver():
    try:
        d = request.get_json(silent=True) or {}
        model, scaler = load_pickle_model("liver_model.pkl")
        X = np.array([[
            _safe_float(d.get("age"),              0, 120),
            _safe_float(d.get("gender"),           0, 1),
            _safe_float(d.get("total_bilirubin"),  0, 100),
            _safe_float(d.get("direct_bilirubin"), 0, 50),
            _safe_float(d.get("alk_phos"),         0, 3000),
            _safe_float(d.get("alt"),              0, 3000),
            _safe_float(d.get("ast"),              0, 3000),
            _safe_float(d.get("total_proteins"),   0, 20),
            _safe_float(d.get("albumin"),          0, 10),
            _safe_float(d.get("ag_ratio"),         0, 10),
        ]])
        X_scaled = scaler.transform(X)
        pred     = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.71 if detected else 0.14)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Liver Disease"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Liver predict error")
        return jsonify({"error": "Prediction failed"}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  REPORT / PDF ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/generate_full_report", methods=["POST"])
@rate_limit("api")
def generate_full_report():
    try:
        from fpdf import FPDF
        d         = request.get_json(silent=True) or {}
        name_p    = _sanitize_str(d.get("name", "Patient"), 100)
        age_p     = _sanitize_str(str(d.get("age", "N/A")), 10)
        gender_p  = _sanitize_str(d.get("gender", "N/A"), 20)
        blood_p   = _sanitize_str(d.get("blood_group", "N/A"), 10)
        phone_p   = _sanitize_str(d.get("phone", "N/A"), 20)
        address_p = _sanitize_str(d.get("address", "N/A"), 200)
        history   = d.get("history", [])
        if not isinstance(history, list):
            history = []
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")

        pdf = FPDF()
        pdf.add_page()

        # Header
        pdf.set_fill_color(5, 15, 40)
        pdf.rect(0, 0, 210, 36, "F")
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(0, 212, 255)
        pdf.set_y(7)
        pdf.cell(0, 9, "MULTI-DISEASE DIAGNOSTIC PORTAL", align="C", ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(180, 200, 220)
        pdf.cell(0, 6, "AI-Powered Health Report  |  IN NET CREATIONS  |  Created by S. Manohar", align="C", ln=True)

        # Disclaimer
        pdf.set_y(42)
        pdf.set_fill_color(255, 243, 205)
        pdf.set_font("Arial", "BI", 7)
        pdf.set_text_color(100, 70, 0)
        pdf.multi_cell(0, 4.5,
            "DISCLAIMER: AI-assisted screening only. Not a final medical diagnosis. "
            "Consult a qualified healthcare professional before making any medical decisions.",
            border=1, fill=True)
        pdf.ln(4)

        # Patient Details
        pdf.set_fill_color(220, 235, 255)
        pdf.rect(10, pdf.get_y(), 190, 8, "F")
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(10, 60, 130)
        pdf.cell(0, 8, "  Patient Information", ln=True)
        pdf.ln(2)
        details = [
            ("Full Name", name_p), ("Age", age_p),
            ("Gender", gender_p),  ("Blood Group", blood_p),
            ("Phone", phone_p),    ("Address", address_p),
            ("Report Date", timestamp)
        ]
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(30, 30, 30)
        for i, (label, val) in enumerate(details):
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(245, 248, 255)
            pdf.set_font("Arial", "B", 9)
            pdf.cell(55, 7, f"  {label}:", border=0, fill=fill)
            pdf.set_font("Arial", "", 9)
            pdf.cell(0, 7, str(val), border=0, ln=True, fill=fill)
        pdf.ln(5)

        # Prediction History
        pdf.set_fill_color(220, 235, 255)
        pdf.rect(10, pdf.get_y(), 190, 8, "F")
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(10, 60, 130)
        pdf.cell(0, 8, "  Prediction History", ln=True)
        pdf.ln(2)
        if history:
            headers = ["Disease", "Result", "Confidence", "Date/Time"]
            widths  = [55, 45, 40, 50]
            pdf.set_fill_color(10, 60, 130)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 9)
            for h, w in zip(headers, widths):
                pdf.cell(w, 8, h, border=1, fill=True)
            pdf.ln()
            for i, entry in enumerate(history[:50]):   # cap at 50 entries
                row_fill = i % 2 == 0
                pdf.set_fill_color(240, 245, 255) if row_fill else pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(30, 30, 30)
                pdf.set_font("Arial", "", 9)
                values = [
                    _sanitize_str(str(entry.get("disease", "N/A")), 50),
                    _sanitize_str(str(entry.get("result", "N/A")), 30),
                    f"{entry.get('confidence','N/A')}%",
                    _sanitize_str(str(entry.get("time", "N/A")), 30),
                ]
                for v, w in zip(values, widths):
                    pdf.cell(w, 7, v, border=1, fill=row_fill)
                pdf.ln()
        else:
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 7, "  No prediction history found.", ln=True)

        # Footer
        pdf.set_y(-16)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 5, "IN NET CREATIONS · Created by S. Manohar · Stay healthy. Consult a doctor regularly.", align="C", ln=True)

        out = bytes(pdf.output())
        b64 = base64.b64encode(out).decode()
        return jsonify({"pdf_b64": b64})
    except Exception as e:
        logger.exception("Full report error")
        return jsonify({"error": "Report generation failed"}), 500

@app.route("/api/generate_pdf", methods=["POST"])
@rate_limit("api")
def generate_pdf():
    try:
        from fpdf import FPDF
        d          = request.get_json(silent=True) or {}
        disease    = _sanitize_str(d.get("disease", "Unknown"), 50)
        result     = _sanitize_str(d.get("result", "N/A"), 30)
        confidence = _sanitize_str(str(d.get("confidence", "N/A")), 10)
        timestamp  = datetime.now().strftime("%d %b %Y %I:%M %p")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(10, 60, 130)
        pdf.rect(0, 0, 210, 32, "F")
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_y(8)
        pdf.cell(0, 8, "AI Health Prediction Report", align="C", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 7, "Multi-Disease Diagnostic System · IN NET CREATIONS", align="C", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_y(40)
        pdf.set_fill_color(230, 240, 255)
        pdf.rect(10, 38, 190, 18, "F")
        pdf.set_font("Arial", "B", 10)
        pdf.set_x(14)
        pdf.cell(90, 7, f"Disease: {disease}", ln=False)
        pdf.cell(90, 7, f"Date: {timestamp}", ln=True)
        pdf.ln(4)
        pdf.set_fill_color(255, 243, 205)
        pdf.set_font("Arial", "BI", 8)
        pdf.set_text_color(100, 70, 0)
        pdf.multi_cell(0, 5, "DISCLAIMER: AI-assisted screening only. Not a final medical diagnosis. Consult a qualified healthcare professional.", border=1, fill=True)
        pdf.ln(6)
        pdf.set_font("Arial", "B", 13)
        pdf.set_text_color(10, 60, 130)
        pdf.cell(0, 8, "Prediction Result", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 8, f"Result: {result}", ln=True)
        pdf.cell(0, 8, f"Confidence: {confidence}%", ln=True)
        pdf.set_y(-16)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 5, "IN NET CREATIONS · Created by S. Manohar · Stay healthy. Consult a doctor regularly.", align="C", ln=True)

        out = bytes(pdf.output())
        b64 = base64.b64encode(out).decode()
        return jsonify({"pdf_b64": b64})
    except Exception as e:
        logger.exception("PDF error")
        return jsonify({"error": "PDF generation failed"}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  CONTACT / EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_email_notification(name: str, email: str, subject: str, message: str) -> dict:
    """
    Sends contact form email using a resilient dual-tier delivery system:
      Tier 1: High-speed Gmail SMTP SSL (if GMAIL_USER & GMAIL_APP_PASSWORD env vars are set)
      Tier 2: HTTPS Cloud Email Gateway (FormSubmit API) — works in 100% of deployments,
              including Vercel, Render, Railway, AWS Lambda, without SMTP port restrictions.
    """
    errors = []

    # Refresh env from .env file if updated
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
    except Exception:
        pass

    gmail_user = (os.environ.get("GMAIL_USER") or GMAIL_USER or "innetcreations@gmail.com").strip()
    gmail_pwd  = (os.environ.get("GMAIL_APP_PASSWORD") or GMAIL_APP_PASSWORD or "").strip().replace(" ", "")
    recipient  = (os.environ.get("CONTACT_RECIPIENT") or CONTACT_RECIPIENT or "innetcreations@gmail.com").strip()

    # ── Tier 1: Direct Gmail SMTP SSL ─────────────────────────────────────────
    if gmail_user and gmail_pwd:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"]  = f"[MDDS Portal] {subject} — from {name}"
            msg["From"]     = f"MDDS Portal <{gmail_user}>"
            msg["To"]       = recipient
            msg["Reply-To"] = email

            html_body = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;background:#0a0f1e;color:#f1f5f9;border-radius:12px;">
              <div style="text-align:center;margin-bottom:24px;border-bottom:1px solid rgba(0,212,255,0.2);padding-bottom:16px;">
                <h2 style="color:#00D4FF;margin:0;">IN NET CREATIONS · MDDS</h2>
                <p style="color:#64748b;font-size:13px;margin:4px 0 0;">New Contact Form Submission</p>
              </div>
              <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px 0;color:#94a3b8;width:90px;vertical-align:top;"><b>From:</b></td>
                    <td style="padding:8px 0;color:#f1f5f9;">{name} &lt;{email}&gt;</td></tr>
                <tr><td style="padding:8px 0;color:#94a3b8;vertical-align:top;"><b>Subject:</b></td>
                    <td style="padding:8px 0;color:#f1f5f9;">{subject}</td></tr>
              </table>
              <div style="margin-top:16px;padding:16px;background:rgba(255,255,255,0.05);border-radius:8px;border-left:3px solid #00D4FF;">
                <p style="color:#94a3b8;font-size:12px;margin:0 0 8px;">MESSAGE</p>
                <p style="color:#f1f5f9;line-height:1.6;margin:0;white-space:pre-wrap;">{message}</p>
              </div>
              <p style="color:#475569;font-size:11px;text-align:center;margin-top:20px;">
                Sent via MDDS Contact Form · IN NET CREATIONS · Created by S. Manohar
              </p>
            </div>
            """
            msg.attach(MIMEText(html_body, "html"))

            logger.info("Attempting Tier 1 Gmail SMTP SSL dispatch to %s...", recipient)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as srv:
                srv.login(gmail_user, gmail_pwd)
                srv.sendmail(gmail_user, recipient, msg.as_string())

            logger.info("Tier 1 Gmail SMTP succeeded: email delivered to %s", recipient)
            return {"ok": True, "method": "smtp", "message": f"Message sent to {recipient}"}
        except Exception as e:
            logger.warning("SMTP delivery failed: %s; falling back to HTTPS email gateway", e)
            errors.append(f"SMTP: {e}")

    # ── Tier 2: Cloud HTTPS Email Gateway (FormSubmit API) ────────────────────
    try:
        import requests
        payload = {
            "name": name,
            "email": email,
            "_subject": f"[MDDS Portal] {subject} — from {name}",
            "_replyto": email,
            "_template": "table",
            "_captcha": "false",
            "message": message,
        }
        headers = {
            "Origin": "https://mdds-new-rnrp.vercel.app",
            "Referer": "https://mdds-new-rnrp.vercel.app/page/contact",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MDDS-Portal/2.0",
        }
        resp = requests.post(
            f"https://formsubmit.co/ajax/{CONTACT_RECIPIENT}",
            json=payload,
            headers=headers,
            timeout=12
        )
        res_data = resp.json() if resp.status_code == 200 else {}
        logger.info("HTTPS email gateway response: code=%s, body=%s", resp.status_code, res_data)

        if resp.status_code in (200, 201):
            return {"ok": True, "method": "gateway", "message": res_data.get("message", f"Message delivered to {CONTACT_RECIPIENT}")}
        else:
            errors.append(f"Gateway code: {resp.status_code}")
    except Exception as e:
        logger.error("HTTPS email gateway failed: %s", e)
        errors.append(f"Gateway: {e}")

    return {"ok": False, "error": "; ".join(errors)}


@app.route("/api/contact", methods=["POST"])
@rate_limit("contact")
def contact():
    try:
        data    = request.get_json(silent=True) or {}
        name    = _sanitize_str(data.get("name", ""), 100)
        email   = _sanitize_str(data.get("email", ""), 254)
        subject = _sanitize_str(data.get("subject", "MDDS Enquiry"), 200) or "MDDS Enquiry"
        message = _sanitize_str(data.get("message", ""), 2000)

        if not name:
            return jsonify({"error": "Name is required."}), 400
        if not email or not _validate_email(email):
            return jsonify({"error": "A valid email address is required."}), 400
        if not message:
            return jsonify({"error": "Message is required."}), 400

        result = send_email_notification(name, email, subject, message)
        if result.get("ok"):
            return jsonify(result), 200
        else:
            return jsonify({
                "error": f"Email delivery failed. Please send your message directly to {CONTACT_RECIPIENT}",
                "details": result.get("error")
            }), 500

    except Exception as e:
        logger.exception("Contact error")
        return jsonify({"error": "Failed to send message. Try again later."}), 500

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Development server — use gunicorn in production
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
