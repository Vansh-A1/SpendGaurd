import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { ArrowRight, ShieldCheck, AlertTriangle, Clock, RefreshCw } from "lucide-react";

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
    return (
      <div className="py-20 text-center space-y-4">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-[#a99df2]" />
        <p className="text-sm font-mono text-[#8d94a1]">Fetching live SpendGuard telemetry...</p>
      </div>
    );
  }

  if (error && transactions.length === 0) {
    return (
      <div className="p-8 border border-rose-500/20 bg-rose-950/20 rounded-sm text-center space-y-3">
        <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto" />
        <h3 className="font-serif text-lg text-[#f0eef5]">Backend Connection Error</h3>
        <p className="text-xs font-mono text-[#8d94a1]">{error}</p>
        <button
          onClick={fetchData}
          className="px-4 py-1.5 bg-[#10141e] border border-[#dddee8]/20 text-xs font-mono hover:text-[#a99df2]"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-10 pb-16">
      {/* 1. Header with greeting and system status */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#dddee8]/10 pb-6">
        <div>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5] font-normal tracking-tight">
            Live Trust Center
          </h1>
          <p className="text-[#8d94a1] text-sm mt-1">
            Real-time multi-agent payment evaluation, provenance auditing, and pre-auth hold state.
          </p>
        </div>

        <button
          onClick={fetchData}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* 2. Quiet Metric Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
        <div className="bg-[#0b0e14] border border-[#dddee8]/10 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            EVALUATIONS
          </div>
          <div className="text-2xl sm:text-3xl font-mono font-bold text-[#f0eef5]">
            {totalCount}
          </div>
          <div className="text-[11px] text-[#8d94a1]">
            100% policy containment
          </div>
        </div>

        <div className="bg-[#0b0e14] border border-[#dddee8]/10 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            PROTECTED VALUE
          </div>
          <div className="text-2xl sm:text-3xl font-mono font-bold text-rose-400">
            ₹{blockedValue.toLocaleString()}
          </div>
          <div className="text-[11px] text-rose-400/80 font-mono">
            {blockCount} hard blocks enforced
          </div>
        </div>

        <div className="bg-[#0b0e14] border border-[#dddee8]/10 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            VERIFICATION HOLDS
          </div>
          <div className="text-2xl sm:text-3xl font-mono font-bold text-amber-400">
            ₹{heldValue.toLocaleString()}
          </div>
          <div className="text-[11px] text-amber-400/80 font-mono">
            {verifyCount} cases placed on SLA
          </div>
        </div>

        <div className="bg-[#0b0e14] border border-[#dddee8]/10 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            CLEAN AUTHORIZED
          </div>
          <div className="text-2xl sm:text-3xl font-mono font-bold text-emerald-400">
            ₹{totalSpent.toLocaleString()}
          </div>
          <div className="text-[11px] text-emerald-400/80 font-mono flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5" /> {allowCount} instant captures
          </div>
        </div>
      </div>

      {/* 3. Real-Time Pipeline Visual */}
      <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-6 sm:p-8 space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
              REAL-TIME FLOW
            </span>
            <h3 className="font-serif text-xl text-[#f0eef5] mt-0.5">
              Autonomous Decision Pipeline
            </h3>
          </div>
          <span className="text-xs font-mono text-[#8d94a1]">
            {totalCount} Total Processed
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#07090d]/80 border border-emerald-500/20 rounded-sm p-4 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="font-bold text-emerald-400">01 DIRECT ALLOW</span>
              <span className="text-[#f0eef5] font-bold">{allowCount} txs</span>
            </div>
            <p className="text-xs text-[#8d94a1] leading-relaxed font-sans">
              Clean legitimate purchases approved immediately without human latency.
            </p>
            <div className="text-[11px] font-mono text-[#8d94a1] pt-2 border-t border-[#dddee8]/10">
              Value: ₹{totalSpent.toLocaleString()}
            </div>
          </div>

          <div className="bg-[#07090d]/80 border border-amber-500/20 rounded-sm p-4 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="font-bold text-amber-400">02 HELD FOR REVIEW</span>
              <span className="text-[#f0eef5] font-bold">{verifyCount} txs</span>
            </div>
            <p className="text-xs text-[#8d94a1] leading-relaxed font-sans">
              Substitutions &amp; stale mandates placed on 15m pre-auth holds.
            </p>
            <div className="text-[11px] font-mono text-[#8d94a1] pt-2 border-t border-[#dddee8]/10">
              Value: ₹{heldValue.toLocaleString()}
            </div>
          </div>

          <div className="bg-[#07090d]/80 border border-rose-500/20 rounded-sm p-4 space-y-2">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="font-bold text-rose-400">03 FRAUD BLOCKED</span>
              <span className="text-[#f0eef5] font-bold">{blockCount} txs</span>
            </div>
            <p className="text-xs text-[#8d94a1] leading-relaxed font-sans">
              Budget overshoots, wrong products, and evidence conflicts hard-stopped.
            </p>
            <div className="text-[11px] font-mono text-[#8d94a1] pt-2 border-t border-[#dddee8]/10">
              Value: ₹{blockedValue.toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active Verification Queue Notice (if any) */}
      {escalations.length > 0 && (
        <div className="bg-amber-950/30 border border-amber-500/30 rounded-sm p-5 flex flex-col sm:flex-row justify-between sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-amber-400 animate-pulse" />
            <div>
              <h4 className="font-serif text-base text-[#f0eef5]">
                {escalations.length} Pending Pre-Authorization Holds
              </h4>
              <p className="text-xs text-[#8d94a1]">
                Requires human review before 15-minute SLA timeout expiration.
              </p>
            </div>
          </div>
          <button
            onClick={() => setTab("review")}
            className="px-4 py-1.5 bg-amber-400 text-[#07090d] font-semibold text-xs rounded-sm hover:bg-amber-300 transition-colors"
          >
            Open Verification Queue →
          </button>
        </div>
      )}

      {/* 5. Live Activity Feed */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
              LIVE AUDIT STREAM
            </span>
            <h3 className="font-serif text-2xl text-[#f0eef5] mt-0.5">
              Recent Decision Activity
            </h3>
          </div>
          <button
            onClick={() => setTab("transactions")}
            className="text-xs font-mono text-[#a99df2] hover:text-[#f0eef5] transition-colors inline-flex items-center gap-1"
          >
            <span>View all transactions</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {recentTxs.length === 0 ? (
          <div className="p-12 border border-[#dddee8]/10 bg-[#0b0e14] rounded-sm text-center space-y-3">
            <p className="text-sm font-mono text-[#8d94a1]">No transactions recorded in the database yet.</p>
            <button
              onClick={() => api.seedScenarios().then(fetchData)}
              className="px-4 py-2 bg-[#a99df2] text-[#07090d] font-bold text-xs rounded-sm hover:bg-white transition-colors"
            >
              Seed 110 Benchmark Scenarios
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {recentTxs.map((tx) => (
              <div
                key={tx.id}
                onClick={() => onSelectTransaction(tx.id)}
                className="group cursor-pointer bg-[#0b0e14] border border-[#dddee8]/10 hover:border-[#a99df2]/40 rounded-sm p-4 sm:p-5 transition-all hover:bg-[#10141e]"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold text-[#a99df2]">{tx.id}</span>
                      <span className="text-[11px] text-[#8d94a1] font-mono">
                        • {tx.timestamp ? new Date(tx.timestamp).toLocaleString() : "Just now"}
                      </span>
                      {tx.payment_hold_id && (
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-500/30">
                          HOLD: {tx.payment_hold_id}
                        </span>
                      )}
                    </div>
                    <h4 className="font-serif text-lg text-[#f0eef5] group-hover:text-[#a99df2] transition-colors">
                      {tx.merchant} — ₹{(parseFloat(tx.amount) || 0).toLocaleString()}
                    </h4>
                    <div className="text-xs text-[#8d94a1] flex flex-wrap items-center gap-3 font-mono">
                      <span>Agent: <strong className="text-[#f0eef5]">{tx.agent_id}</strong></span>
                      <span>•</span>
                      <span>Category: <strong className="text-[#f0eef5]">{tx.category}</strong></span>
                      {tx.risk_score !== undefined && (
                        <>
                          <span>•</span>
                          <span>Risk: <strong className="text-[#f0eef5]">{parseFloat(tx.risk_score).toFixed(2)}</strong></span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between md:justify-end gap-6 pt-3 md:pt-0 border-t md:border-t-0 border-[#dddee8]/10">
                    <div className="text-left md:text-right font-mono">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">Amount</div>
                      <div className="text-lg font-bold text-[#f0eef5]">
                        ₹{(parseFloat(tx.amount) || 0).toLocaleString()}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge status={tx.decision} />
                      <ArrowRight className="w-4 h-4 text-[#8d94a1] group-hover:text-[#a99df2] group-hover:translate-x-0.5 transition-all hidden sm:block" />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConsoleOverview;
