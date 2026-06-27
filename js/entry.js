// ── ENTRY SCREEN (Công nhân) ───────────────────────────────
let currentResult = null;

function initEntry() {
  // Nếu không có date từ URL param thì dùng hôm nay
  const date = state.date || today();
  state.date = date;

  // Try load plan (from URL already saved, or localStorage)
  const plan = loadPlan(date);
  state.plan = plan;

  renderNamePicker(date, plan);
  document.getElementById('entry-date-lbl').textContent = fmtDate(date);
}

// ── Name picker ───────────────────────────────────────────────
function renderNamePicker(date, plan) {
  const wrap = document.getElementById('name-picker-wrap');
  const taskArea = document.getElementById('worker-task-area');

  if (!plan) {
    wrap.innerHTML = `<div class="empty"><div class="empty-icon">📭</div>
      <p>Chưa có kế hoạch ngày <strong>${fmtDate(date)}</strong>.<br>
      Quét QR từ Tim hoặc chờ Tim nhập kế hoạch.</p></div>`;
    taskArea.innerHTML = '';
    return;
  }

  const nameGrid = `<div class="name-grid" id="name-grid">
    ${WORKERS.map(n => `<button class="name-btn" data-name="${n}" onclick="selectWorker('${n}')">${n}</button>`).join('')}
  </div>`;
  wrap.innerHTML = nameGrid;
  taskArea.innerHTML = '';

  // Auto-select if only 1 worker on plan
  const uniqueWorkers = [...new Set(plan.tasks.map(t => t.nguoi))];
  if (uniqueWorkers.length === 1) selectWorker(uniqueWorkers[0]);
}

function selectWorker(name) {
  state.workerName = name;
  document.querySelectorAll('.name-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.name === name);
  });

  const plan = state.plan;
  const myTasks = plan ? plan.tasks.filter(t => t.nguoi === name) : [];

  // Load or init result
  currentResult = loadResult(state.date, name) || {
    date: state.date,
    nguoi: name,
    submitted: false,
    results: myTasks.map(t => ({
      task_id: t.id,
      be_cap: t.be_cap,
      lsx: t.lsx,
      mo_ta: t.mo_ta,
      dvt: t.dvt,
      cong: t.cong,
      be_nhan: t.be_nhan,
      luong_dk: t.luong_dk,
      status: 'pending',  // pending | done | partial | skip
      luong_tt: t.luong_dk || 0,
      ghi_chu: ''
    }))
  };

  renderWorkerTasks(name, myTasks);
}

