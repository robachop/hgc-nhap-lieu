// ── PLAN SCREEN (Tim) ──────────────────────────────────────
let editingPlan = null;   // current plan being built
let taskCounter = 0;

function initPlan() {
  const date = document.getElementById('plan-date').value || today();
  document.getElementById('plan-date').value = date;
  state.date = date;

  // Load existing plan for this date
  editingPlan = loadPlan(date) || { date, tasks: [] };

  // Populate LSX datalist
  buildLSXDatalist();

  renderPlanTasks();
  renderPlanStats();
}

// ── LSX datalist ────────────────────────────────────────────
function buildLSXDatalist() {
  const dl = document.getElementById('lsx-datalist');
  if (dl.children.length > 0) return; // already built
  Object.entries(LSX_DATA).forEach(([code, info]) => {
    const opt = document.createElement('option');
    opt.value = code;
    opt.label = info.mo_ta;
    dl.appendChild(opt);
  });
  // Bể datalist
  const dlBe = document.getElementById('be-datalist');
  if (dlBe.children.length === 0) {
    BE_LIST.forEach(be => {
      const opt = document.createElement('option');
      opt.value = be;
      dlBe.appendChild(opt);
    });
  }
}

// ── Quick LSX buttons ────────────────────────────────────────
function renderQuickLSX() {
  const wrap = document.getElementById('quick-lsx');
  wrap.innerHTML = LSX_TOP.map(code =>
    `<button class="btn btn-sm btn-outline" onclick="setLSX('${code}')"
       title="${LSX_DATA[code]?.mo_ta||''}" style="width:auto">${code}</button>`
  ).join('');
}

function setLSX(code) {
  document.getElementById('inp-lsx').value = code;
  updateLSXHint(code);
}

function updateLSXHint(code) {
  const info = LSX_DATA[code];
  const hint = document.getElementById('lsx-hint');
  hint.textContent = info ? `${info.mo_ta} · ĐVT: ${info.dvt||'—'} · Công: ${info.cong}` : '';
}

// ── Add task ─────────────────────────────────────────────────
function addTask() {
  const lsx    = document.getElementById('inp-lsx').value.trim().toUpperCase();
  const beNhan = document.getElementById('inp-be-nhan').value.trim().toUpperCase();
  const beCap  = document.getElementById('inp-be-cap').value.trim().toUpperCase();
  const luong  = parseInt(document.getElementById('inp-luong').value) || 0;
  const nguoi  = document.getElementById('inp-nguoi').value;
  const ghiChu = document.getElementById('inp-ghi-chu').value.trim();

  if (!lsx)    { toast('⚠️ Chưa nhập Lệnh SX'); return; }
  if (!beNhan) { toast('⚠️ Chưa nhập Bể nhận'); return; }
  if (!nguoi)  { toast('⚠️ Chưa chọn Người'); return; }

  const info = LSX_DATA[lsx] || {};
  const task = {
    id: 't' + (++taskCounter),
    be_cap: beCap, lsx, be_nhan: beNhan,
    mo_ta: info.mo_ta || lsx,
    dvt: info.dvt || '',
    cong: info.cong || 5,
    luong_dk: luong,
    nguoi, ghi_chu: ghiChu
  };

  editingPlan.tasks.push(task);
  savePlan(editingPlan);

  // Clear form (keep nguoi)
  document.getElementById('inp-lsx').value = '';
  document.getElementById('inp-be-nhan').value = '';
  document.getElementById('inp-be-cap').value = '';
  document.getElementById('inp-luong').value = '';
  document.getElementById('inp-ghi-chu').value = '';
  document.getElementById('lsx-hint').textContent = '';

  renderPlanTasks();
  renderPlanStats();
  toast('✅ Đã thêm task');
}

function deleteTask(id) {
  editingPlan.tasks = editingPlan.tasks.filter(t => t.id !== id);
  savePlan(editingPlan);
  renderPlanTasks();
  renderPlanStats();
}

