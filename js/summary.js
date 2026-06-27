// ── SUMMARY SCREEN (Tim — tổng hợp + export) ──────────────
let importedResults = [];  // array of result objects

function initSummary() {
  importedResults = [];
  // Try load results already in localStorage for current date
  const date = state.date || today();
  WORKERS.forEach(name => {
    const res = loadResult(date, name);
    if (res && res.results && res.results.length > 0) importedResults.push(res);
  });
  renderSummary();
}

// ── Import JSON files from workers ────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('import-file');
  fileInput.addEventListener('change', e => {
    const files = Array.from(e.target.files);
    let loaded = 0;
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = ev => {
        try {
          const res = JSON.parse(ev.target.result);
          // Deduplicate by (date, nguoi)
          const idx = importedResults.findIndex(r => r.date === res.date && r.nguoi === res.nguoi);
          if (idx >= 0) importedResults[idx] = res;
          else importedResults.push(res);
          saveResult(res);
          loaded++;
          if (loaded === files.length) {
            toast(`✅ Đã import ${loaded} file`);
            renderSummary();
          }
        } catch { toast('❌ File không hợp lệ: ' + file.name); }
      };
      reader.readAsText(file);
    });
    fileInput.value = '';
  });

  // Click import zone
  document.getElementById('import-zone').addEventListener('click', () => fileInput.click());
  document.getElementById('btn-export-s500').addEventListener('click', exportS500);
  document.getElementById('btn-clear-summary').addEventListener('click', () => {
    if (confirm('Xóa tất cả dữ liệu đã import?')) {
      importedResults = [];
      renderSummary();
      toast('🗑 Đã xóa');
    }
  });
});

// ── Render summary table ──────────────────────────────────────
function renderSummary() {
  const wrap = document.getElementById('summary-content');

  if (importedResults.length === 0) {
    wrap.innerHTML = `<div class="empty"><div class="empty-icon">📭</div>
      <p>Chưa có kết quả nào.<br>Import file JSON từ công nhân.</p></div>`;
    document.getElementById('btn-export-s500').disabled = true;
    return;
  }

  // Flatten all results
  const allRows = [];
  importedResults.forEach(res => {
    res.results.forEach(r => {
      if (r.status !== 'skip' && r.status !== 'pending') {
        allRows.push({ ...r, nguoi: res.nguoi, date: res.date, submitted_at: res.submitted_at });
      }
    });
  });

  // Stats
  const total   = allRows.length + importedResults.reduce((s,r) => s + r.results.filter(x=>x.status==='skip').length, 0);
  const done    = importedResults.reduce((s,r) => s + r.results.filter(x=>x.status==='done').length, 0);
  const partial = importedResults.reduce((s,r) => s + r.results.filter(x=>x.status==='partial').length, 0);
  const skip    = importedResults.reduce((s,r) => s + r.results.filter(x=>x.status==='skip').length, 0);

  let html = `
    <div class="stats-bar">
      <div class="stat-box"><div class="sv sv-green">${done}</div><div class="sl">✅ Xong</div></div>
      <div class="stat-box"><div class="sv sv-amber">${partial}</div><div class="sl">⚠️ Một phần</div></div>
      <div class="stat-box"><div class="sv sv-red">${skip}</div><div class="sl">❌ Bỏ qua</div></div>
      <div class="stat-box"><div class="sv">${importedResults.length}</div><div class="sl">👷 Người</div></div>
    </div>
    <table class="sum-table">
    <thead><tr>
      <th>Người</th><th>Bể cấp</th><th>LSX</th><th>Bể nhận</th>
      <th>DK</th><th>Thực tế</th><th>TT</th><th>Ghi chú</th>
    </tr></thead>
    <tbody>`;

  allRows.forEach(r => {
    const stClass = r.status === 'done' ? 'sc-done' : r.status === 'partial' ? 'sc-partial' : 'sc-skip';
    const stLabel = r.status === 'done' ? '✅' : r.status === 'partial' ? '⚠️' : '❌';
    html += `<tr>
      <td><strong>${r.nguoi}</strong></td>
      <td style="font-family:monospace">${r.be_cap||'—'}</td>
      <td style="font-family:monospace;font-weight:700">${r.lsx}</td>
      <td style="font-family:monospace">${r.be_nhan}</td>
      <td style="text-align:right">${r.luong_dk?.toLocaleString()||'—'}</td>
      <td style="text-align:right;font-weight:700">${r.luong_tt?.toLocaleString()||'—'}</td>
      <td><span class="status-chip ${stClass}">${stLabel}</span></td>
      <td style="font-size:11px;color:#64748b">${r.ghi_chu||''}</td>
    </tr>`;
  });

  // Skip rows
  importedResults.forEach(res => {
    res.results.filter(r=>r.status==='skip').forEach(r => {
      html += `<tr style="opacity:.5">
        <td>${res.nguoi}</td><td style="font-family:monospace">${r.be_cap||'—'}</td>
        <td style="font-family:monospace">${r.lsx}</td><td style="font-family:monospace">${r.be_nhan}</td>
        <td>—</td><td>—</td><td><span class="status-chip sc-skip">❌</span></td>
        <td style="font-size:11px">${r.ghi_chu||''}</td>
      </tr>`;
    });
  });

  html += '</tbody></table>';
  wrap.innerHTML = html;
  document.getElementById('btn-export-s500').disabled = (allRows.length === 0);
}

