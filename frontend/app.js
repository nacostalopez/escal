const API_BASE = window.location.hostname === "" || window.location.protocol === "file:"
  ? "http://localhost:8000"
  : `${window.location.protocol}//${window.location.hostname}:8000`;

const state = {
  token: localStorage.getItem("escal_token") || null,
  refreshToken: localStorage.getItem("escal_refresh_token") || null,
  account: null,
  stores: [],
  activeStoreId: null,
};

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

// Concurrent 401s (e.g. metrics + connector health firing together) must
// share one in-flight refresh instead of racing to rotate the token twice —
// the second rotation would revoke the first one's brand-new refresh token.
let refreshPromise = null;

async function refreshAccessToken() {
  if (!state.refreshToken) throw new Error("No refresh token");
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error((data && data.detail) || "Session expired");
        setTokens(data.access_token, data.refresh_token);
        return data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function api(path, { method = "GET", body, auth = true, _retried = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && !_retried && state.refreshToken) {
    try {
      await refreshAccessToken();
    } catch (err) {
      sessionExpired();
      throw err;
    }
    return api(path, { method, body, auth, _retried: true });
  }

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data && data.detail) || `${res.status} ${res.statusText}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

// ---------------------------------------------------------------------------
// Auth view
// ---------------------------------------------------------------------------

const authView = document.getElementById("auth-view");
const dashboardView = document.getElementById("dashboard-view");
const topbarAccount = document.getElementById("topbar-account");
const authError = document.getElementById("auth-error");

document.getElementById("tab-login").addEventListener("click", () => switchAuthTab("login"));
document.getElementById("tab-register").addEventListener("click", () => switchAuthTab("register"));

function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("tab-login").classList.toggle("active", isLogin);
  document.getElementById("tab-register").classList.toggle("active", !isLogin);
  document.getElementById("login-form").hidden = !isLogin;
  document.getElementById("register-form").hidden = isLogin;
  authError.hidden = true;
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.hidden = true;
  try {
    const data = await api("/auth/login", {
      auth: false,
      method: "POST",
      body: {
        email: document.getElementById("login-email").value,
        password: document.getElementById("login-password").value,
      },
    });
    setTokens(data.access_token, data.refresh_token);
    await enterDashboard();
  } catch (err) {
    showAuthError(err.message);
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.hidden = true;
  try {
    const data = await api("/auth/register", {
      auth: false,
      method: "POST",
      body: {
        account_name: document.getElementById("register-account-name").value,
        email: document.getElementById("register-email").value,
        password: document.getElementById("register-password").value,
      },
    });
    setTokens(data.access_token, data.refresh_token);
    await enterDashboard();
  } catch (err) {
    showAuthError(err.message);
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  const refreshToken = state.refreshToken;
  try {
    if (refreshToken) {
      await api("/auth/logout", { method: "POST", body: { refresh_token: refreshToken } });
    }
  } catch (err) {
    // Best-effort revoke — log out locally regardless of whether the
    // server call succeeded (e.g. token already expired/rotated).
  } finally {
    setTokens(null, null);
    showLoggedOut();
  }
});

function showAuthError(message) {
  authError.textContent = message;
  authError.hidden = false;
}

function showLoggedOut() {
  state.account = null;
  state.stores = [];
  state.activeStoreId = null;
  authView.hidden = false;
  dashboardView.hidden = true;
  topbarAccount.hidden = true;
}

function sessionExpired() {
  showLoggedOut();
  switchAuthTab("login");
  showAuthError("Your session expired — please log in again.");
}

function setTokens(accessToken, refreshToken) {
  state.token = accessToken;
  state.refreshToken = refreshToken;
  if (accessToken) localStorage.setItem("escal_token", accessToken);
  else localStorage.removeItem("escal_token");
  if (refreshToken) localStorage.setItem("escal_refresh_token", refreshToken);
  else localStorage.removeItem("escal_refresh_token");
}

// ---------------------------------------------------------------------------
// Dashboard shell
// ---------------------------------------------------------------------------

async function enterDashboard() {
  state.account = await api("/accounts/me");
  document.getElementById("account-name").textContent = state.account.name;
  topbarAccount.hidden = false;
  authView.hidden = true;
  dashboardView.hidden = false;

  await loadStores();
}

async function loadStores() {
  state.stores = await api("/stores");
  renderStoreList();

  if (state.stores.length === 0) {
    document.getElementById("empty-state").hidden = false;
    document.getElementById("store-panel").hidden = true;
    return;
  }

  document.getElementById("empty-state").hidden = true;
  if (!state.activeStoreId || !state.stores.find((s) => s.id === state.activeStoreId)) {
    state.activeStoreId = state.stores[0].id;
  }
  await selectStore(state.activeStoreId);
}

function renderStoreList() {
  const list = document.getElementById("store-list");
  list.innerHTML = "";
  for (const store of state.stores) {
    const li = document.createElement("li");
    li.textContent = store.name;
    li.className = store.id === state.activeStoreId ? "active" : "";
    li.addEventListener("click", () => selectStore(store.id));
    list.appendChild(li);
  }
}

async function selectStore(storeId) {
  state.activeStoreId = storeId;
  renderStoreList();
  document.getElementById("store-panel").hidden = false;

  const store = state.stores.find((s) => s.id === storeId);
  document.getElementById("store-name").textContent = store.name;
  document.getElementById("store-meta").textContent = `${store.platform} · ${store.currency}`;

  await refreshMetrics();
  await refreshConnectorHealth();
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

document.getElementById("range-select").addEventListener("change", refreshMetrics);

function dateRange() {
  const days = Number(document.getElementById("range-select").value);
  const end = new Date();
  const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
  return { start: start.toISOString(), end: end.toISOString() };
}

function fmtMoney(n) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n || 0);
}

async function refreshMetrics() {
  if (!state.activeStoreId) return;
  const { start, end } = dateRange();
  const qs = `start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;

  const [summary, daily] = await Promise.all([
    api(`/stores/${state.activeStoreId}/metrics/summary?${qs}`),
    api(`/stores/${state.activeStoreId}/metrics/daily?${qs}`),
  ]);

  document.getElementById("metrics-empty").hidden = summary.revenue > 0;

  document.getElementById("stat-revenue").textContent = fmtMoney(summary.revenue);
  document.getElementById("stat-net-profit").textContent = fmtMoney(summary.net_profit);
  document.getElementById("stat-ad-spend").textContent = fmtMoney(summary.total_ad_spend);

  const realProfitEl = document.getElementById("stat-real-profit");
  realProfitEl.textContent = fmtMoney(summary.real_profit_after_ads);
  realProfitEl.className = "stat-value " + (summary.real_profit_after_ads >= 0 ? "positive" : "negative");

  document.getElementById("stat-roas").textContent =
    summary.true_roas === null || summary.true_roas === undefined ? "—" : `${summary.true_roas}x`;

  renderChart(daily);
}