// ── Render plan task list ────────────────────────────────────
function renderPlanTasks() {
  const wrap = document.getElementById('plan-task-list');
  if (!editingPlan || editingPlan.tasks.length === 0) {
    wrap.innerHTML = `<div class="empty"><div class="empty-icon">📋</div>
      <p>Chưa có task nào.<br>Thêm task bên trên.</p></div>`;
    return;
  }

  // Group by person
  const byPerson = {};
  WORKERS.forEach(w => byPerson[w] = []);
  editingPlan.tasks.forEach(t => {
    if (!byPerson[t.nguoi]) byPerson[t.nguoi] = [];
    byPerson[t.nguoi].push(t);
  });

  let html = '';
  WORKERS.forEach(name => {
    const tasks = byPerson[name];
    if (!tasks || tasks.length === 0) return;
    html += `<div class="sec-hdr">👷 ${name} (${tasks.length} task)</div>`;
    tasks.forEach(t => {
      const cap = t.be_cap ? `<span class="tc-be">${t.be_cap}</span><span class="tc-arrow">→</span>` : '';
      html += `<div class="task-card">
        <div class="tc-row">
          <span class="tc-lsx">${t.lsx}</span>
          <span class="tc-desc">${t.mo_ta}</span>
          <button class="tc-del" onclick="deleteTask('${t.id}')">🗑</button>
        </div>
        <div class="tc-flow">
          ${cap}
          <span class="tc-be">${t.be_nhan}</span>
          <span style="margin-left:auto" class="tc-qty">${t.luong_dk ? t.luong_dk.toLocaleString() + ' ' + t.dvt : '—'}</span>
        </div>
        ${t.ghi_chu ? `<div style="font-size:11px;color:#64748b;margin-top:3px">💬 ${t.ghi_chu}</div>` : ''}
      </div>`;
    });
  });
  wrap.innerHTML = html;
}

function renderPlanStats() {
  if (!editingPlan) return;
  const n = editingPlan.tasks.length;
  const people = new Set(editingPlan.tasks.map(t => t.nguoi)).size;
  document.getElementById('plan-stats').textContent =
    n ? `${n} task · ${people} người` : '';
}

// ── Date change ───────────────────────────────────────────────
function onPlanDateChange() {
  const date = document.getElementById('plan-date').value;
  state.date = date;
  editingPlan = loadPlan(date) || { date, tasks: [] };
  renderPlanTasks();
  renderPlanStats();
}

// ── Compact plan encoding (chỉ dữ liệu cần thiết) ────────────
function encodePlan(plan) {
  const compact = {
    d: plan.date,
    t: plan.tasks.map(t => ({
      i: t.id, c: t.be_cap||'', l: t.lsx, n: t.be_nhan,
      q: t.luong_dk||0, p: t.nguoi, g: t.ghi_chu||''
    }))
  };
  return encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(compact)))));
}

function decodePlan(encoded) {
  const compact = JSON.parse(decodeURIComponent(escape(atob(decodeURIComponent(encoded)))));
  return {
    date: compact.d,
    tasks: compact.t.map(t => {
      const info = LSX_DATA[t.l] || {};
      return { id:t.i, be_cap:t.c, lsx:t.l, mo_ta:info.mo_ta||t.l,
               dvt:info.dvt||'', cong:info.cong||5,
               be_nhan:t.n, luong_dk:t.q, nguoi:t.p, ghi_chu:t.g };
    })
  };
}

// ── Gửi kế hoạch qua Zalo ────────────────────────────────────
function sendPlanZalo() {
  if (!editingPlan || editingPlan.tasks.length === 0) {
    toast('⚠️ Chưa có task nào'); return;
  }
  editingPlan.date = document.getElementById('plan-date').value;
  savePlan(editingPlan);

  const encoded = encodePlan(editingPlan);
  const base    = 'https://robachop.github.io/hgc-nhap-lieu/';
  const url     = base + '?plan=' + encoded;
  const msg     = `📋 Kế hoạch HGC ${fmtDate(editingPlan.date)} (${editingPlan.tasks.length} task)\nMở link để xem việc của bạn:\n${url}`;

  if (navigator.share) {
    navigator.share({ title: 'Kế hoạch HGC ' + fmtDate(editingPlan.date), text: msg })
      .catch(() => fallbackCopy(url, msg));
  } else {
    fallbackCopy(url, msg);
  }
}

