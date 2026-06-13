let currentUser = null;
let currentFilter = 'all';
let installPrompt = null;
let pushEnabled = false;
let VAPID_PUBLIC_KEY = null;
let telegramDeepLinkUrl = '';
let performanceChart = null;

const ICONS = {
  bellOff: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      <path d="M3 3l18 18"/>
    </svg>
  `,
  bellOn: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
    </svg>
  `,
  telegram: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22 2L11 13"/>
      <path d="M22 2 15 22l-4-9-9-4Z"/>
    </svg>
  `,
  linked: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5"/>
    </svg>
  `,
  logout: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
      <path d="m16 17 5-5-5-5"/>
      <path d="M21 12H9"/>
    </svg>
  `,
  install: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v12"/>
      <path d="m7 10 5 5 5-5"/>
      <path d="M5 21h14"/>
    </svg>
  `,
  signal: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 18h18"/>
      <path d="M5 18V8"/>
      <path d="M10 18V4"/>
      <path d="M15 18v-6"/>
      <path d="M20 18V9"/>
    </svg>
  `,
  overview: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12h6V4H4z"/>
      <path d="M14 20h6v-8h-6z"/>
      <path d="M14 10h6V4h-6z"/>
      <path d="M4 20h6v-4H4z"/>
    </svg>
  `,
  holdings: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16"/>
      <path d="M4 12h16"/>
      <path d="M4 17h16"/>
      <path d="M8 4v16"/>
    </svg>
  `,
  insights: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16v10H7l-3 3z"/>
      <path d="M8 9h8"/>
      <path d="M8 12h5"/>
    </svg>
  `,
  activity: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 12h4l2-5 4 10 2-5h6"/>
    </svg>
  `,
  profile: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 21a8 8 0 0 0-16 0"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  `,
  source: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16v10H7l-3 3z"/>
      <path d="M8 9h8"/>
    </svg>
  `,
  holding: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2v20"/>
      <path d="M17 5H9a3 3 0 0 0 0 6h6a3 3 0 0 1 0 6H6"/>
    </svg>
  `,
  pending: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9"/>
      <path d="M12 7v5l3 3"/>
    </svg>
  `,
};

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

const urlB64ToUint8Array = (b64) => {
  const raw = atob(b64.replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
};

const setIcon = (el, markup) => {
  if (el) el.innerHTML = markup;
};

function hydrateStaticIcons() {
  document.querySelectorAll('[data-icon="install"]').forEach((el) => setIcon(el, ICONS.install));
  document.querySelectorAll('[data-icon="signal"]').forEach((el) => setIcon(el, ICONS.signal));
  document.querySelectorAll('[data-icon="overview"]').forEach((el) => setIcon(el, ICONS.overview));
  document.querySelectorAll('[data-icon="holdings"]').forEach((el) => setIcon(el, ICONS.holdings));
  document.querySelectorAll('[data-icon="insights"]').forEach((el) => setIcon(el, ICONS.insights));
  document.querySelectorAll('[data-icon="activity"]').forEach((el) => setIcon(el, ICONS.activity));
  document.querySelectorAll('[data-icon="profile"]').forEach((el) => setIcon(el, ICONS.profile));
  setIcon(document.getElementById('logoutBtn'), ICONS.logout);
  setIcon(document.getElementById('linkTelegramBtn'), ICONS.telegram);
  setIcon(document.getElementById('pushToggleBtn'), ICONS.bellOff);
}

async function loadVapidKey() {
  try {
    const data = await fetchJSON('/api/push/vapid-key');
    VAPID_PUBLIC_KEY = data.public_key;
  } catch (_) {}
}

function getToken() {
  return localStorage.getItem('np_token');
}

function setToken(t) {
  localStorage.setItem('np_token', t);
}

function clearToken() {
  localStorage.removeItem('np_token');
}

async function fetchJSON(url, opts = {}) {
  const headers = { ...opts.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    showAuth();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

function fmtINR(n) {
  if (n == null || Number.isNaN(Number(n))) return '—';
  return `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtCompactINR(n) {
  if (n == null || Number.isNaN(Number(n))) return '—';
  const value = Number(n);
  if (Math.abs(value) >= 10000000) return `₹${(value / 10000000).toFixed(2)}Cr`;
  if (Math.abs(value) >= 100000) return `₹${(value / 100000).toFixed(2)}L`;
  return fmtINR(value);
}

function fmtDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function escHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function panicColor(score) {
  if (score >= 80) return '#f2b0a0';
  if (score >= 50) return '#f2e0b2';
  return '#ded6c8';
}

function setPushUI(enabled) {
  pushEnabled = enabled;
  const btn = document.getElementById('pushToggleBtn');
  const profileBtn = document.getElementById('profilePushBtn');
  const profileStatus = document.getElementById('profilePushStatus');
  setIcon(btn, enabled ? ICONS.bellOn : ICONS.bellOff);
  btn.title = enabled ? 'Disable Push' : 'Enable Push';
  btn.setAttribute('aria-label', btn.title);
  if (profileBtn) {
    profileBtn.textContent = enabled ? 'Disable Push Alerts' : 'Enable Push Alerts';
  }
  if (profileStatus) {
    profileStatus.textContent = enabled ? 'Enabled' : 'Disabled';
  }
}

function setTelegramUI(hasTelegram) {
  const btn = document.getElementById('linkTelegramBtn');
  const profileStatus = document.getElementById('profileTelegramStatus');
  if (hasTelegram) {
    setIcon(btn, ICONS.linked);
    btn.title = 'Telegram Linked';
    btn.setAttribute('aria-label', 'Telegram Linked');
    profileStatus.textContent = 'Linked';
    document.getElementById('telegramBanner').hidden = true;
  } else {
    setIcon(btn, ICONS.telegram);
    btn.title = 'Link Telegram';
    btn.setAttribute('aria-label', 'Link Telegram');
    profileStatus.textContent = 'Not linked';
  }
}

function showAuth() {
  document.getElementById('authView').hidden = false;
  document.getElementById('dashboardView').hidden = true;
  clearToken();
  currentUser = null;
}

function showDashboard() {
  document.getElementById('authView').hidden = true;
  document.getElementById('dashboardView').hidden = false;
  if (currentUser) {
    document.getElementById('headerUser').textContent = currentUser.username;
    document.getElementById('profileUsername').textContent = currentUser.username;
  }
  activateTab('overview');
  loadOverview();
  showTelegramPrompt();
}

function activateTab(tabName) {
  document.querySelectorAll('.nav-link, .dock-link').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-pane').forEach((pane) => {
    pane.classList.toggle('active', pane.id === `tab-${tabName}`);
  });

  if (tabName === 'overview') loadOverview();
  if (tabName === 'holdings') loadPortfolio();
  if (tabName === 'insights') loadHeadlines();
  if (tabName === 'activity') loadTrades();
  if (tabName === 'profile') loadProfile();
}