function renderChart(daily) {
  const container = document.getElementById("chart-container");
  if (!daily.length) {
    container.innerHTML = '<div class="chart-empty">No daily data in this range yet.</div>';
    return;
  }

  const width = 720;
  const height = 220;
  const padding = 28;
  const barGroupWidth = (width - padding * 2) / daily.length;
  const barWidth = Math.min(18, barGroupWidth / 3);

  const maxVal = Math.max(1, ...daily.map((d) => Math.max(d.total_revenue, d.ad_spend)));
  const scale = (v) => (height - padding) - (v / maxVal) * (height - padding * 1.5);

  let bars = "";
  let labels = "";
  daily.forEach((d, i) => {
    const groupX = padding + i * barGroupWidth;
    const revY = scale(d.total_revenue);
    const spendY = scale(d.ad_spend);
    bars += `<rect x="${groupX}" y="${revY}" width="${barWidth}" height="${(height - padding) - revY}" fill="#2263A2" rx="2"></rect>`;
    bars += `<rect x="${groupX + barWidth + 3}" y="${spendY}" width="${barWidth}" height="${(height - padding) - spendY}" fill="#1A2B4A" rx="2"></rect>`;
    if (i % Math.ceil(daily.length / 8 || 1) === 0) {
      labels += `<text x="${groupX}" y="${height - 8}" font-size="10" fill="#5c6987">${String(d.day).slice(5)}</text>`;
    }
  });

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}">
      <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#dbe3ee"></line>
      ${bars}
      ${labels}
    </svg>
    <div style="display:flex;gap:16px;font-size:12px;color:#5c6987;margin-top:6px;">
      <span><span style="display:inline-block;width:9px;height:9px;background:#2263A2;border-radius:2px;margin-right:4px;"></span>Revenue</span>
      <span><span style="display:inline-block;width:9px;height:9px;background:#1A2B4A;border-radius:2px;margin-right:4px;"></span>Ad spend</span>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Connector health
// ---------------------------------------------------------------------------

