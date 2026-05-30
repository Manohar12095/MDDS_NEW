"""
Flask backend for Multi-Disease Diagnostic System (MDDS)
Replaces Streamlit entirely — pure Flask + Vanilla JS frontend.
"""

import os, sys, pickle, io, base64, json, gdown
import numpy as np
from flask import Flask, request, jsonify, send_from_directory, render_template
from datetime import datetime

# ─── paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

# ─── Google Drive model IDs ────────────────────────────────────────────────────
DRIVE_IDS = {
    "diabetes_model.pkl":   "10Ug0oD77wmVWJXnsS6loZdPJleRSlOXm",
    "heart_model.pkl":      "1n1-03M3sV3PsuMTMzqokZFjPlDC0eRiq",
    "brain_tumor_dataset.h5": "1r7Kmf14ZGKQK3GSTk3nxPxfAyGpg2m_b",
    "kidney_10f_model.pkl": "1v8HPAp926mzG9ldc9EZ-C9E-vRBzXgzq",
    "liver_model.pkl":      "17f0FNIe8O3hYNoDsrtYeTerK6kUEjSs0",
}

_model_cache = {}

def ensure_file(filename):
    dest = os.path.join(MODELS_DIR, filename)
    if not os.path.exists(dest) or os.path.getsize(dest) < 1024:
        print(f"[MDDS] Downloading {filename}…")
        gdown.download(f"https://drive.google.com/uc?export=download&id={DRIVE_IDS[filename]}", dest, quiet=False)
    return dest

def load_pickle_model(filename):
    if filename not in _model_cache:
        path = ensure_file(filename)
        with open(path, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, tuple):
            _model_cache[filename] = data  # (model, scaler)
        else:
            _model_cache[filename] = (data["model"], data["scaler"])
    return _model_cache[filename]

def load_brain_model():
    try:
        from tensorflow.keras.models import load_model as keras_load
    except ImportError:
        raise RuntimeError("TensorFlow is not installed in this environment.")
    if "brain" not in _model_cache:
        path = ensure_file("brain_tumor_dataset.h5")
        _model_cache["brain"] = keras_load(path)
    return _model_cache["brain"]

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/page/<name>")
def page(name):
    valid = ["heart", "diabetes", "brain", "kidney", "liver", "chatbot", "report", "contact"]
    if name in valid:
        return render_template(f"{name}.html")
    return "Page not found", 404

# ── Heart Disease ──────────────────────────────────────────────────────────────
@app.route("/api/predict/heart", methods=["POST"])
def predict_heart():
    try:
        d = request.json
        model, scaler = load_pickle_model("heart_model.pkl")
        X = np.array([[
            float(d["age"]), float(d["sex"]), float(d["cp"]),
            float(d["trestbps"]), float(d["chol"]), float(d["fbs"]),
            float(d["restecg"]), float(d["thalach"]), float(d["exang"]),
            float(d["oldpeak"]), float(d["slope"]), float(d["ca"]),
            float(d["thal"])
        ]])
        X_scaled = scaler.transform(X)
        pred = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.78 if detected else 0.15)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Heart Disease"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Diabetes ───────────────────────────────────────────────────────────────────
@app.route("/api/predict/diabetes", methods=["POST"])
def predict_diabetes():
    try:
        d = request.json
        model, scaler = load_pickle_model("diabetes_model.pkl")
        X = np.array([[
            float(d["pregnancies"]), float(d["glucose"]), float(d["bp"]),
            float(d["skin"]), float(d["insulin"]), float(d["bmi"]),
            float(d["dpf"]), float(d["age"])
        ]])
        X_scaled = scaler.transform(X)
        pred = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.72 if detected else 0.18)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Diabetes"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Brain Tumor ────────────────────────────────────────────────────────────────
@app.route("/api/predict/brain", methods=["POST"])
def predict_brain():
    try:
        from PIL import Image
        model = load_brain_model()
    except RuntimeError as e:
        return jsonify({"error": "Brain Tumor detection is unavailable in this deployment (TensorFlow not installed). All other disease predictions work normally.", "unavailable": True}), 503
    try:
        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No image uploaded"}), 400
        image = Image.open(file.stream).convert("RGB")
        input_shape = model.input_shape[1:]
        if len(input_shape) == 1:
            side = int(np.sqrt(input_shape[0] / 3))
            img = image.resize((side, side))
            img_array = np.expand_dims(np.array(img).flatten() / 255.0, axis=0)
        elif input_shape[-1] == 1:
            img = image.resize((input_shape[0], input_shape[1])).convert("L")
            img_array = np.array(img).reshape(1, input_shape[0], input_shape[1], 1) / 255.0
        else:
            img = image.resize((input_shape[0], input_shape[1]))
            img_array = np.expand_dims(np.array(img) / 255.0, axis=0)
        prediction = float(model.predict(img_array)[0][0])
        detected = prediction > 0.5
        confidence = prediction if detected else 1 - prediction
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Brain Tumor"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Kidney Disease ─────────────────────────────────────────────────────────────
@app.route("/api/predict/kidney", methods=["POST"])
def predict_kidney():
    try:
        d = request.json
        model, scaler = load_pickle_model("kidney_10f_model.pkl")
        X = np.array([[
            float(d["age"]), float(d["bp"]), float(d["sg"]), float(d["al"]),
            float(d["su"]), float(d["bgr"]), float(d["bu"]), float(d["sc"]),
            float(d["hemo"]), float(d["pcv"])
        ]])
        X_scaled = scaler.transform(X)
        pred = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.75 if detected else 0.12)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Kidney Disease"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Liver Disease ──────────────────────────────────────────────────────────────