document.querySelectorAll('.auth-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.auth-tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    const form = tab.dataset.auth;
    document.getElementById('loginForm').hidden = form !== 'login';
    document.getElementById('signupForm').hidden = form !== 'signup';
  });
});

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('loginError');
  errEl.textContent = '';
  try {
    const data = await fetchJSON('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username: document.getElementById('loginUsername').value,
        password: document.getElementById('loginPassword').value,
      }),
    });
    setToken(data.token);
    currentUser = { user_id: data.user_id, username: data.username };
    showDashboard();
    generateTelegramLink();
  } catch (err) {
    errEl.textContent = err.message;
  }
});

document.getElementById('signupForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('signupError');
  errEl.textContent = '';
  try {
    const data = await fetchJSON('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        username: document.getElementById('signupUsername').value,
        password: document.getElementById('signupPassword').value,
      }),
    });
    setToken(data.token);
    currentUser = { user_id: data.user_id, username: data.username };
    showDashboard();
    generateTelegramLink();
  } catch (err) {
    errEl.textContent = err.message;
  }
});

document.getElementById('logoutBtn').addEventListener('click', () => showAuth());

document.querySelectorAll('.nav-link, .dock-link').forEach((btn) => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

document.getElementById('headlineTabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.filter-pill');
  if (!btn) return;
  document.querySelectorAll('#headlineTabs .filter-pill').forEach((pill) => pill.classList.remove('active'));
  btn.classList.add('active');
  currentFilter = btn.dataset.filter;
  loadHeadlines();
});

async function generateTelegramLink() {
  try {
    const data = await fetchJSON('/auth/generate-link-code', { method: 'POST' });
    telegramDeepLinkUrl = data.deep_link || '';
    return data;
  } catch (_) {
    telegramDeepLinkUrl = '';
    return null;
  }
}

async function openTelegramDirect() {
  const btn = document.getElementById('linkTelegramBtn');
  btn.disabled = true;
  const data = await generateTelegramLink();
  btn.disabled = false;
  if (data && data.deep_link) {
    window.open(data.deep_link, '_blank');
  } else {
    openTelegramModal();
  }
}