async function refreshConnectorHealth() {
  const grid = document.getElementById("connector-status");
  const health = await api(`/stores/${state.activeStoreId}/connectors/health`);
  const providers = ["shopify", "meta", "google"];

  grid.innerHTML = providers
    .map((provider) => {
      const info = health[provider];
      let dotClass = "none";
      let statusText = "Not connected";
      if (info) {
        dotClass = info.last_error ? "error" : "ok";
        statusText = info.last_error
          ? `Error: ${info.last_error}`
          : `Last synced ${info.last_synced_at ? new Date(info.last_synced_at).toLocaleString() : "—"}`;
      }
      return `
        <div class="connector-card">
          <div class="connector-name"><span class="connector-dot ${dotClass}"></span>${provider}</div>
          <div class="muted">${statusText}</div>
        </div>
      `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// New store modal
// ---------------------------------------------------------------------------

const newStoreModal = document.getElementById("new-store-modal");
document.getElementById("new-store-btn").addEventListener("click", () => (newStoreModal.hidden = false));
document.getElementById("empty-new-store-btn").addEventListener("click", () => (newStoreModal.hidden = false));
document.getElementById("new-store-cancel").addEventListener("click", () => (newStoreModal.hidden = true));

document.getElementById("new-store-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const store = await api("/stores", {
    method: "POST",
    body: {
      name: document.getElementById("new-store-name").value,
      platform: document.getElementById("new-store-platform").value,
      currency: document.getElementById("new-store-currency").value || "USD",
    },
  });
  newStoreModal.hidden = true;
  document.getElementById("new-store-form").reset();
  document.getElementById("new-store-currency").value = "USD";
  await loadStores();
  await selectStore(store.id);
});

// ---------------------------------------------------------------------------
// Seed demo data (mirrors scripts/seed_demo.py, run from the browser)
// ---------------------------------------------------------------------------

document.getElementById("seed-btn").addEventListener("click", async () => {
  const btn = document.getElementById("seed-btn");
  btn.disabled = true;
  btn.textContent = "Seeding…";
  try {
    await seedDemoData(state.activeStoreId);
    await refreshMetrics();
  } catch (err) {
    alert(`Seeding failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Seed demo data";
  }
});

async function seedDemoData(storeId) {
  await api(`/stores/${storeId}/products`, {
    method: "PUT",
    body: [
      { external_id: "sku-1", sku: "SKU1", title: "T-Shirt", cogs: 5.0, shipping_cost: 2.0 },
      { external_id: "sku-2", sku: "SKU2", title: "Hoodie", cogs: 12.0, shipping_cost: 3.0 },
    ],
  });

  const now = Date.now();
  const orders = [];
  for (let dayOffset = 0; dayOffset < 14; dayOffset++) {
    const dayCount = 3 + Math.floor(Math.random() * 8);
    for (let i = 0; i < dayCount; i++) {
      const gross = Math.round((20 + Math.random() * 130) * 100) / 100;
      const time = new Date(now - dayOffset * 86400000 - Math.random() * 86400000);
      orders.push({
        time: time.toISOString(),
        order_id: `order-${dayOffset}-${Math.floor(Math.random() * 9000 + 1000)}`,
        gross_amount: gross,
        discounts: 0,
        shipping_fee: 4.99,
        payment_gateway_fee: Math.round((gross * 0.029 + 0.3) * 100) / 100,
        cogs_total: Math.round(gross * 0.25 * 100) / 100,
        currency: "USD",
        attribution_utm_source: ["meta", "google", "organic"][Math.floor(Math.random() * 3)],
        attribution_utm_campaign: "demo-campaign",
      });
    }
  }
  await api(`/stores/${storeId}/orders`, { method: "POST", body: orders });

  const adSpend = [];
  for (let dayOffset = 0; dayOffset < 14; dayOffset++) {
    const day = new Date(now - dayOffset * 86400000);
    day.setHours(0, 0, 0, 0);
    for (const platform of ["meta", "google"]) {
      adSpend.push({
        time: day.toISOString(),
        platform,
        campaign_id: `${platform}-demo-campaign`,
        campaign_name: "Demo Campaign",
        adset_id: "adset-1",
        spend: Math.round((20 + Math.random() * 60) * 100) / 100,
        impressions: Math.floor(1000 + Math.random() * 4000),
        clicks: Math.floor(50 + Math.random() * 250),
      });
    }
  }
  await api(`/stores/${storeId}/ad-spend`, { method: "POST", body: adSpend });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

(async function boot() {
  if (!state.token && !state.refreshToken) return;
  try {
    await enterDashboard();
  } catch (err) {
    setTokens(null, null);
  }
})();