function fallbackCopy(url, msg) {
  navigator.clipboard.writeText(msg)
    .then(() => toast('📋 Đã copy! Dán vào Zalo gửi công nhân'))
    .catch(() => {
      // Last resort: show the URL
      document.getElementById('share-url-wrap').style.display = 'block';
      document.getElementById('share-url-text').value = msg;
    });
}

// ── QR cố định cho từng công nhân ────────────────────────────
function showWorkerQRs() {
  const modal = document.getElementById('qr-modal');
  const base  = 'https://robachop.github.io/hgc-nhap-lieu/';
  const wrap  = document.getElementById('worker-qrs');
  wrap.innerHTML = '';

  WORKERS.forEach(name => {
    const url = base + '?worker=' + name;
    const div = document.createElement('div');
    div.style.cssText = 'text-align:center;padding:8px 0;border-bottom:1px solid #e2e8f0';

    const label = document.createElement('div');
    label.style.cssText = 'font-weight:700;font-size:14px;margin-bottom:6px';
    label.textContent = '👷 ' + name;
    div.appendChild(label);

    const canvas = document.createElement('canvas');
    canvas.width = 150; canvas.height = 150;
    div.appendChild(canvas);

    const urlEl = document.createElement('div');
    urlEl.style.cssText = 'font-size:9px;color:#94a3b8;word-break:break-all;margin:4px 0 2px';
    urlEl.textContent = url;
    div.appendChild(urlEl);

    const copyBtn = document.createElement('button');
    copyBtn.textContent = '📋 Copy link';
    copyBtn.style.cssText = 'font-size:11px;padding:4px 10px;border:1px solid #e2e8f0;border-radius:5px;background:#fff;cursor:pointer;margin-top:2px';
    copyBtn.onclick = () => navigator.clipboard.writeText(url).then(() => { copyBtn.textContent = '✅ Đã copy!'; setTimeout(() => copyBtn.textContent='📋 Copy link', 1500); });
    div.appendChild(copyBtn);

    wrap.appendChild(div);

    if (typeof QRCode !== 'undefined') {
      QRCode.toCanvas(canvas, url, { width: 150, margin: 1,
        color: { dark:'#0f172a', light:'#ffffff' } }, () => {});
    } else {
      canvas.getContext('2d').fillText('QR N/A', 10, 75);
    }
  });

  document.getElementById('qr-modal-title').textContent = '📲 QR cố định cho công nhân';
  document.getElementById('qr-modal-sub').textContent   = 'In ra hoặc gửi cho từng người 1 lần. Họ quét để cài app.';
  modal.classList.remove('hidden');
}

function closeQR() {
  document.getElementById('qr-modal').classList.add('hidden');
}

function copyWorkerLinks() {
  const base  = 'https://robachop.github.io/hgc-nhap-lieu/';
  const links = WORKERS.map(n => `${n}: ${base}?worker=${n}`).join('\n');
  navigator.clipboard.writeText(links)
    .then(() => toast('📋 Đã copy link tất cả công nhân'));
}

// ── Wire up events (called after DOM ready) ──────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('plan-date').value = today();
  document.getElementById('plan-date').addEventListener('change', onPlanDateChange);
  document.getElementById('btn-add-task').addEventListener('click', addTask);
  document.getElementById('btn-send-zalo').addEventListener('click', sendPlanZalo);
  document.getElementById('btn-show-qr').addEventListener('click', showWorkerQRs);
  document.getElementById('btn-close-qr').addEventListener('click', closeQR);
  document.getElementById('btn-copy-worker-links').addEventListener('click', copyWorkerLinks);
  document.getElementById('inp-lsx').addEventListener('input', e => updateLSXHint(e.target.value.toUpperCase()));

  // Person quick-select for Tim form
  document.querySelectorAll('.tim-person-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tim-person-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('inp-nguoi').value = btn.dataset.name;
    });
  });

  renderQuickLSX();
});
