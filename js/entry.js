// ── ENTRY SCREEN (Nhân viên) ───────────────────────────────
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
      be_cap: t.be_cap || '',
      lsx: t.lsx,
      mo_ta: t.mo_ta,
      dvt: t.dvt,
      cong: t.cong,
      be_nhan: t.be_nhan,
      luong_dk: t.luong_dk,
      status: 'pending',  // pending | done | partial | skip
      luong_tt: t.luong_dk || 0,
      be_nhan: t.be_nhan || '',
      so_lo: '',
      ghi_chu: ''
    }))
  };

  renderWorkerTasks(name, myTasks);
}

// ── Render worker task cards ──────────────────────────────────
function renderWorkerTasks(name, tasks) {
  const wrap = document.getElementById('worker-task-area');

  if (tasks.length === 0) {
    wrap.innerHTML = `
      <button class="btn btn-outline" onclick="openAddLSX()"
        style="width:100%;border-color:#3b82f6;color:#1e40af;margin-bottom:12px">
        ➕ Thêm lệnh sản xuất
      </button>
      <div class="empty"><div class="empty-icon">✌️</div>
        <p>Không có lệnh nào được giao cho <strong>${name}</strong> hôm nay.<br>
        Bấm nút trên để tự thêm lệnh.</p>
      </div>`;
    return;
  }

  const done   = currentResult.results.filter(r => r.status === 'done').length;
  const total  = tasks.length;
  const partial = currentResult.results.filter(r => r.status === 'partial').length;
  const skip   = currentResult.results.filter(r => r.status === 'skip').length;

  let html = `
    <button class="btn btn-outline" onclick="openAddLSX()"
      style="width:100%;border-color:#3b82f6;color:#1e40af;margin-bottom:12px">
      ➕ Thêm lệnh sản xuất
    </button>
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

    const isPx = /^Px\d0$/.test(task.lsx);
    const curLsx = res.lsx || task.lsx;
    const curBeNhan = res.be_nhan || task.be_nhan || '';

    html += `<div class="w-card ${st !== 'pending' ? st : ''} ${task.worker_added ? 'worker-added' : ''} ${isPx ? 'px-card' : ''}" id="wcard-${task.id}">
      <div class="w-lsx" id="lsx-display-${task.id}">${curLsx}</div>
      <div class="w-desc">${task.mo_ta}</div>
      <div class="w-flow-col">
        <div class="w-loc-row">
          <span class="w-loc-label">🏺 Nơi cấp</span>
          <input type="text" class="w-loc-input" id="becap-${task.id}"
            placeholder="Bỏ trống nếu không có" list="be-datalist"
            autocomplete="off"
            value="${res.be_cap || task.be_cap || ''}"
            onchange="setBeCap('${task.id}', this.value)">
        </div>
        ${isPx ? `
        <div style="font-size:11px;color:#a855f7;font-weight:600;margin-bottom:4px">📦 Nơi đến — chọn nhanh:</div>
        <div class="tp-grid" id="tpgrid-${task.id}">
          ${['L113','L114','L133','L134','L138','L213'].map((be,i)=>`
            <button class="tp-btn ${curBeNhan===be?'tp-sel':''}" onclick="pickTP('${task.id}','${be}',${i+1})">${be}<br><small>x=${i+1}</small></button>
          `).join('')}
          <button class="tp-btn ${curBeNhan.startsWith('T')?'tp-t':''}" id="tbtn-${task.id}" onclick="pickT('${task.id}')">Txxx<br><small>tại trổ</small></button>
          <button class="tp-btn" onclick="clearTP('${task.id}')">✕<br><small>xóa</small></button>
        </div>` : ''}
        <div class="w-loc-row">
          <span class="w-loc-label">📦 Nơi nhận</span>
          <input type="text" class="w-loc-input" id="benhan-${task.id}"
            placeholder="${isPx ? 'L113, L114... hoặc Txxx' : 'Bể nhận'}" list="be-datalist"
            autocomplete="off" style="text-transform:uppercase"
            value="${curBeNhan}"
            onchange="${isPx ? `onPxBeNhan('${task.id}',this.value)` : `setBeNhan('${task.id}',this.value)`}">
        </div>
        <div class="w-loc-row" style="margin-top:2px">
          <span class="w-loc-label">📋 Số lô</span>
          <input type="text" class="w-loc-input" id="lo-${task.id}"
            placeholder="Tùy chọn" autocomplete="off"
            value="${res.so_lo||''}"
            onchange="setLo('${task.id}', this.value)">
        </div>
        <div style="font-size:11px;color:#94a3b8;margin-top:4px">DK: ${task.luong_dk ? task.luong_dk.toLocaleString()+' '+task.dvt : '—'}</div>
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
          onchange="setQty('${task.id}', this.value)">
        <span class="dvt">${task.dvt || 'lít'}</span>
      </div>` : ''}

      <div class="w-note">
        <input type="text" id="note-${task.id}" placeholder="Ghi chú (nếu có)"
          value="${res.ghi_chu || ''}"
          onchange="setNote('${task.id}', this.value)">
      </div>
    </div>`;
  });

  // Send button (nút Thêm LSX đã ở trên cùng)
  const allDone = currentResult.results.every(r => r.status !== 'pending');
  html += `<div style="margin-top:16px;display:flex;flex-direction:column;gap:10px">
    <button class="btn btn-success" onclick="submitResult()">
      📤 Gửi kết quả qua Zalo
    </button>
    ${allDone ? '' : '<p style="font-size:11px;color:#94a3b8;text-align:center">Điền xong tất cả task rồi bấm Gửi</p>'}
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

  // Update chỉ card này — tránh re-render 78 cards
  const card = document.getElementById('wcard-' + taskId);
  if (!card) return;

  // Cập nhật class card
  card.className = `w-card ${status !== 'pending' ? status : ''} ${card.classList.contains('worker-added') ? 'worker-added' : ''}`;

  // Cập nhật nút status
  const selMap = { done:'sel-done', partial:'sel-partial', skip:'sel-skip' };
  card.querySelectorAll('.w-status-btn').forEach(btn => {
    btn.classList.remove('sel-done','sel-partial','sel-skip');
    if (btn.getAttribute('onclick')?.includes(`'${status}'`)) {
      btn.classList.add(selMap[status]);
    }
  });

  // Qty row: skip → ẩn, khác → hiện
  const qtyRow = card.querySelector('.w-qty-row');
  if (qtyRow) qtyRow.style.display = status === 'skip' ? 'none' : '';

  // Cập nhật stats header
  const plan = state.plan;
  const myTasks = plan.tasks.filter(t => t.nguoi === state.workerName);
  const done    = currentResult.results.filter(r => r.status === 'done').length;
  const partial = currentResult.results.filter(r => r.status === 'partial').length;
  const skip2   = currentResult.results.filter(r => r.status === 'skip').length;
  const whCount = document.querySelector('.wh-count');
  if (whCount) whCount.textContent = `${done}/${myTasks.length} xong`;
  const svs = document.querySelectorAll('.sv');
  if (svs[0]) svs[0].textContent = done;
  if (svs[1]) svs[1].textContent = partial;
  if (svs[2]) svs[2].textContent = skip2;
}

function setQty(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.luong_tt = parseInt(val) || 0; saveResult(currentResult); }
}

function setNote(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.ghi_chu = val; saveResult(currentResult); }
}

function setBeCap(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.be_cap = val.trim().toUpperCase(); saveResult(currentResult); }
}

function setBeNhan(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.be_nhan = val.trim().toUpperCase(); saveResult(currentResult); }
}

// ── Px task helpers ───────────────────────────────────────────
const TP_MAP = {
  'L113':'1','L114':'2','L133':'3','L134':'4','L138':'5','L213':'6'
};

function pxNewLsx(baseLsx, x) {
  // Px10 + x=1 → P110 | Px20 + x=2 → P220
  const day = baseLsx[2]; // '1'..'9'
  return `P${x}${day}0`;
}

function updatePxCard(taskId, beNhan, newLsx) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (!res) return;
  res.be_nhan = beNhan;
  res.lsx     = newLsx;
  saveResult(currentResult);
  // Cập nhật hiển thị LSX
  const el = document.getElementById('lsx-display-' + taskId);
  if (el) el.textContent = newLsx;
  // Highlight nút đã chọn
  const grid = document.getElementById('tpgrid-' + taskId);
  if (grid) {
    grid.querySelectorAll('.tp-btn').forEach(b => b.classList.remove('tp-sel','tp-t'));
    grid.querySelectorAll('.tp-btn').forEach(b => {
      if (b.textContent.includes(beNhan)) b.classList.add('tp-sel');
    });
    if (beNhan.startsWith('T')) {
      const tbtn = document.getElementById('tbtn-' + taskId);
      if (tbtn) tbtn.classList.add('tp-t');
    }
  }
}

function pickTP(taskId, be, x) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (!res) return;
  const baseLsx = res.lsx.startsWith('P') ? res.lsx : res.lsx; // giữ base từ plan
  const task = state.plan?.tasks.find(t => t.id === taskId);
  const base = task?.lsx || res.lsx;
  const newLsx = pxNewLsx(base, String(x));
  document.getElementById('benhan-' + taskId).value = be;
  updatePxCard(taskId, be, newLsx);
}

function pickT(taskId) {
  const inp = document.getElementById('benhan-' + taskId);
  inp.value = '';
  inp.placeholder = 'T... (nhập số bể trổ)';
  inp.focus();
  const task = state.plan?.tasks.find(t => t.id === taskId);
  const baseLsx = task?.lsx || 'Px?0';
  updatePxCard(taskId, '', baseLsx);
  const grid = document.getElementById('tpgrid-' + taskId);
  if (grid) {
    grid.querySelectorAll('.tp-btn').forEach(b => b.classList.remove('tp-sel','tp-t'));
    const tbtn = document.getElementById('tbtn-' + taskId);
    if (tbtn) tbtn.classList.add('tp-t');
  }
}

function clearTP(taskId) {
  document.getElementById('benhan-' + taskId).value = '';
  const task = state.plan?.tasks.find(t => t.id === taskId);
  const baseLsx = task?.lsx || 'Px?0';
  updatePxCard(taskId, '', baseLsx);
}

function onPxBeNhan(taskId, val) {
  val = val.trim().toUpperCase();
  const task = state.plan?.tasks.find(t => t.id === taskId);
  const baseLsx = task?.lsx || 'Px?0';
  const x = TP_MAP[val];
  if (x) {
    updatePxCard(taskId, val, pxNewLsx(baseLsx, x));
  } else {
    updatePxCard(taskId, val, baseLsx);
  }
}

function setLo(taskId, val) {
  const res = currentResult.results.find(r => r.task_id === taskId);
  if (res) { res.so_lo = val.trim(); saveResult(currentResult); }
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

// ── Thêm LSX — inline card (không dùng modal) ────────────────
let inlineSt = '';

function openAddLSX() {
  // Nếu card đang mở rồi thì scroll tới và focus
  const existing = document.getElementById('add-lsx-inline');
  if (existing) { existing.scrollIntoView({behavior:'smooth',block:'center'}); return; }

  inlineSt = '';

  const card = document.createElement('div');
  card.id = 'add-lsx-inline';
  card.className = 'w-card worker-added';
  card.innerHTML = `
    <div style="font-size:13px;font-weight:700;color:#1e40af;margin-bottom:10px">
      ✏️ Lệnh mới — tự thêm
    </div>

    <!-- LSX -->
    <div style="margin-bottom:8px">
      <div class="w-loc-label" style="margin-bottom:4px">Lệnh SX (LSX) <span style="color:#ef4444">*</span></div>
      <input type="text" id="ai-lsx" class="w-loc-input" style="width:100%;text-transform:uppercase"
        placeholder="C040, PM00, S030..." list="lsx-datalist" autocomplete="off"
        oninput="aiUpdateHint(this.value.toUpperCase())">
      <div style="font-size:11px;color:#94a3b8;margin-top:3px" id="ai-hint"></div>
    </div>

    <!-- Nơi cấp + Nơi nhận -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
      <div>
        <div class="w-loc-label" style="margin-bottom:4px">🏺 Nơi cấp</div>
        <input type="text" id="ai-cap" class="w-loc-input" style="width:100%"
          placeholder="Bỏ trống nếu không có" list="be-datalist" autocomplete="off">
      </div>
      <div>
        <div class="w-loc-label" style="margin-bottom:4px">📦 Nơi nhận <span style="color:#ef4444">*</span></div>
        <input type="text" id="ai-nhan" class="w-loc-input" style="width:100%"
          placeholder="L001" list="be-datalist" autocomplete="off">
      </div>
    </div>

    <!-- Số lô -->
    <div style="margin-bottom:8px">
      <div class="w-loc-label" style="margin-bottom:4px">📋 Số lô</div>
      <input type="text" id="ai-lo" class="w-loc-input" style="width:100%"
        placeholder="Tùy chọn" autocomplete="off">
    </div>

    <!-- Trạng thái -->
    <div class="w-loc-label" style="margin-bottom:6px">Trạng thái <span style="color:#ef4444">*</span></div>
    <div class="w-status-row" style="margin-bottom:10px">
      <button class="w-status-btn" id="ai-btn-done"    onclick="aiSelectSt('done')">✅<span class="w-status-label">Xong</span></button>
      <button class="w-status-btn" id="ai-btn-partial" onclick="aiSelectSt('partial')">⚠️<span class="w-status-label">Một phần</span></button>
      <button class="w-status-btn" id="ai-btn-skip"    onclick="aiSelectSt('skip')">❌<span class="w-status-label">Bỏ qua</span></button>
    </div>

    <!-- Lượng -->
    <div class="w-qty-row" style="margin-bottom:8px">
      <input type="number" id="ai-luong" inputmode="numeric" placeholder="0"
        style="flex:1;padding:10px;border:1.5px solid #e2e8f0;border-radius:6px;
               font-size:18px;font-weight:700;text-align:right;width:100%">
      <span class="dvt" id="ai-dvt">lít</span>
    </div>

    <!-- Ghi chú -->
    <div class="w-note" style="margin-bottom:12px">
      <input type="text" id="ai-ghichu" placeholder="Ghi chú (nếu có)"
        style="width:100%;padding:8px 10px;border:1.5px solid #e2e8f0;
               border-radius:6px;font-size:13px">
    </div>

    <!-- Buttons -->
    <div style="display:flex;gap:8px">
      <button class="btn btn-outline btn-sm" onclick="cancelAddLSX()" style="flex:1">✕ Huỷ</button>
      <button class="btn btn-primary btn-sm" onclick="submitWorkerTask()" style="flex:2">✅ Lưu lệnh này</button>
    </div>`;

  // Chèn ngay sau nút "Thêm lệnh sản xuất" (phần tử đầu tiên trong wrap)
  const wrap  = document.getElementById('worker-task-area');
  const addBtn = wrap.querySelector('button');
  if (addBtn) addBtn.insertAdjacentElement('afterend', card);
  else wrap.prepend(card);

  card.scrollIntoView({behavior:'smooth', block:'start'});
  setTimeout(() => document.getElementById('ai-lsx')?.focus(), 300);
}

function cancelAddLSX() {
  document.getElementById('add-lsx-inline')?.remove();
  inlineSt = '';
}

function aiUpdateHint(code) {
  const info = LSX_DATA[code];
  const hint = document.getElementById('ai-hint');
  if (hint) hint.textContent = info ? `${info.mo_ta} · ĐVT: ${info.dvt||'—'}` : '';
  const dvt = document.getElementById('ai-dvt');
  if (dvt && info?.dvt) dvt.textContent = info.dvt;
}

function aiSelectSt(st) {
  inlineSt = st;
  const colors = { done:'#22c55e', partial:'#f59e0b', skip:'#94a3b8' };
  const bgs    = { done:'#f0fdf4', partial:'#fffbeb', skip:'#f1f5f9' };
  ['done','partial','skip'].forEach(s => {
    const btn = document.getElementById('ai-btn-' + s);
    if (!btn) return;
    btn.style.borderColor = (s === st) ? colors[s] : '#e2e8f0';
    btn.style.background  = (s === st) ? bgs[s]    : '#fff';
  });
}

function submitWorkerTask() {
  const lsx   = (document.getElementById('ai-lsx')?.value   || '').trim().toUpperCase();
  const cap   = (document.getElementById('ai-cap')?.value   || '').trim().toUpperCase();
  const nhan  = (document.getElementById('ai-nhan')?.value  || '').trim().toUpperCase();
  const lo    = (document.getElementById('ai-lo')?.value    || '').trim();
  const luong = parseInt(document.getElementById('ai-luong')?.value) || 0;
  const ghi   = (document.getElementById('ai-ghichu')?.value|| '').trim();

  if (!lsx)    { toast('⚠️ Chưa nhập mã lệnh SX'); return; }
  if (!nhan)   { toast('⚠️ Chưa nhập Nơi nhận');   return; }
  if (!inlineSt){ toast('⚠️ Chưa chọn trạng thái'); return; }

  const info  = LSX_DATA[lsx] || {};
  const newId = 'w_' + Date.now();

  // Thêm vào plan local
  if (!state.plan) state.plan = { date: state.date, tasks: [] };
  state.plan.tasks.push({
    id: newId, be_cap: cap, lsx, mo_ta: info.mo_ta||lsx,
    dvt: info.dvt||'lít', cong: info.cong||5,
    be_nhan: nhan, luong_dk: 0, nguoi: state.workerName,
    ghi_chu: ghi, worker_added: true
  });
  savePlan(state.plan);

  // Thêm vào result
  if (!currentResult) currentResult = { date: state.date, nguoi: state.workerName, submitted: false, results: [] };
  currentResult.results.push({
    task_id: newId, be_cap: cap, lsx, mo_ta: info.mo_ta||lsx,
    dvt: info.dvt||'lít', cong: info.cong||5,
    be_nhan: nhan, luong_dk: 0, luong_tt: luong,
    so_lo: lo, status: inlineSt, ghi_chu: ghi, worker_added: true
  });
  saveResult(currentResult);

  inlineSt = '';
  toast('✅ Đã thêm lệnh ' + lsx);

  // Re-render toàn bộ (inline card sẽ tự biến mất)
  const myTasks = state.plan?.tasks.filter(t => t.nguoi === state.workerName) || [];
  renderWorkerTasks(state.workerName, myTasks);
}