// ── Export S500.xlsx ──────────────────────────────────────────
function exportS500() {
  if (!window.XLSX) { toast('⏳ Đang tải thư viện Excel...'); return; }

  const rows = [];
  const s500Headers = [
    'ID','Start time','Completion time','Email','Name',
    'Bể / xe','Lệnh sản xuất','Ngày thực hiện','Lượng thực tế',
    'Người thực hiện1','Lô','Ghi chú','Diễn giải','Công','Bể / xe cấp'
  ];
  rows.push(s500Headers);

  let idCounter = 1;
  importedResults.forEach(res => {
    res.results.forEach(r => {
      if (r.status === 'skip' || r.status === 'pending') return;
      const info = LSX_DATA[r.lsx] || {};
      const ngay = res.date; // YYYY-MM-DD → Excel will store as string, ok
      rows.push([
        idCounter++,             // A: ID
        '',                      // B: Start time
        res.submitted_at || '',  // C: Completion time
        'anonymous',             // D: Email
        '',                      // E: Name
        r.be_nhan,               // F: Bể / xe (nhận)
        r.lsx,                   // G: Lệnh sản xuất
        ngay,                    // H: Ngày thực hiện
        r.luong_tt || r.luong_dk || 0, // I: Lượng thực tế
        r.nguoi,                 // J: Người thực hiện1
        r.so_lo || '',           // K: Lô
        r.ghi_chu || '',         // L: Ghi chú
        r.mo_ta || info.mo_ta || '', // M: Diễn giải
        r.cong || info.cong || 5,    // N: Công
        r.be_cap || '',          // O: Bể / xe cấp (nguồn)
      ]);
    });
  });

  if (rows.length <= 1) { toast('Không có dữ liệu để xuất'); return; }

  const ws = XLSX.utils.aoa_to_sheet(rows);

  // Column widths
  ws['!cols'] = [
    {wch:5},{wch:18},{wch:18},{wch:10},{wch:8},
    {wch:8},{wch:12},{wch:14},{wch:12},
    {wch:12},{wch:8},{wch:20},{wch:30},{wch:6},{wch:12}
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'S500');

  const date = (importedResults[0]?.date || today()).replace(/-/g,'');
  XLSX.writeFile(wb, `HGC_S500_${date}.xlsx`);
  toast(`✅ Đã xuất S500 (${rows.length - 1} dòng)`);
}