function openTelegramModal() {
  document.getElementById('telegramModal').hidden = false;
  document.getElementById('linkCodeBox').hidden = true;
  document.getElementById('telegramInstructions').textContent = 'Generate a secure linking code to connect this dashboard to your Telegram chat.';
  document.getElementById('telegramExtra').textContent = '';
  document.getElementById('telegramDeepLink').hidden = true;
  document.getElementById('generateLinkBtn').hidden = false;
}

document.getElementById('linkTelegramBtn').addEventListener('click', openTelegramDirect);
document.getElementById('profileLinkTelegramBtn').addEventListener('click', openTelegramModal);

document.querySelectorAll('.modal-close').forEach((el) => {
  el.addEventListener('click', () => {
    el.closest('.modal').hidden = true;
  });
});

document.querySelectorAll('.modal').forEach((modal) => {
  modal.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) modal.hidden = true;
  });
});

document.getElementById('generateLinkBtn').addEventListener('click', async () => {
  try {
    const data = await generateTelegramLink();
    if (!data) throw new Error('Failed to generate code');
    document.getElementById('linkCodeBox').hidden = false;
    document.getElementById('linkCodeValue').textContent = data.code;
    document.getElementById('generateLinkBtn').hidden = true;
    document.getElementById('telegramInstructions').textContent = 'Open Telegram and use this secure link code to complete pairing.';
    document.getElementById('telegramExtra').textContent = `If deep linking fails, message the bot manually with: /link ${data.code}`;
    const deepLink = document.getElementById('telegramDeepLink');
    if (data.deep_link) {
      deepLink.href = data.deep_link;
      deepLink.hidden = false;
      deepLink.textContent = 'Open Telegram Bot';
    } else {
      deepLink.hidden = true;
    }
  } catch (err) {
    document.getElementById('telegramInstructions').textContent = `Error: ${err.message}`;
  }
});

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  installPrompt = e;
  document.getElementById('installBanner').hidden = false;
});

document.getElementById('installBtn').addEventListener('click', async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  const result = await installPrompt.userChoice;
  if (result.outcome === 'accepted') document.getElementById('installBanner').hidden = true;
  installPrompt = null;
});

document.getElementById('installDismiss').addEventListener('click', () => {
  document.getElementById('installBanner').hidden = true;
});

async function getPushSubscription() {
  try {
    const reg = await navigator.serviceWorker.ready;
    return await reg.pushManager.getSubscription();
  } catch (_) {
    return null;
  }
}

async function subscribePush() {
  if (!VAPID_PUBLIC_KEY) await loadVapidKey();
  if (!VAPID_PUBLIC_KEY) {
    alert('Could not load push configuration.');
    return;
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(VAPID_PUBLIC_KEY),
    });
    await fetchJSON('/api/push/subscribe', {
      method: 'POST',
      body: JSON.stringify(sub.toJSON()),
    });
    setPushUI(true);
  } catch (err) {
    alert(`Failed to enable push: ${err.message}`);
  }
}

async function unsubscribePush() {
  try {
    const sub = await getPushSubscription();
    if (sub) await sub.unsubscribe();
    await fetchJSON('/api/push/unsubscribe', { method: 'POST' });
    setPushUI(false);
  } catch (err) {
    console.error('Push unsubscribe error:', err);
  }
}

document.getElementById('pushToggleBtn').addEventListener('click', async () => {
  if (pushEnabled) {
    await unsubscribePush();
  } else {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      await subscribePush();
    } else {
      alert('Notification permission denied.');
    }
  }
});

document.getElementById('profilePushBtn').addEventListener('click', async () => {
  if (pushEnabled) {
    await unsubscribePush();
  } else {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') await subscribePush();
  }
});

async function restorePushState() {
  const sub = await getPushSubscription();
  setPushUI(Boolean(sub));
}

async function showTelegramPrompt() {
  try {
    const stats = await fetchJSON('/api/stats');
    setTelegramUI(Boolean(stats.has_telegram));
    if (!stats.has_telegram && localStorage.getItem('np_telegram_dismissed') !== 'true') {
      document.getElementById('telegramBanner').hidden = false;
    }
    if (!telegramDeepLinkUrl) await generateTelegramLink();
  } catch (_) {}
}

document.getElementById('telegramBannerBtn').addEventListener('click', () => {
  document.getElementById('telegramBanner').hidden = true;
  openTelegramDirect();
});

