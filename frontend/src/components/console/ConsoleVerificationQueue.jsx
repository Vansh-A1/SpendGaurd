import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Check, X, ArrowUpRight, RefreshCw, AlertTriangle, ShieldCheck } from "lucide-react";

export function ConsoleVerificationQueue({ onSelectTransaction, user }) {
  const [loading, setLoading] = useState(true);
  const [escalations, setEscalations] = useState([]);
  const [resolvingId, setResolvingId] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const canResolve = ["admin", "operator"].includes(user?.role);

  const loadEscalations = async () => {
    try {
      setLoading(true);
      const data = await api.getEscalations();
      setEscalations(data || []);
    } catch (err) {
      console.error("Failed to load escalations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEscalations();
    const interval = setInterval(loadEscalations, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (txId, approved) => {
    try {
      setResolvingId(txId);
      await api.verifyTransaction(txId, approved);
      setFeedback({
        id: txId,
        type: approved ? "approved" : "rejected",
        message: approved
          ? `Transaction ${txId} approved. Payment captured via Razorpay.`
          : `Transaction ${txId} rejected. Pre-auth hold voided.`,
      });
      await loadEscalations();
      setTimeout(() => setFeedback(null), 5000);
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <div className="console-page" data-testid="verification-queue-page">
      <header className="console-page-header">
        <div>
          <span className="console-kicker">Human-in-the-loop Resolution</span>
          <h1 className="console-title">Needs your attention</h1>
          <p className="console-subtitle">Transactions placed on 15-minute SLA authorization holds requiring operator approval.</p>
        </div>
        <button className="console-button" onClick={loadEscalations} data-testid="refresh-queue-button">
          <RefreshCw size={13} />
          <span>Refresh Queue</span>
        </button>
      </header>

      {feedback && (
        <div className={`console-seed-message ${feedback.type}`} data-testid="queue-feedback">
          {feedback.type === "approved" ? <ShieldCheck size={14} /> : <AlertTriangle size={14} />}
          <span>{feedback.message}</span>
        </div>
      )}

      <div className="queue-list" data-testid="verification-queue-list">
        {loading && escalations.length === 0 ? (
          <div className="console-empty">Checking active escalation queue...</div>
        ) : escalations.length === 0 ? (
          <div className="console-empty" data-testid="queue-empty-state">
            <ShieldCheck size={20} />
            <h3>All Clear</h3>
            <p>No pending pre-authorization holds in the escalation queue. All transactions have been cleanly resolved.</p>
          </div>
        ) : (
          escalations.map((item) => {
            const isResolving = resolvingId === item.transaction_id;
            return (
              <article className="queue-item" key={item.id || item.transaction_id} data-testid={`queue-item-${item.transaction_id}`}>
                <div className="queue-item-head">
                  <div>
                    <button className="console-back" onClick={() => onSelectTransaction(item.transaction_id)} data-testid={`open-queue-${item.transaction_id}`}>
                      <span>{item.transaction_id}</span>
                      <ArrowUpRight size={13} />
                    </button>
                    <h3 className="queue-title">Agent: {item.agent_id}</h3>
                    <div className="queue-meta">Escalated at: {item.created_at ? new Date(item.created_at).toLocaleTimeString() : "Recent"}</div>
                  </div>
                  <div className="queue-amount">
                    <span>Hold Amount</span>
                    <strong>₹{(parseFloat(item.amount) || 0).toLocaleString()}</strong>
                    <StatusBadge status="VERIFY" />
                  </div>
                </div>
                <div className="queue-context">
                  <strong>Escalation Context</strong>
                  <p>{item.reason || "Autonomous agent initiated a purchase requiring operator confirmation (e.g. brand substitution or stale mandate)."}</p>
                </div>
                <div className="queue-actions">
                  <span className="status-badge status-verify">SLA {item.sla_remaining_minutes !== undefined ? `${item.sla_remaining_minutes.toFixed(1)}m remaining` : "15m hold"}</span>
                  {canResolve ? (
                    <>
                      <button className="console-button-danger" onClick={() => handleAction(item.transaction_id, false)} disabled={isResolving} data-testid={`reject-hold-${item.transaction_id}`}>
                        <X size={13} />
                        <span>Reject &amp; Void Hold</span>
                      </button>
                      <button className="console-button-primary" onClick={() => handleAction(item.transaction_id, true)} disabled={isResolving} data-testid={`approve-hold-${item.transaction_id}`}>
                        <Check size={13} />
                        <span>Approve &amp; Capture Payment</span>
                      </button>
                    </>
                  ) : (
                    <span className="status-badge">Read-only viewer</span>
                  )}
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ConsoleVerificationQueue;
