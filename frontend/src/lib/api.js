/**
 * SpendGuard API Client
 * Connects the Emergent React frontend to the FastAPI backend.
 */

const RAW_URL =
  process.env.REACT_APP_API_BASE_URL ||
  process.env.REACT_APP_BACKEND_URL ||
  process.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

const API_BASE = RAW_URL.replace(/\/+$/, "").replace(/\/api$/, "");

function getToken() {
  if (typeof window !== "undefined") {
    return localStorage.getItem("spendguard_access_token");
  }
  return null;
}

function setToken(token) {
  if (typeof window !== "undefined") {
    if (token) {
      localStorage.setItem("spendguard_access_token", token);
    } else {
      localStorage.removeItem("spendguard_access_token");
    }
  }
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const config = {
    credentials: "include",
    headers,
    ...options,
  };

  try {
    const res = await fetch(url, config);
    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      const message = errorBody.detail || `Request failed with status ${res.status}`;
      throw new Error(message);
    }
    return await res.json();
  } catch (err) {
    if (!options.silent) {
      console.error(`[API Error] ${options.method || "GET"} ${endpoint}:`, err.message);
    }
    throw err;
  }
}

export const api = {
  // System & Auth
  getHealth: () => request("/health"),
  seedScenarios: () => request("/admin/seed_scenarios", { method: "POST" }),
  login: async (email, password) => {
    const res = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (res?.access_token) {
      setToken(res.access_token);
    }
    return res;
  },
  logout: async () => {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
    }
    return { status: "ok" };
  },
  getCurrentUser: () => request("/auth/me", { silent: true }),
  refreshSession: async () => {
    const res = await request("/auth/refresh", { method: "POST" });
    if (res?.access_token) {
      setToken(res.access_token);
    }
    return res;
  },

  // Transactions & Decision Engine
  evaluateTransaction: (transactionRequest) =>
    request("/transactions/evaluate", {
      method: "POST",
      body: JSON.stringify(transactionRequest),
    }),

  getTransactions: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.decision) params.append("decision", filters.decision);
    if (filters.agent_id) params.append("agent_id", filters.agent_id);
    if (filters.session_id) params.append("session_id", filters.session_id);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/transactions${query}`);
  },

  getTransactionReceipt: (id) => request(`/transactions/${id}/receipt`),
  getTransactionSnapshot: (id) => request(`/transactions/${id}/snapshot`),

  verifyTransaction: (id, approved) =>
    request(`/transactions/${id}/verify`, {
      method: "POST",
      body: JSON.stringify({ approved: Boolean(approved) }),
    }),

  // Purchase Sessions
  getSessions: (agentId) => {
    const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : "";
    return request(`/sessions${query}`);
  },

  getSessionDetails: (sessionId) => request(`/sessions/${sessionId}`),

  // Escalations & SLA Queue
  getEscalations: () => request("/escalations"),
  processTimeouts: () => request("/escalations/process_timeouts", { method: "POST" }),

  // Webhooks
  getWebhook: () => request("/admin/webhook"),
  setWebhook: (url) =>
    request("/admin/webhook", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
};

export default api;