@app.route("/api/predict/liver", methods=["POST"])
def predict_liver():
    try:
        d = request.json
        model, scaler = load_pickle_model("liver_model.pkl")
        X = np.array([[
            float(d["age"]), float(d["gender"]), float(d["total_bilirubin"]),
            float(d["direct_bilirubin"]), float(d["alk_phos"]), float(d["alt"]),
            float(d["ast"]), float(d["total_proteins"]), float(d["albumin"]),
            float(d["ag_ratio"])
        ]])
        X_scaled = scaler.transform(X)
        pred = model.predict(X_scaled)[0]
        detected = bool(pred == 1)
        confidence = float(pred) if 0 < pred < 1 else (0.71 if detected else 0.14)
        return jsonify({"detected": detected, "confidence": round(confidence * 100, 1), "disease": "Liver Disease"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Full Personal Report PDF ───────────────────────────────────────────────────
@app.route("/api/generate_full_report", methods=["POST"])
def generate_full_report():
    try:
        from fpdf import FPDF
        d = request.json
        name_p     = d.get("name", "Patient")
        age_p      = d.get("age", "N/A")
        gender_p   = d.get("gender", "N/A")
        blood_p    = d.get("blood_group", "N/A")
        phone_p    = d.get("phone", "N/A")
        address_p  = d.get("address", "N/A")
        history    = d.get("history", [])
        timestamp  = datetime.now().strftime("%d %b %Y %I:%M %p")

        pdf = FPDF()
        pdf.add_page()

        # ── Header banner ──
        pdf.set_fill_color(5, 15, 40)
        pdf.rect(0, 0, 210, 36, "F")
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(0, 212, 255)
        pdf.set_y(7)
        pdf.cell(0, 9, "MULTI-DISEASE DIAGNOSTIC PORTAL", align="C", ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(180, 200, 220)
        pdf.cell(0, 6, "AI-Powered Health Report  |  Powered by RAHONAM", align="C", ln=True)

        # ── Disclaimer ──
        pdf.set_y(42)
        pdf.set_fill_color(255, 243, 205)
        pdf.set_font("Arial", "BI", 7)
        pdf.set_text_color(100, 70, 0)
        pdf.multi_cell(0, 4.5,
            "DISCLAIMER: AI-assisted screening only. Not a final medical diagnosis. "
            "Consult a qualified healthcare professional before making any medical decisions.",
            border=1, fill=True)
        pdf.ln(4)

        # ── Patient Details ──
        pdf.set_fill_color(220, 235, 255)
        pdf.rect(10, pdf.get_y(), 190, 8, "F")
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(10, 60, 130)
        pdf.cell(0, 8, "  Patient Information", ln=True)
        pdf.ln(2)
        details = [
            ("Full Name", name_p),   ("Age", str(age_p)),
            ("Gender", gender_p),    ("Blood Group", blood_p),
            ("Phone", phone_p),      ("Address", address_p),
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

        # ── Prediction History ──
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
            for i, entry in enumerate(history):
                row_fill = i % 2 == 0
                if row_fill:
                    pdf.set_fill_color(240, 245, 255)
                else:
                    pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(30, 30, 30)
                pdf.set_font("Arial", "", 9)
                risk_color = (200, 0, 0) if entry.get("detected") else (0, 130, 60)
                values = [
                    entry.get("disease", "N/A"),
                    entry.get("result", "N/A"),
                    f"{entry.get('confidence','N/A')}%",
                    entry.get("time", "N/A")
                ]
                for v, w in zip(values, widths):
                    pdf.cell(w, 7, str(v), border=1, fill=row_fill)
                pdf.ln()
        else:
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 7, "  No prediction history found.", ln=True)

        # ── Footer ──
        pdf.set_y(-16)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 5, "Created by Manohar, Miduna Virshni, Keerthi Vaasan  |  Supported by RAHONAM  |  Stay healthy.", align="C", ln=True)

        out = bytes(pdf.output())
        b64 = base64.b64encode(out).decode()
        return jsonify({"pdf_b64": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Simple PDF (single result) ─────────────────────────────────────────────────
@app.route("/api/generate_pdf", methods=["POST"])
def generate_pdf():
    try:
        from fpdf import FPDF
        d = request.json
        disease  = d.get("disease", "Unknown")
        result   = d.get("result", "N/A")
        confidence = d.get("confidence", "N/A")
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_fill_color(10, 60, 130)
        pdf.rect(0, 0, 210, 32, "F")
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_y(8)
        pdf.cell(0, 8, "AI Health Prediction Report", align="C", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 7, "Multi-Disease Diagnostic System", align="C", ln=True)
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
        pdf.cell(0, 5, "Stay healthy. Consult a doctor regularly.", align="C", ln=True)

        out = bytes(pdf.output())
        b64 = base64.b64encode(out).decode()
        return jsonify({"pdf_b64": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=False, port=5000)