document.getElementById('telegramBannerDismiss').addEventListener('click', () => {
  document.getElementById('telegramBanner').hidden = true;
  localStorage.setItem('np_telegram_dismissed', 'true');
});

document.getElementById('importBtn').addEventListener('click', () => {
  document.getElementById('importModal').hidden = false;
  document.getElementById('importResult').hidden = true;
});

document.querySelectorAll('.import-tabs .filter-pill').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.import-tabs .filter-pill').forEach((pill) => pill.classList.remove('active'));
    tab.classList.add('active');
    const pane = tab.dataset.import;
    document.getElementById('importFile').hidden = pane !== 'file';
    document.getElementById('importPaste').hidden = pane !== 'paste';
  });
});

document.getElementById('importSubmitBtn').addEventListener('click', async () => {
  const fileInput = document.getElementById('csvFileInput');
  const pasteArea = document.getElementById('csvPasteArea');
  const resultEl = document.getElementById('importResult');
  resultEl.hidden = true;

  try {
    let body;
    let headers = {};
    const fileTabActive = document.querySelector('.import-tabs .filter-pill.active[data-import="file"]');

    if (fileTabActive) {
      if (!fileInput.files || !fileInput.files[0]) {
        resultEl.className = 'import-result error';
        resultEl.textContent = 'Select a CSV file before importing.';
        resultEl.hidden = false;
        return;
      }
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      body = formData;
    } else {
      const csv = pasteArea.value.trim();
      if (!csv) {
        resultEl.className = 'import-result error';
        resultEl.textContent = 'Paste CSV content before importing.';
        resultEl.hidden = false;
        return;
      }
      body = JSON.stringify({ csv });
      headers['Content-Type'] = 'application/json';
    }

    const res = await fetch('/api/portfolio/import', {
      method: 'POST',
      headers: { ...headers, Authorization: `Bearer ${getToken()}` },
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      resultEl.className = 'import-result error';
      resultEl.textContent = data.errors ? data.errors.join('; ') : data.error || 'Import failed';
      resultEl.hidden = false;
      return;
    }

    resultEl.className = 'import-result success';
    resultEl.textContent = `Imported ${data.count} holdings using ${data.format} format.`;
    resultEl.hidden = false;
    document.getElementById('importModal').hidden = true;
    loadPortfolio();
    loadOverview();
  } catch (err) {
    resultEl.className = 'import-result error';
    resultEl.textContent = err.message;
    resultEl.hidden = false;
  }
});

document.getElementById('refreshPricesBtn').addEventListener('click', async () => {
  const btn = document.getElementById('refreshPricesBtn');
  const original = btn.textContent;
  btn.textContent = 'Refreshing';
  btn.disabled = true;
  try {
    const data = await fetchJSON('/api/portfolio/refresh-prices', { method: 'POST' });
    btn.textContent = `Updated ${data.updated}`;
    loadPortfolio();
    loadOverview();
  } catch (_) {
    btn.textContent = 'Refresh Failed';
  } finally {
    setTimeout(() => {
      btn.textContent = original;
      btn.disabled = false;
    }, 2200);
  }
});

function renderPerformanceChart(history) {
  const canvas = document.getElementById('performanceChart');
  if (!canvas || typeof Chart === 'undefined') return;

  const labels = history.map((point, idx) => {
    if (point.timestamp === 'start') return 'Start';
    return idx === history.length - 1 ? 'Now' : new Date(point.timestamp).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  });
  const values = history.map((point) => Number(point.total || 0));
  const lineColor = '#f2ebdd';

  if (performanceChart) performanceChart.destroy();

  performanceChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: lineColor,
        borderWidth: 2,
        pointRadius: Math.min(4, Math.max(2, Math.floor(24 / Math.max(values.length, 6)))),
        pointHoverRadius: 5,
        pointBackgroundColor: '#f2ebdd',
        pointBorderColor: '#c6ad76',
        pointBorderWidth: 1.2,
        tension: 0.42,
        fill: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          displayColors: false,
          backgroundColor: 'rgba(24, 22, 19, 0.96)',
          borderColor: 'rgba(221, 192, 130, 0.2)',
          borderWidth: 1,
          titleColor: '#f2ebdd',
          bodyColor: '#f2ebdd',
          callbacks: {
            label: (ctx) => fmtINR(ctx.raw),
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: 'rgba(179, 171, 158, 0.72)',
            maxRotation: 0,
            autoSkip: true,
            font: { size: 11, family: 'Manrope' },
          },
          grid: { display: false },
          border: { display: false },
        },
        y: {
          ticks: {
            color: 'rgba(179, 171, 158, 0.72)',
            callback: (value) => fmtCompactINR(value),
            font: { size: 11, family: 'Manrope' },
          },
          grid: {
            color: 'rgba(255,255,255,0.06)',
            drawBorder: false,
          },
          border: { display: false },
        },
      },
    },
  });
}

