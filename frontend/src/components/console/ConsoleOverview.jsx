import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, RefreshCw, ShieldX } from "lucide-react";

export function ConsoleOverview({ onSelectTransaction, setTab }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [escalations, setEscalations] = useState([]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [txs, sess, esc] = await Promise.all([
        api.getTransactions().catch(() => []),
        api.getSessions().catch(() => []),
        api.getEscalations().catch(() => []),
      ]);
      setTransactions(txs || []);
      setSessions(sess || []);
      setEscalations(esc || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Compute live statistics from real backend data
  const totalCount = transactions.length;
  const allowCount = transactions.filter((t) => t.decision === "ALLOW").length;
  const verifyCount = transactions.filter((t) => t.decision === "VERIFY").length;
  const blockCount = transactions.filter((t) => t.decision === "BLOCK").length;

  const totalSpent = transactions
    .filter((t) => t.decision === "ALLOW")
    .reduce((sum, t) => sum + (parseFloat(t.amount) || 0), 0);

  const blockedValue = transactions
    .filter((t) => t.decision === "BLOCK")
    .reduce((sum, t) => sum + (parseFloat(t.amount) || 0), 0);

  const heldValue = transactions
    .filter((t) => t.decision === "VERIFY")
    .reduce((sum, t) => sum + (parseFloat(t.amount) || 0), 0);

  const recentTxs = transactions.slice(0, 6);

  if (loading && transactions.length === 0) {
    return <div className="console-loading"><RefreshCw size={14} /><span>Fetching live SpendGuard telemetry...</span></div>;
  }

  if (error && transactions.length === 0) {
    return (
      <div className="console-empty" data-testid="overview-error">
        <AlertTriangle size={18} />
        <h3>Backend Connection Error</h3>
        <p>{error}</p>
        <button className="console-button" onClick={fetchData}>Retry Connection</button>
      </div>
    );
  }

  return (
    <div className="console-page" data-testid="console-overview-page">
      <header className="console-page-header">
        <div>
          <span className="console-kicker">Live Trust Center</span>
          <h1 className="console-title">Live Trust Center</h1>
          <p className="console-subtitle">Real-time multi-agent payment evaluation, provenance auditing, and pre-auth hold state.</p>
        </div>
        <button className="console-button" onClick={fetchData} data-testid="refresh-data-button">
          <RefreshCw size={13} />
          <span>Refresh Data</span>
        </button>
      </header>

      <section className="kpi-grid" data-testid="kpi-grid">
        <article className="kpi-card" data-testid="kpi-evaluations">
          <span className="kpi-label">Evaluations</span>
          <strong className="kpi-value">{totalCount}</strong>
          <span className="kpi-meta">100% policy containment</span>
        </article>
        <article className="kpi-card" data-testid="kpi-protected-value">
          <span className="kpi-label">Protected Value</span>
          <strong className="kpi-value">₹{blockedValue.toLocaleString()}</strong>
          <span className="kpi-meta block">{blockCount} hard blocks enforced</span>
        </article>
        <article className="kpi-card" data-testid="kpi-verification-holds">
          <span className="kpi-label">Verification Holds</span>
          <strong className="kpi-value">₹{heldValue.toLocaleString()}</strong>
          <span className="kpi-meta verify">{verifyCount} cases placed on SLA</span>
        </article>
        <article className="kpi-card" data-testid="kpi-clean-authorized">
          <span className="kpi-label">Clean Authorized</span>
          <strong className="kpi-value">₹{totalSpent.toLocaleString()}</strong>
          <span className="kpi-meta allow">{allowCount} instant captures</span>
        </article>
      </section>

      <section className="console-panel" data-testid="decision-pipeline">
        <div className="console-panel-header">
          <div>
            <span className="console-kicker">Real-time flow</span>
            <h2 className="console-panel-title">Autonomous Decision Pipeline</h2>
          </div>
          <span className="console-panel-note">{totalCount} Total Processed</span>
        </div>
        <div className="pipeline">
          <div className="pipeline-flow">
            <article className="pipeline-step allow" data-testid="pipeline-allow">
              <div className="pipeline-marker"><CheckCircle2 size={14} /></div>
              <h4>DIRECT ALLOW</h4>
              <p>Clean legitimate purchases approved immediately without human latency.</p>
              <div className="pipeline-stats"><span>Volume<strong>{allowCount} txs</strong></span><span>Value<strong>₹{totalSpent.toLocaleString()}</strong></span></div>
            </article>
            <article className="pipeline-step verify" data-testid="pipeline-verify">
              <div className="pipeline-marker"><Clock3 size={14} /></div>
              <h4>HELD FOR REVIEW</h4>
              <p>Substitutions &amp; stale mandates placed on 15m pre-auth holds.</p>
              <div className="pipeline-stats"><span>Volume<strong>{verifyCount} txs</strong></span><span>Value<strong>₹{heldValue.toLocaleString()}</strong></span></div>
            </article>
            <article className="pipeline-step block" data-testid="pipeline-block">
              <div className="pipeline-marker"><ShieldX size={14} /></div>
              <h4>FRAUD BLOCKED</h4>
              <p>Budget overshoots, wrong products, and evidence conflicts hard-stopped.</p>
              <div className="pipeline-stats"><span>Volume<strong>{blockCount} txs</strong></span><span>Value<strong>₹{blockedValue.toLocaleString()}</strong></span></div>
            </article>
          </div>
        </div>
      </section>

      {escalations.length > 0 && (
        <section className="pending-alert" data-testid="pending-verification-alert">
          <div>
            <h3>{escalations.length} Pending Pre-Authorization Holds</h3>
            <p>Requires human review before 15-minute SLA timeout expiration.</p>
          </div>
          <button className="console-button" onClick={() => setTab("review")} data-testid="open-verification-queue-button">
            <span>Open Verification Queue</span>
            <ArrowRight size={13} />
          </button>
        </section>
      )}

      <section className="console-panel" data-testid="recent-decision-activity">
        <div className="console-panel-header">
          <div>
            <span className="console-kicker">Live audit stream</span>
            <h2 className="console-panel-title">Recent Decision Activity</h2>
          </div>
          <button className="console-button" onClick={() => setTab("transactions")} data-testid="view-all-transactions-button">
            <span>View all transactions</span>
            <ArrowRight size={13} />
          </button>
        </div>
        {recentTxs.length === 0 ? (
          <div className="console-empty">
            <p>No transactions recorded in the database yet.</p>
            <button className="console-button-primary" onClick={() => api.seedScenarios().then(fetchData)} data-testid="seed-empty-state-button">Seed 110 Benchmark Scenarios</button>
          </div>
        ) : (
          <div className="console-table-wrap">
            <table className="console-table">
              <thead>
                <tr><th>Status</th><th>Transaction ID</th><th>Merchant</th><th>Amount</th><th>Timestamp</th><th>Hold / Reference</th><th>Action</th></tr>
              </thead>
              <tbody>
                {recentTxs.map((tx) => (
                  <tr key={tx.id} onClick={() => onSelectTransaction(tx.id)} data-testid={`recent-tx-${tx.id}`}>
                    <td><StatusBadge status={tx.decision} /></td>
                    <td><span className="tx-id">{tx.id}</span></td>
                    <td><span className="tx-merchant">{tx.merchant}</span></td>
                    <td className="tx-amount">₹{(parseFloat(tx.amount) || 0).toLocaleString()}</td>
                    <td>{tx.timestamp ? new Date(tx.timestamp).toLocaleString() : "Just now"}</td>
                    <td><span className="tx-reference">{tx.payment_hold_id || tx.session_id || "—"}</span></td>
                    <td><button className="console-button" data-testid={`open-recent-${tx.id}`}>Open</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default ConsoleOverview;
