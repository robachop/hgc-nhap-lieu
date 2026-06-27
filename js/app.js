// HGC Nhập Liệu Real-time — V1.0
const APP_VERSION = 'V1.0';
const BUILD_DATE  = '2026-06-27';
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
  const workerName  = params.get('worker') || params.get('w');

  // Load plan from URL if present (?plan=BASE64)
  if (planEncoded) {
    try {
      const plan = decodePlan(planEncoded);
      savePlan(plan);
      state.date = plan.date;
      toast('✅ Đã tải kế hoạch ' + fmtDate(plan.date));
    } catch(e) {
      toast('❌ Link kế hoạch không hợp lệ');
      return;
    }
  }

  // Auto-open worker screen if ?worker=Name given
  if (workerName && WORKERS.includes(workerName)) {
    state.workerName = workerName;
    state.role = 'worker';
    initEntry();
    goto('entry');
    // Small delay to let DOM render name picker before selecting
    setTimeout(() => selectWorker(workerName), 150);
  } else if (planEncoded) {
    // Plan loaded but no worker specified — go to worker screen, let them pick name
    state.role = 'worker';
    initEntry();
    goto('entry');
  }
}

// ── Format date VN ──────────────────────────────────────────
function fmtDate(d) {
  const [y,m,day] = d.split('-');
  return `${day}/${m}/${y}`;
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

  // Register SW
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/hgc-nhap-lieu/sw.js').catch(() => {});
  }

  // Check URL for plan data or worker name
  tryLoadFromURL();
});