function renderCoreHoldings(holdings) {
  const strip = document.getElementById('coreHoldingsStrip');
  strip.innerHTML = '';
  if (!holdings || holdings.length === 0) {
    strip.innerHTML = '<p class="empty-msg">No holdings available yet.</p>';
    return;
  }

  holdings
    .slice()
    .sort((a, b) => (b.current_value || 0) - (a.current_value || 0))
    .slice(0, 4)
    .forEach((holding) => {
      const card = document.createElement('article');
      card.className = 'core-card';
      const pnlClass = holding.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
      card.innerHTML = `
        <div class="core-top">
          <div class="holding-avatar">${ICONS.holding}</div>
          <div class="core-value">${fmtCompactINR(holding.current_value)}</div>
        </div>
        <div>
          <strong class="core-symbol">${escHtml(holding.symbol)}</strong>
          <div class="core-name">Average ${fmtINR(holding.avg_price)}</div>
        </div>
        <div class="core-meta">Qty ${holding.qty}</div>
        <div class="core-pnl ${pnlClass}">${holding.pnl >= 0 ? '+' : ''}${holding.pnl_pct}%</div>
      `;
      strip.appendChild(card);
    });
}

async function loadOverview() {
  try {
    const [portfolio, stats, history] = await Promise.all([
      fetchJSON('/api/portfolio'),
      fetchJSON('/api/stats'),
      fetchJSON('/api/portfolio-history'),
    ]);

    document.getElementById('portfolioTotal').textContent = fmtINR(portfolio.total_value);
    document.getElementById('portfolioCash').textContent = fmtINR(portfolio.cash);

    const pnl = Number(portfolio.total_pnl || 0);
    const invested = Math.max(1, Number(portfolio.total_invested || 0));
    const pnlPct = ((pnl / invested) * 100);
    const pnlEl = document.getElementById('portfolioPnl');
    pnlEl.textContent = `${pnl >= 0 ? '+' : ''}${fmtINR(pnl)}`;
    pnlEl.className = `metric-value ${pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;

    document.getElementById('portfolioChangePct').textContent = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`;
    document.getElementById('portfolioDeltaValue').textContent = `${pnl >= 0 ? '+' : ''}${fmtINR(pnl)} YTD`;

    document.getElementById('statsHeadlinesToday').textContent = stats.headlines_today ?? '—';
    document.getElementById('statsTradesCount').textContent = stats.trades_count ?? '—';
    document.getElementById('statsPendingCount').textContent = stats.pending_count ?? '—';
    document.getElementById('statsHoldingsCount').textContent = stats.holdings_count ?? '—';

    renderCoreHoldings(portfolio.holdings || []);
    renderPerformanceChart(history || []);
    setTelegramUI(Boolean(stats.has_telegram));
  } catch (err) {
    console.error('loadOverview error:', err);
  }
}

