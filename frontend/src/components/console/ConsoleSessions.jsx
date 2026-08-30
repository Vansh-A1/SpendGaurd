import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Layers, RefreshCw, AlertTriangle, ArrowRight, CheckCircle2 } from "lucide-react";

export function ConsoleSessions({ onSelectTransaction }) {
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);

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
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#dddee8]/10 pb-6">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
            MULTI-WINDOW GOVERNANCE
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5] font-normal mt-1">
            Purchase Sessions
          </h1>
          <p className="text-[#8d94a1] text-sm mt-1">
            Multi-step session lifecycle tracking, cumulative spend limits, and split-payment velocity monitoring.
          </p>
        </div>

        <button
          onClick={loadSessions}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Sessions List */}
      <div className="space-y-4">
        {loading && sessions.length === 0 ? (
          <div className="py-20 text-center text-sm font-mono text-[#8d94a1]">
            Loading purchase sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-16 border border-[#dddee8]/10 bg-[#0b0e14] rounded-sm text-center space-y-3">
            <Layers className="w-8 h-8 text-[#a99df2] mx-auto" />
            <h3 className="font-serif text-xl text-[#f0eef5]">No Active Sessions</h3>
            <p className="text-xs font-mono text-[#8d94a1] max-w-md mx-auto">
              Purchase sessions are registered when autonomous agents initiate multi-item or scheduled procurement tasks.
            </p>
          </div>
        ) : (
          sessions.map((sess) => {
            const budget = parseFloat(sess.declared_budget || 0);
            const spent = parseFloat(sess.total_spent || 0);
            const remaining = Math.max(0, budget - spent);
            const pct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : 0;
            const isNearLimit = pct >= 80;

            return (
              <div
                key={sess.session_id}
                className="bg-[#0b0e14] border border-[#dddee8]/15 hover:border-[#a99df2]/30 rounded-sm p-6 sm:p-8 space-y-6 transition-all"
              >
                <div className="flex flex-col lg:flex-row justify-between lg:items-center gap-6">
                  {/* Left: Info */}
                  <div className="space-y-2 max-w-xl">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold text-[#a99df2]">
                        {sess.session_id}
                      </span>
                      <StatusBadge status={sess.status || "ACTIVE"} size="sm" />
                      {isNearLimit && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 text-[10px] font-mono border border-amber-500/30">
                          <AlertTriangle className="w-3 h-3" />
                          <span>HIGH UTILIZATION ({pct}%)</span>
                        </span>
                      )}
                    </div>
                    <h3 className="font-serif text-xl sm:text-2xl text-[#f0eef5]">
                      {sess.intent_description || `Session for ${sess.agent_id}`}
                    </h3>
                    <div className="text-xs text-[#8d94a1] font-mono">
                      Agent: <strong className="text-[#f0eef5]">{sess.agent_id}</strong> • Created: {sess.created_at ? new Date(sess.created_at).toLocaleDateString() : "Active"}
                    </div>
                  </div>

                  {/* Right: Numbers */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-6 items-center pt-4 lg:pt-0 border-t lg:border-t-0 border-[#dddee8]/10 font-mono">
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">
                        Declared Budget
                      </div>
                      <div className="text-base sm:text-lg font-bold text-[#f0eef5]">
                        ₹{budget.toLocaleString()}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">
                        Cumulative Spent
                      </div>
                      <div className={`text-base sm:text-lg font-bold ${isNearLimit ? "text-amber-400" : "text-emerald-400"}`}>
                        ₹{spent.toLocaleString()} ({pct}%)
                      </div>
                    </div>

                    <div className="col-span-2 sm:col-span-1">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">
                        Transactions
                      </div>
                      <div className="text-base sm:text-lg font-bold text-[#f0eef5]">
                        {sess.transaction_count || 0} / {sess.max_items || 10} items
                      </div>
                    </div>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-[#07090d] rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      pct > 90 ? "bg-rose-400" : pct > 70 ? "bg-amber-400" : "bg-emerald-400"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {/* Transactions stream inside session */}
                {sess.transactions && sess.transactions.length > 0 && (
                  <div className="pt-4 border-t border-[#dddee8]/10 space-y-2">
                    <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#8d94a1]">
                      SESSION TRANSACTIONS ({sess.transactions.length})
                    </div>
                    <div className="divide-y divide-[#dddee8]/10">
                      {sess.transactions.map((tx) => (
                        <div
                          key={tx.id}
                          onClick={() => onSelectTransaction(tx.id)}
                          className="py-2.5 flex justify-between items-center text-xs font-mono cursor-pointer hover:text-[#a99df2] transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-[#a99df2] font-bold">{tx.id}</span>
                            <span className="text-[#8d94a1]">{tx.merchant}</span>
                          </div>
                          <div className="flex items-center gap-4">
                            <span className="text-[#f0eef5] font-bold">
                              ₹{(parseFloat(tx.amount) || 0).toLocaleString()}
                            </span>
                            <StatusBadge status={tx.decision} size="sm" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ConsoleSessions;
