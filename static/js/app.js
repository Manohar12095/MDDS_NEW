// ── Shared JS utilities ───────────────────────────────────────────────────────

// Range slider live value display
document.querySelectorAll('input[type="range"]').forEach(slider => {
  const display = document.getElementById(slider.id + '_val');
  if (display) display.textContent = slider.value;
  slider.addEventListener('input', () => {
    if (display) display.textContent = slider.value;
  });
});

// Loading overlay helpers
function showLoading(msg = 'Analyzing…') {
  const el = document.getElementById('loading-overlay');
  if (el) {
    el.querySelector('.loading-text').textContent = msg;
    el.classList.add('show');
  }
}
function hideLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.remove('show');
}

// Toast notification
function showToast(msg, type = 'success') {
  const t = document.createElement('div');
  t.className = 'toast';
  t.style.background = type === 'error'
    ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)';
  t.style.borderColor = type === 'error'
    ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)';
  t.style.color = type === 'error' ? '#f87171' : '#34d399';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// Render result card
function renderResult(data, container) {
  const cls = data.detected ? 'detected' : 'safe';
  const icon = data.detected ? '⚠️' : '✅';
  const label = data.detected ? 'Risk Detected' : 'Low Risk';
  const msg = data.detected
    ? `Based on the inputs, there is a <b>higher possibility</b> of <b>${data.disease}</b>.<br><br>⚠️ Please consult a specialist for proper clinical evaluation. This is AI-assisted screening, not a final diagnosis.`
    : `Your indicators appear to be within a <b>normal range</b> for <b>${data.disease}</b>.<br><br>✅ Keep up the healthy lifestyle — regular exercise, balanced diet, and routine checkups!`;

  container.innerHTML = `
    <div class="result-card ${cls}">
      <div class="result-title ${cls}">${icon} ${data.disease}</div>
      <div class="result-badge ${cls}">${label}</div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:12px;">${msg}</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:4px;">Confidence Score</div>
      <div class="confidence-bar-wrap">
        <div class="confidence-bar-fill ${cls}" id="conf-fill" style="width:0%"></div>
      </div>
      <div style="font-size:14px;font-weight:700;color:${data.detected ? '#f87171':'#34d399'};margin-bottom:16px;">${data.confidence}%</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:16px;font-style:italic;">
        ⚠️ This is an AI-assisted screening only. Always consult a licensed medical professional.
      </div>
      <div class="result-actions">
        <button onclick="downloadPDF('${data.disease}','${label}','${data.confidence}')" class="btn btn-primary" style="font-size:12px;padding:9px 18px;">📄 Download PDF Report</button>
        <a href="https://www.google.com/maps/search/${encodeURIComponent(data.disease + ' specialist near me')}" target="_blank" style="padding:9px 18px;border-radius:10px;font-size:12px;font-weight:600;text-decoration:none;transition:all 0.2s;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.05);color:#f1f5f9;display:inline-flex;align-items:center;gap:6px;">🗺️ Find Specialist</a>
      </div>
    </div>`;
  container.style.display = 'block';
  requestAnimationFrame(() => {
    const fill = document.getElementById('conf-fill');
    if (fill) fill.style.width = data.confidence + '%';
  });
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // ── Save to prediction history in localStorage ──
  const history = JSON.parse(localStorage.getItem('mdds_history') || '[]');
  history.unshift({
    disease: data.disease,
    result: label,
    confidence: data.confidence,
    detected: data.detected,
    time: new Date().toLocaleString()
  });
  localStorage.setItem('mdds_history', JSON.stringify(history.slice(0, 20)));
}

// PDF download
async function downloadPDF(disease, result, confidence) {
  try {
    const res = await fetch('/api/generate_pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disease, result, confidence })
    });
    const data = await res.json();
    if (data.pdf_b64) {
      const link = document.createElement('a');
      link.href = 'data:application/pdf;base64,' + data.pdf_b64;
      link.download = `MDDS_Report_${disease.replace(/\s+/g,'_')}.pdf`;
      link.click();
      showToast('PDF report downloaded!');
    }
  } catch (e) {
    showToast('PDF generation failed: ' + e.message, 'error');
  }
}

// Stars canvas
function initStars() {
  const canvas = document.getElementById('stars-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let stars = [];
  function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
  resize();
  window.addEventListener('resize', resize);
  for (let i = 0; i < 160; i++) {
    stars.push({ x: Math.random(), y: Math.random(), r: Math.random() * 1.4 + 0.3, a: Math.random(), da: (Math.random() - 0.5) * 0.01 });
  }
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    stars.forEach(s => {
      s.a = Math.max(0.05, Math.min(1, s.a + s.da));
      ctx.beginPath();
      ctx.arc(s.x * canvas.width, s.y * canvas.height, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${s.a})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }
  draw();
}

document.addEventListener('DOMContentLoaded', initStars);
