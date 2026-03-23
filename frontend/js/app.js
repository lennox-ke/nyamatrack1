/**
 * NyamaTrack — app.js
 * Single shared script: config, auth (with token refresh), nav, toasts, utilities.
 * Load this INSTEAD of config.js and nav.js on every page.
 * Keep config.js in place too — it's referenced by login.html before app.js loads.
 */

// ─────────────────────────────────────────────────────────────────
// CONFIG  (mirrors config.js so both work)
// ─────────────────────────────────────────────────────────────────
const CONFIG = window.CONFIG || (() => {
  const cfg = {
    DEV_API_URL:  'http://localhost:8000/api',
    PROD_API_URL: 'https://nyamatrack1.onrender.com/api',
    get API_URL() {
      return (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? this.DEV_API_URL
        : this.PROD_API_URL;
    },
    APP_NAME:    'NyamaTrack',
    APP_VERSION: '1.0.0',
    DEFAULT_LOW_STOCK_THRESHOLD: 5.0,
    DEFAULT_SPOILAGE_DAYS: 3,
    ITEMS_PER_PAGE: 20,
  };
  window.CONFIG = cfg;
  return cfg;
})();

// ─────────────────────────────────────────────────────────────────
// AUTH — token storage + automatic refresh on 401
// ─────────────────────────────────────────────────────────────────
const Auth = {
  getToken()        { return localStorage.getItem('access_token'); },
  getRefreshToken() { return localStorage.getItem('refresh_token'); },

  setTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    if (refresh) localStorage.setItem('refresh_token', refresh);
  },

  clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
  },

  isAuthenticated() { return !!this.getToken(); },

  async refreshAccessToken() {
    const refresh = this.getRefreshToken();
    if (!refresh) { this.logout(); return false; }
    try {
      const res = await fetch(`${CONFIG.API_URL}/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh })
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('access_token', data.access);
        // If server rotated the refresh token, save the new one
        if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
        return true;
      } else {
        this.logout(); return false;
      }
    } catch { this.logout(); return false; }
  },

  logout() {
    this.clearTokens();
    window.location.href = 'login.html';
  },

  getAuthHeaders() {
    return {
      'Authorization': `Bearer ${this.getToken()}`,
      'Content-Type': 'application/json'
    };
  }
};

// ─────────────────────────────────────────────────────────────────
// API REQUEST — wraps fetch, auto-refreshes expired tokens once
// ─────────────────────────────────────────────────────────────────
async function apiRequest(endpoint, options = {}) {
  const url = `${CONFIG.API_URL}${endpoint}`;
  if (!options.headers) options.headers = Auth.getAuthHeaders();

  let res = await fetch(url, options);

  if (res.status === 401) {
    const ok = await Auth.refreshAccessToken();
    if (ok) {
      options.headers = Auth.getAuthHeaders();
      res = await fetch(url, options);
    } else {
      throw new Error('Session expired — please log in again');
    }
  }

  if (!res.ok) {
    let errMsg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      errMsg = err.detail || err.error || errMsg;
    } catch {}
    throw new Error(errMsg);
  }

  // 204 No Content
  if (res.status === 204) return null;
  return res.json();
}

// ─────────────────────────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ─────────────────────────────────────────────────────────────────
const Toast = {
  _icons: { success:'check-circle', error:'exclamation-circle', warning:'exclamation-triangle', info:'info-circle' },

  show(message, type = 'success', duration = 3200) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas fa-${this._icons[type] || 'info-circle'}"></i><span>${message}</span>`;
    container.appendChild(t);
    setTimeout(() => t.remove(), duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg)   { this.show(msg, 'error'); },
  warning(msg) { this.show(msg, 'warning'); },
  info(msg)    { this.show(msg, 'info'); },
};

// Convenience alias used throughout the HTML pages
function showToast(msg, type = 'success') { Toast.show(msg, type); }

// ─────────────────────────────────────────────────────────────────
// NAVIGATION — sidebar + mobile nav builder
// ─────────────────────────────────────────────────────────────────
const NAV_PAGES = [
  { href: 'dashboard.html',  icon: 'fa-home',          label: 'Dashboard',    short: 'Home'    },
  { href: 'stock-entry.html', icon: 'fa-plus-circle',  label: 'Record Stock', short: 'Stock'   },
  { href: 'sales.html',      icon: 'fa-cash-register', label: 'Record Sale',  short: 'Sale'    },
  { href: 'reports.html',    icon: 'fa-chart-bar',     label: 'Reports',      short: 'Reports' },
];

function buildSidebar(activePage) {
  const navMenu = document.querySelector('.sidebar .nav-menu');
  const mobileInner = document.querySelector('.mobile-nav-inner');

  if (navMenu) {
    navMenu.innerHTML = NAV_PAGES.map(p => `
      <a href="${p.href}" class="nav-item ${p.href === activePage ? 'active' : ''}">
        <i class="fas ${p.icon}"></i> ${p.label}
      </a>`).join('');
  }

  if (mobileInner) {
    mobileInner.innerHTML = NAV_PAGES.map(p => `
      <a href="${p.href}" class="mobile-nav-item ${p.href === activePage ? 'active' : ''}">
        <i class="fas ${p.icon}"></i><span>${p.short}</span>
      </a>`).join('');
  }

  const username = localStorage.getItem('username') || 'User';
  const el = {
    name:   document.getElementById('userName'),
    avatar: document.getElementById('userAvatar'),
  };
  if (el.name)   el.name.textContent   = username;
  if (el.avatar) el.avatar.textContent = username[0].toUpperCase();
}

function toggleSidebar() {
  document.getElementById('sidebar')?.classList.toggle('open');
  document.getElementById('sidebarOverlay')?.classList.toggle('show');
  document.getElementById('hamburgerBtn')?.classList.toggle('active');
}

function logout() {
  Auth.logout();
}

window.addEventListener('resize', () => {
  if (window.innerWidth > 1024) {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('show');
    document.getElementById('hamburgerBtn')?.classList.remove('active');
  }
});

// ─────────────────────────────────────────────────────────────────
// LOAD USER ROLE — fetches and displays role in sidebar footer
// ─────────────────────────────────────────────────────────────────
async function loadUserRole() {
  const username = localStorage.getItem('username');
  const roleEl   = document.getElementById('userRole');
  if (!roleEl) return;

  // Show cached role immediately while request is in flight
  const cached = localStorage.getItem('role');
  if (cached) roleEl.textContent = cached.charAt(0).toUpperCase() + cached.slice(1);

  try {
    const users = await apiRequest('/users/');
    const list  = Array.isArray(users) ? users : (users.results || []);
    const me    = list.find(u => u.username === username);
    const role  = me?.profile?.role || '';
    if (role) {
      roleEl.textContent = role.charAt(0).toUpperCase() + role.slice(1);
      localStorage.setItem('role', role);
    }
  } catch {}
}

// ─────────────────────────────────────────────────────────────────
// LOADING STATE HELPER
// ─────────────────────────────────────────────────────────────────
const Loading = {
  show(btn, message = 'Loading…') {
    btn.disabled = true;
    btn._orig = btn.innerHTML;
    btn.innerHTML = `<i class="fas fa-circle-notch fa-spin"></i> ${message}`;
  },
  hide(btn) {
    btn.disabled = false;
    if (btn._orig) btn.innerHTML = btn._orig;
  }
};

// ─────────────────────────────────────────────────────────────────
// DATE / CURRENCY UTILITIES
// ─────────────────────────────────────────────────────────────────
const DateUtils = {
  formatDate(d)     { return new Date(d).toLocaleDateString('en-KE', { year:'numeric', month:'short', day:'numeric' }); },
  formatDateTime(d) { return new Date(d).toLocaleString('en-KE', { year:'numeric', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }); },
  getToday()        { return new Date().toISOString().split('T')[0]; },
  getNow()          { return new Date().toISOString().slice(0, 16); },
};

const Currency = {
  format(amount)    { return `KES ${parseFloat(amount).toFixed(0)}`; },
  formatWeight(kg)  { return `${parseFloat(kg).toFixed(2)} kg`; },
};

// ─────────────────────────────────────────────────────────────────
// AUTH GUARD — call on every protected page
// ─────────────────────────────────────────────────────────────────
function requireAuth() {
  if (!Auth.isAuthenticated()) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

// ─────────────────────────────────────────────────────────────────
// EXPOSE GLOBALS
// ─────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────
// KEEP-ALIVE — pings the backend every 14 min so Render never sleeps.
// Only runs in production (not on localhost).
// ─────────────────────────────────────────────────────────────────
(function keepAlive() {
  const isProduction = window.location.hostname !== 'localhost'
                    && window.location.hostname !== '127.0.0.1';
  if (!isProduction) return;

  async function ping() {
    try {
      // Hit the token endpoint with a dummy request — lightweight, no auth needed
      await fetch(`${CONFIG.PROD_API_URL}/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: '_ping_', password: '_ping_' })
      });
    } catch {}
    // Silently ignore — we only care that the server woke up
  }

  // Ping immediately on page load, then every 14 minutes
  ping();
  setInterval(ping, 14 * 60 * 1000);
})();

window.NyamaTrack = { CONFIG, Auth, apiRequest, Toast, DateUtils, Currency, Loading };