// HGC Nhập Liệu Real-time
// Version badge lấy tự động từ ?v= của chính script này (luôn khớp bản deploy thật,
// vì không bump ?v= thì trình duyệt còn chẳng tải bản JS mới).
const SELF_SCRIPT_SRC = document.currentScript ? document.currentScript.src : '';
const VERSION_MATCH = SELF_SCRIPT_SRC.match(/[?&]v=(\d{4})(\d{2})(\d{2})([a-z]?)/);
const APP_VERSION = VERSION_MATCH ? `v${VERSION_MATCH[1]}${VERSION_MATCH[2]}${VERSION_MATCH[3]}${VERSION_MATCH[4]}` : 'v?';
const BUILD_DATE  = VERSION_MATCH ? `${VERSION_MATCH[1]}-${VERSION_MATCH[2]}-${VERSION_MATCH[3]}` : '?';
const WORKERS = ['Ha', 'Hao', 'Mien', 'Phong', 'Toan'];

// ── State ──────────────────────────────────────────────────
let state = {
  screen: 'home',
  role: null,          // 'tim' | 'worker'
  date: today(),
  workerName: null,
  plan: null,          // loaded plan for the day
};

function today() {
  return new Date().toISOString().split('T')[0];
}

// ── Router ─────────────────────────────────────────────────
function goto(screen) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = document.getElementById('screen-' + screen);
  if (el) el.classList.add('active');
  state.screen = screen;
  updateTopbar(screen);
  window.scrollTo(0, 0);
}

function updateTopbar(screen) {
  const topbar = document.getElementById('topbar');
  const backBtn = document.getElementById('back-btn');
  const appTitle = document.getElementById('app-title');

  const titles = {
    home:    'Chọn vai trò',
    plan:    '📋 Kế hoạch hôm nay',
    entry:   '✅ Nhập kết quả',
    summary: '📊 Tổng hợp & Xuất',
  };
  appTitle.textContent = titles[screen] || '';
  backBtn.style.display = (screen === 'home') ? 'none' : 'flex';
}

// ── localStorage helpers ────────────────────────────────────
function planKey(date) { return `hgc_plan_${date}`; }
function resultKey(date, name) { return `hgc_result_${date}_${name}`; }

function savePlan(plan) {
  localStorage.setItem(planKey(plan.date), JSON.stringify(plan));
}
function loadPlan(date) {
  try { return JSON.parse(localStorage.getItem(planKey(date))); } catch { return null; }
}
function saveResult(result) {
  localStorage.setItem(resultKey(result.date, result.nguoi), JSON.stringify(result));
}
function loadResult(date, name) {
  try { return JSON.parse(localStorage.getItem(resultKey(date, name))); } catch { return null; }
}

// ── Toast ───────────────────────────────────────────────────
function toast(msg, ms=2500) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

// ── URL params decode on load ───────────────────────────────
function tryLoadFromURL() {
  const params      = new URLSearchParams(location.search);
  const planEncoded = params.get('plan');
  const planFile    = params.get('plan_file');
  const workerName  = params.get('worker') || params.get('w');
  const forceOpen   = params.get('force') === '1';

  function afterPlanLoaded() {
    if (workerName && WORKERS.includes(workerName)) {
      state.workerName = workerName;
      state.role = 'worker';
      initEntry();
      goto('entry');
      setTimeout(() => selectWorker(workerName), 150);
    } else {
      state.role = 'worker';
      initEntry();
      goto('entry');
    }
  }

  // ?plan_file=phong-29062026 → fetch từ /plans/phong-29062026.json
  if (planFile) {
    const base = location.origin + location.pathname.replace(/\/[^/]*$/, '/');
    fetch(base + 'plans/' + planFile + '.json')
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(plan => {
        if (!forceOpen && isPlanExpired(plan.date)) { showExpiredPlan(plan.date); return; }
        savePlan(plan);
        state.date = plan.date;
        toast('✅ Đã tải kế hoạch ' + fmtDate(plan.date) + (forceOpen ? ' (mở lại)' : ''));
        afterPlanLoaded();
      })
      .catch(() => toast('❌ Không tải được kế hoạch: ' + planFile));
    return;
  }

  // ?plan=BASE64 (kế hoạch nhỏ — giữ tương thích cũ)
  if (planEncoded) {
    try {
      const plan = decodePlan(planEncoded);
      if (!forceOpen && isPlanExpired(plan.date)) { showExpiredPlan(plan.date); return; }
      savePlan(plan);
      state.date = plan.date;
      toast('✅ Đã tải kế hoạch ' + fmtDate(plan.date));
    } catch(e) {
      toast('❌ Link kế hoạch không hợp lệ');
      return;
    }
    afterPlanLoaded();
    return;
  }

  // Auto-open nếu chỉ có ?w= (dùng plan đã lưu trong localStorage)
  if (workerName && WORKERS.includes(workerName)) {
    state.workerName = workerName;
    state.role = 'worker';
    initEntry();
    goto('entry');
    setTimeout(() => selectWorker(workerName), 150);
  }
}

// ── Format date VN ──────────────────────────────────────────
function fmtDate(d) {
  const [y,m,day] = d.split('-');
  return `${day}/${m}/${y}`;
}

// ── Khóa kế hoạch quá khứ: chỉ HÔM NAY trở đi mới nhập được ──
// (nhập bù ngày trước: mở link hôm nay → nút Thêm lệnh → đổi ô Ngày)
function isPlanExpired(dateStr) {
  return !!dateStr && dateStr < today();   // ISO YYYY-MM-DD so sánh chuỗi
}
function showExpiredPlan(dateStr) {
  const el = document.getElementById('screen-entry');
  if (el) el.innerHTML = `<div class="empty" style="margin-top:48px;padding:0 14px">
    <div class="empty-icon">🔒</div>
    <p><strong>Kế hoạch ngày ${fmtDate(dateStr)} đã hết hạn.</strong></p>
    <p style="margin-top:10px">Chỉ nhập được kế hoạch <strong>hôm nay trở đi</strong>.<br>
    Vui lòng mở <strong>link kế hoạch hôm nay</strong> mà Giám sát gửi.</p>
    <p style="margin-top:14px;font-size:12px;color:#94a3b8">
      Quên nhập hôm qua? Mở link hôm nay → bấm ➕ Thêm lệnh sản xuất → đổi ô 📅 Ngày để nhập bù.</p>
  </div>`;
  goto('entry');
}

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Version badge
  document.querySelectorAll('.version-txt').forEach(el => {
    el.textContent = APP_VERSION + ' · ' + BUILD_DATE;
  });

  // Back button
  document.getElementById('back-btn').addEventListener('click', () => {
    if (state.screen === 'entry') goto(state.role === 'tim' ? 'home' : 'home');
    else goto('home');
  });

  // Home role buttons
  document.getElementById('btn-tim').addEventListener('click', () => {
    state.role = 'tim';
    initPlan();
    goto('plan');
  });
  document.getElementById('btn-worker').addEventListener('click', () => {
    state.role = 'worker';
    initEntry();
    goto('entry');
  });
  document.getElementById('btn-summary').addEventListener('click', () => {
    goto('summary');
    initSummary();
  });

  // Register SW — unregister cũ trước để force dùng code mới
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(regs => {
      regs.forEach(r => r.unregister());
    }).finally(() => {
      navigator.serviceWorker.register('/hgc-nhap-lieu/sw.js').catch(() => {});
    });
  }

  // Check URL for plan data or worker name
  tryLoadFromURL();
});
