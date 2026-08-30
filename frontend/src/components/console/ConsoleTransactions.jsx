import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { ArrowRight, RefreshCw, Search } from "lucide-react";

export function ConsoleTransactions({ onSelectTransaction }) {
  const [loading, setLoading] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [decisionFilter, setDecisionFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("ALL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [riskFilter, setRiskFilter] = useState("ALL");

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await api.getTransactions(
        decisionFilter !== "ALL" ? { decision: decisionFilter } : {}
      );
      setTransactions(data || []);
    } catch (err) {
      console.error("Failed to load transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decisionFilter]);

  // Extract unique agents for filtering
  const agents = Array.from(new Set(transactions.map((t) => t.agent_id).filter(Boolean)));

  const getRiskScore = (tx) => {
    try {
      const parsed = JSON.parse(tx.behavioral_risk_json || "{}");
      return typeof parsed.score === "number" ? parsed.score : null;
    } catch {
      return null;
    }
  };

  const filteredTxs = transactions.filter((tx) => {
    if (agentFilter !== "ALL" && tx.agent_id !== agentFilter) return false;
    const timestamp = tx.timestamp ? new Date(tx.timestamp) : null;
    if (startDate && (!timestamp || timestamp < new Date(`${startDate}T00:00:00`))) return false;
    if (endDate && (!timestamp || timestamp > new Date(`${endDate}T23:59:59`))) return false;
    const riskScore = getRiskScore(tx);
    if (riskFilter === "HIGH" && !(riskScore !== null && riskScore >= 0.7)) return false;
    if (riskFilter === "MEDIUM" && !(riskScore !== null && riskScore >= 0.35 && riskScore < 0.7)) return false;
    if (riskFilter === "LOW" && !(riskScore !== null && riskScore < 0.35)) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (tx.id && tx.id.toLowerCase().includes(q)) ||
      (tx.agent_id && tx.agent_id.toLowerCase().includes(q)) ||
      (tx.merchant && tx.merchant.toLowerCase().includes(q)) ||
      (tx.category && tx.category.toLowerCase().includes(q))
    );
  });

  return (
    <div className="console-page" data-testid="console-transactions-page">
      <header className="console-page-header">
        <div>
          <span className="console-kicker">Audit Trail</span>
          <h1 className="console-title">Transaction Activity Feed</h1>
          <p className="console-subtitle">Immutable log of multi-agent evaluations, policy checks, and gateway hold states.</p>
        </div>
        <button className="console-button" onClick={loadTransactions} data-testid="transactions-refresh-button">
          <RefreshCw size={13} />
          <span>Refresh</span>
        </button>
      </header>

      <div className="console-filters" data-testid="transaction-filters">
        <div className="filter-group" role="tablist" aria-label="Decision filters">
          {["ALL", "ALLOW", "VERIFY", "BLOCK"].map((status) => (
            <button key={status} onClick={() => setDecisionFilter(status)} className={`filter-button ${decisionFilter === status ? "active" : ""}`} data-testid={`filter-${status.toLowerCase()}`}>{status}</button>
          ))}
        </div>
        <div className="filter-group">
          <div className="console-search">
            <Search />
            <input type="text" placeholder="Search ID, Merchant, SKU..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} data-testid="transaction-search-input" />
          </div>
          {agents.length > 0 && (
            <select className="console-select" value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} data-testid="agent-filter-select">
              <option value="ALL">All Agents</option>
              {agents.map((ag) => <option key={ag} value={ag}>{ag}</option>)}
            </select>
          )}
        </div>
      </div>

      <div className="audit-filter-row" data-testid="audit-filters">
        <label><span>From</span><input className="console-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} data-testid="start-date-filter" /></label>
        <label><span>To</span><input className="console-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} data-testid="end-date-filter" /></label>
        <label><span>Risk Score</span><select className="console-select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} data-testid="risk-score-filter"><option value="ALL">All Risk</option><option value="LOW">Low · &lt; 0.35</option><option value="MEDIUM">Medium · 0.35–0.69</option><option value="HIGH">High · ≥ 0.70</option></select></label>
      </div>

      <section className="console-table-wrap" data-testid="transactions-table">
        {loading && transactions.length === 0 ? (
          <div className="console-empty">Loading audit records...</div>
        ) : filteredTxs.length === 0 ? (
          <div className="console-empty">No transactions match the selected filter criteria.</div>
        ) : (
          <table className="console-table">
            <thead>
              <tr><th>Status</th><th>Transaction ID</th><th>Merchant</th><th>Agent</th><th>Amount</th><th>Risk</th><th>Timestamp</th><th>Hold / Reference</th><th>Action</th></tr>
            </thead>
            <tbody>
              {filteredTxs.map((tx) => (
                <tr key={tx.id} onClick={() => onSelectTransaction(tx.id)} data-testid={`transaction-row-${tx.id}`}>
                  <td><StatusBadge status={tx.decision} /></td>
                  <td><span className="tx-id">{tx.id}</span></td>
                  <td><span className="tx-merchant">{tx.merchant}</span></td>
                  <td>{tx.agent_id}</td>
                  <td className="tx-amount">₹{(parseFloat(tx.amount) || 0).toLocaleString()}</td>
                  <td>{getRiskScore(tx) !== null ? getRiskScore(tx).toFixed(2) : "—"}</td>
                  <td>{tx.timestamp ? new Date(tx.timestamp).toLocaleString() : "Just now"}</td>
                  <td><span className="tx-reference">{tx.payment_hold_id || tx.session_id || "—"}</span></td>
                  <td><button className="console-button" data-testid={`open-transaction-${tx.id}`}><span>Open</span><ArrowRight size={12} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default ConsoleTransactions;