async function loadPortfolio() {
  try {
    const portfolio = await fetchJSON('/api/portfolio');
    const list = document.getElementById('holdingsList');
    const empty = document.getElementById('holdingsEmpty');
    list.innerHTML = '';

    if (!portfolio.holdings || portfolio.holdings.length === 0) {
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    portfolio.holdings.forEach((holding) => {
      const card = document.createElement('article');
      card.className = 'holding-card';
      const pnlClass = holding.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
      card.innerHTML = `
        <div class="holding-head">
          <div class="holding-title">
            <div class="holding-avatar">${ICONS.holding}</div>
            <div>
              <div class="holding-symbol">${escHtml(holding.symbol)}</div>
              <div class="core-name">Tracked portfolio position</div>
            </div>
          </div>
          <div class="core-value">${fmtINR(holding.current_value)}</div>
        </div>
        <div class="holding-grid">
          <div class="holding-detail"><span class="label">Quantity</span><span class="value">${holding.qty}</span></div>
          <div class="holding-detail"><span class="label">Average</span><span class="value">${fmtINR(holding.avg_price)}</span></div>
          <div class="holding-detail"><span class="label">Current</span><span class="value">${fmtINR(holding.current_price)}</span></div>
          <div class="holding-detail"><span class="label">Invested</span><span class="value">${fmtINR(holding.invested)}</span></div>
        </div>
        <div class="holding-pnl">
          <div class="metric-label">Position Return</div>
          <div class="${pnlClass}">
            <div class="pnl-value">${holding.pnl >= 0 ? '+' : ''}${fmtINR(holding.pnl)}</div>
            <div class="pnl-pct">${holding.pnl_pct >= 0 ? '+' : ''}${holding.pnl_pct}%</div>
          </div>
        </div>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    console.error('loadPortfolio error:', err);
  }
}

async function loadHeadlines() {
  try {
    const headlines = await fetchJSON(`/api/headlines?filter=${currentFilter}`);
    const list = document.getElementById('headlinesList');
    list.innerHTML = '';

    if (!headlines.length) {
      list.innerHTML = '<p class="empty-msg">No headlines yet.</p>';
      return;
    }

    headlines.slice(0, 100).forEach((headline) => {
      const item = document.createElement('article');
      item.className = 'headline-item';
      item.innerHTML = `
        <div class="headline-source-icon">${ICONS.source}</div>
        <div class="headline-body">
          <div class="headline-topline">
            <span class="headline-pill ${headline.importance}">${headline.importance}</span>
            <div class="headline-meta">${escHtml(headline.company || 'Market')} · ${escHtml(headline.source)} · ${fmtDate(headline.timestamp)}</div>
          </div>
          <div class="headline-text">${escHtml(headline.headline)}</div>
        </div>
        <div class="headline-score">
          <strong style="color:${panicColor(headline.panic_score)}">${headline.panic_score}</strong>
          <span>${escHtml(headline.action)}</span>
        </div>
      `;
      list.appendChild(item);
    });
  } catch (err) {
    console.error('loadHeadlines error:', err);
  }
}

async function loadTrades() {
  try {
    const trades = await fetchJSON('/api/trades');
    const tbody = document.getElementById('tradesBody');
    const empty = document.getElementById('tradesEmpty');
    tbody.innerHTML = '';

    if (!trades.length) {
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    trades.forEach((trade) => {
      const tr = document.createElement('tr');
      const actionClass = `action-${(trade.action || '').toLowerCase()}`;
      const statusClass = `status-${(trade.status || '').toLowerCase()}`;
      tr.innerHTML = `
        <td>${fmtDate(trade.timestamp)}</td>
        <td>${escHtml(trade.company)}</td>
        <td>${escHtml(trade.symbol)}</td>
        <td class="${actionClass}">${escHtml(trade.action || '')}</td>
        <td>${trade.quantity || ''}</td>
        <td>${fmtINR(trade.estimated_value_inr)}</td>
        <td class="${statusClass}">${escHtml(trade.status || '')}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('loadTrades error:', err);
  }
}

async function loadProfile() {
  try {
    const [me, pending] = await Promise.all([
      fetchJSON('/auth/me'),
      fetchJSON('/api/pending'),
    ]);

    document.getElementById('profileUsername').textContent = me.username;
    setTelegramUI(Boolean(me.has_telegram));

    const list = document.getElementById('pendingList');
    list.innerHTML = '';

    if (!pending.length) {
      list.innerHTML = '<p class="empty-msg">No pending approvals or queued signals.</p>';
      return;
    }

    pending.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'pending-card';
      const analysis = item.analysis || {};
      const validation = item.validation || {};
      card.innerHTML = `
        <div class="pending-icon">${ICONS.pending}</div>
        <div>
          <div class="pending-title">${escHtml(analysis.company || 'Market')} · ${escHtml(analysis.action || 'Pending')}</div>
          <div class="pending-headline">${escHtml((item.news_item || {}).headline || '')}</div>
          <div class="pending-meta">
            <span>Panic ${analysis.panic_score ?? '—'}</span>
            <span>Qty ${validation.quantity ?? '—'}</span>
            <span>${fmtDate(item.created_at || item.timestamp)}</span>
          </div>
        </div>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    console.error('loadProfile error:', err);
  }
}

(async () => {
  hydrateStaticIcons();
  await loadVapidKey();
  const token = getToken();

  if (token) {
    try {
      const me = await fetchJSON('/auth/me');
      currentUser = { user_id: me.user_id, username: me.username };
      showDashboard();
      restorePushState();
      generateTelegramLink();
      return;
    } catch (_) {
      clearToken();
    }
  }

  showAuth();
})();
