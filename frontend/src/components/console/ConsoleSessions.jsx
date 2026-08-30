import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Layers, RefreshCw } from "lucide-react";

export function ConsoleSessions({ onSelectTransaction }) {
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const data = await api.getSessions();
      setSessions(data || []);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  return (
    <div className="console-page" data-testid="purchase-sessions-page">
      <header className="console-page-header">
        <div>
          <span className="console-kicker">Multi-window Governance</span>
          <h1 className="console-title">Purchase Sessions</h1>
          <p className="console-subtitle">Multi-step session lifecycle tracking, cumulative spend limits, and split-payment velocity monitoring.</p>
        </div>
        <button className="console-button" onClick={loadSessions} data-testid="sessions-refresh-button">
          <RefreshCw size={13} />
          <span>Refresh</span>
        </button>
      </header>

      <div className="session-list" data-testid="sessions-list">
        {loading && sessions.length === 0 ? (
          <div className="console-empty">Loading purchase sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="console-empty" data-testid="sessions-empty-state">
            <Layers size={20} />
            <h3>No Active Sessions</h3>
            <p>Purchase sessions are registered when autonomous agents initiate multi-item or scheduled procurement tasks.</p>
          </div>
        ) : (
          sessions.map((sess) => {
            const transactions = sess.transactions || [];
            const budget = parseFloat(sess.declared_total_budget ?? sess.declared_budget ?? 0);
            const spent = parseFloat(sess.total_spent ?? transactions.reduce((sum, tx) => sum + (parseFloat(tx.amount) || 0), 0));
            const remaining = Math.max(0, budget - spent);
            const pct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : 0;
            const transactionCount = sess.transaction_count ?? transactions.length;
            const maxItems = sess.declared_item_count ?? sess.max_items ?? 10;

            return (
              <article className="session-item" key={sess.session_id} data-testid={`session-${sess.session_id}`}>
                <div className="session-item-head">
                  <div>
                    <div className="queue-meta">{sess.session_id} · Agent: {sess.agent_id}</div>
                    <h3 className="session-title">{sess.intent_description || `Session for ${sess.agent_id}`}</h3>
                    <div className="session-meta">Created: {sess.created_at ? new Date(sess.created_at).toLocaleDateString() : "Active"}</div>
                  </div>
                  <div className="session-metrics">
                    <div className="session-metric"><span>Declared Budget</span><strong>₹{budget.toLocaleString()}</strong></div>
                    <div className="session-metric"><span>Cumulative Spent</span><strong>₹{spent.toLocaleString()} ({pct}%)</strong></div>
                    <div className="session-metric"><span>Transactions</span><strong>{transactionCount} / {maxItems} items</strong></div>
                  </div>
                </div>
                <div className={`budget-meter ${pct > 90 ? "danger" : pct > 70 ? "warn" : ""}`}><i style={{ width: `${pct}%` }} /></div>
                <div className="session-meta">Remaining capacity: ₹{remaining.toLocaleString()}</div>
                {transactions.length > 0 && (
                  <div className="session-transactions">
                    {transactions.map((tx) => (
                      <div className="session-transaction" key={tx.id} onClick={() => onSelectTransaction(tx.id)} data-testid={`session-tx-${tx.id}`}>
                        <span><strong className="tx-id">{tx.id}</strong> · {tx.merchant}</span>
                        <span>₹{(parseFloat(tx.amount) || 0).toLocaleString()} <StatusBadge status={tx.decision} /></span>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ConsoleSessions;