// ── Render worker task cards ──────────────────────────────────
function renderWorkerTasks(name, tasks) {
  const wrap = document.getElementById('worker-task-area');

  if (tasks.length === 0) {
    wrap.innerHTML = `<div class="empty"><div class="empty-icon">✌️</div>
      <p>Không có task nào được giao cho <strong>${name}</strong> hôm nay.</p></div>`;
    return;
  }

  const done   = currentResult.results.filter(r => r.status === 'done').length;
  const total  = tasks.length;
  const partial = currentResult.results.filter(r => r.status === 'partial').length;
  const skip   = currentResult.results.filter(r => r.status === 'skip').length;

  let html = `
    <div class="worker-header">
      <div>
        <div class="wh-name">👷 ${name}</div>
        <div class="wh-date">${fmtDate(state.date)}</div>
      </div>
      <div class="wh-count">${done}/${total} xong</div>
    </div>
    <div class="stats-bar">
      <div class="stat-box"><div class="sv sv-green">${done}</div><div class="sl">✅ Xong</div></div>
      <div class="stat-box"><div class="sv sv-amber">${partial}</div><div class="sl">⚠️ Một phần</div></div>
      <div class="stat-box"><div class="sv sv-red">${skip}</div><div class="sl">❌ Bỏ qua</div></div>
    </div>`;

  tasks.forEach((task, i) => {
    const res = currentResult.results.find(r => r.task_id === task.id) || {};
    const st  = res.status || 'pending';
    const capFlow = task.be_cap
      ? `<span class="w-be">${task.be_cap}</span><span class="w-arrow">→</span>` : '';

    html += `<div class="w-card ${st !== 'pending' ? st : ''}" id="wcard-${task.id}">
      <div class="w-lsx">${task.lsx}</div>
      <div class="w-desc">${task.mo_ta}</div>
      <div class="w-flow">
        ${capFlow}
        <span class="w-be">${task.be_nhan}</span>
        <span class="w-dk" style="margin-left:auto">DK: ${task.luong_dk ? task.luong_dk.toLocaleString()+' '+task.dvt : '—'}</span>
      </div>

      <div class="w-status-row">
        <button class="w-status-btn ${st==='done'?'sel-done':''}"
          onclick="setStatus('${task.id}','done')">✅<span class="w-status-label">Xong</span></button>
        <button class="w-status-btn ${st==='partial'?'sel-partial':''}"
          onclick="setStatus('${task.id}','partial')">⚠️<span class="w-status-label">Một phần</span></button>
        <button class="w-status-btn ${st==='skip'?'sel-skip':''}"
          onclick="setStatus('${task.id}','skip')">❌<span class="w-status-label">Bỏ qua</span></button>
      </div>

      ${st !== 'skip' ? `
      <div class="w-qty-row">
        <input type="number" inputmode="numeric" id="qty-${task.id}"
          value="${res.luong_tt || task.luong_dk || ''}"
          placeholder="${task.luong_dk || 0}"
          onchange="setQty('${task.id}', this.value)"
          ${st === 'pending' ? 'disabled' : ''}>
        <span class="dvt">${task.dvt || 'lít'}</span>
      </div>` : ''}

      <div class="w-note">
        <input type="text" id="note-${task.id}" placeholder="Ghi chú (nếu có)"
          value="${res.ghi_chu || ''}"
          onchange="setNote('${task.id}', this.value)"
          ${st === 'pending' ? 'disabled' : ''}>
      </div>
    </div>`;
  });

  // Send button
  const allDone = currentResult.results.every(r => r.status !== 'pending');
  html += `<div style="margin-top:16px">
    <button class="btn btn-success" onclick="submitResult()">
      📤 Gửi kết quả qua Zalo
    </button>
    ${allDone ? '' : '<p style="font-size:11px;color:#94a3b8;text-align:center;margin-top:6px">Điền xong tất cả task rồi bấm Gửi</p>'}
  </div>`;

  wrap.innerHTML = html;
}

// ── Status / Qty / Note setters ───────────────────────────────
function setStatus(taskId, status) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (!res) return;
  res.status = status;
  if (status === 'skip') res.luong_tt = 0;
  saveResult(currentResult);

  // Re-render worker tasks
  const plan = state.plan;
  const myTasks = plan.tasks.filter(t => t.nguoi === state.workerName);
  renderWorkerTasks(state.workerName, myTasks);
}

function setQty(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.luong_tt = parseInt(val) || 0; saveResult(currentResult); }
}

function setNote(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.ghi_chu = val; saveResult(currentResult); }
}

// ── Submit / Share ────────────────────────────────────────────
function submitResult() {
  if (!currentResult) return;

  const pending = currentResult.results.filter(r => r.status === 'pending');
  if (pending.length > 0) {
    toast(`⚠️ Còn ${pending.length} task chưa điền trạng thái`);
    return;
  }

  currentResult.submitted_at = new Date().toISOString();
  currentResult.submitted = true;
  saveResult(currentResult);

  const json = JSON.stringify(currentResult, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const filename = `HGC_${currentResult.date}_${currentResult.nguoi}.json`;

  // Try Web Share API (Android share sheet — includes Zalo)
  if (navigator.share && navigator.canShare) {
    const file = new File([blob], filename, { type: 'application/json' });
    if (navigator.canShare({ files: [file] })) {
      navigator.share({
        title: `HGC Nhập liệu - ${currentResult.nguoi} - ${fmtDate(currentResult.date)}`,
        text: `Kết quả sản xuất ${currentResult.nguoi} ngày ${fmtDate(currentResult.date)}`,
        files: [file]
      }).then(() => toast('✅ Đã gửi kết quả!'))
        .catch(err => { if (err.name !== 'AbortError') downloadJSON(blob, filename); });
      return;
    }
  }

  // Fallback: download file
  downloadJSON(blob, filename);
  toast('📥 Đã tải file — gửi cho Tim qua Zalo');
}

function downloadJSON(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
