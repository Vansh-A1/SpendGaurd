/**
 * SpendGuard API Client
 * Connects the Emergent React frontend to the FastAPI backend.
 */

const API_BASE =
  process.env.REACT_APP_API_BASE_URL ||
  process.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
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
    console.error(`[API Error] ${options.method || "GET"} ${endpoint}:`, err.message);
    throw err;
  }
}

export const api = {
  // System
  getHealth: () => request("/health"),
  seedScenarios: () => request("/admin/seed_scenarios", { method: "POST" }),

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
