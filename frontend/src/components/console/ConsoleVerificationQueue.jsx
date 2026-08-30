import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Clock, Check, X, ArrowUpRight, RefreshCw, AlertTriangle, ShieldCheck } from "lucide-react";

export function ConsoleVerificationQueue({ onSelectTransaction }) {
  const [loading, setLoading] = useState(true);
  const [escalations, setEscalations] = useState([]);
  const [resolvingId, setResolvingId] = useState(null);
  const [feedback, setFeedback] = useState(null);

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
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#dddee8]/10 pb-6">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
            HUMAN-IN-THE-LOOP RESOLUTION
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5] font-normal mt-1">
            Needs your attention
          </h1>
          <p className="text-[#8d94a1] text-sm mt-1">
            Transactions placed on 15-minute SLA authorization holds requiring operator approval.
          </p>
        </div>

        <button
          onClick={loadEscalations}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {feedback && (
        <div
          className={`p-4 rounded-sm border text-xs font-mono flex items-center gap-2 ${
            feedback.type === "approved"
              ? "bg-emerald-950/60 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/60 border-rose-500/30 text-rose-300"
          }`}
        >
          {feedback.type === "approved" ? (
            <ShieldCheck className="w-4 h-4" />
          ) : (
            <AlertTriangle className="w-4 h-4" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Escalations List */}
      <div className="space-y-4">
        {loading && escalations.length === 0 ? (
          <div className="py-20 text-center text-sm font-mono text-[#8d94a1]">
            Checking active escalation queue...
          </div>
        ) : escalations.length === 0 ? (
          <div className="p-16 border border-[#dddee8]/10 bg-[#0b0e14] rounded-sm text-center space-y-3">
            <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
            <h3 className="font-serif text-xl text-[#f0eef5]">All Clear</h3>
            <p className="text-xs font-mono text-[#8d94a1] max-w-md mx-auto">
              No pending pre-authorization holds in the escalation queue. All transactions have been cleanly resolved.
            </p>
          </div>
        ) : (
          escalations.map((item) => {
            const isResolving = resolvingId === item.transaction_id;

            return (
              <div
                key={item.id || item.transaction_id}
                className="bg-[#0b0e14] border border-[#dddee8]/15 hover:border-[#a99df2]/30 rounded-sm p-6 sm:p-8 space-y-6 transition-all"
              >
                <div className="flex flex-col lg:flex-row justify-between lg:items-center gap-4">
                  <div className="space-y-1 max-w-2xl">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => onSelectTransaction(item.transaction_id)}
                        className="font-mono text-sm font-bold text-[#a99df2] hover:underline flex items-center gap-1"
                      >
                        <span>{item.transaction_id}</span>
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </button>
                      <StatusBadge status="VERIFY" size="sm" />
                      {item.payment_hold_id && (
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-500/30">
                          PRE-AUTH HOLD: {item.payment_hold_id}
                        </span>
                      )}
                    </div>

                    <h3 className="font-serif text-2xl text-[#f0eef5] mt-1">
                      Agent: {item.agent_id}
                    </h3>

                    <div className="text-xs text-[#8d94a1] font-mono pt-1">
                      Escalated at: {item.created_at ? new Date(item.created_at).toLocaleTimeString() : "Recent"}
                    </div>
                  </div>

                  <div className="flex flex-row lg:flex-col justify-between lg:items-end gap-2 pt-3 lg:pt-0 border-t lg:border-t-0 border-[#dddee8]/10 font-mono">
                    <div className="lg:text-right">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">
                        Hold Amount
                      </div>
                      <div className="text-2xl font-bold text-[#f0eef5]">
                        ₹{(parseFloat(item.amount) || 0).toLocaleString()}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#07090d] border border-amber-500/30 text-amber-400 text-xs font-mono">
                      <Clock className="w-3.5 h-3.5 animate-pulse" />
                      <span>
                        SLA: {item.sla_remaining_minutes !== undefined ? `${item.sla_remaining_minutes.toFixed(1)}m remaining` : "15m hold"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-[#07090d] border border-[#dddee8]/10 p-4 rounded-sm space-y-1">
                  <div className="text-[10px] font-mono font-bold tracking-wider text-[#8d94a1] uppercase">
                    ESCALATION CONTEXT
                  </div>
                  <p className="text-xs text-[#dddee8] leading-relaxed font-sans">
                    {item.reason || "Autonomous agent initiated a purchase requiring operator confirmation (e.g. brand substitution or stale mandate)."}
                  </p>
                </div>

                <div className="flex justify-end items-center gap-3 pt-2">
                  <button
                    onClick={() => handleAction(item.transaction_id, false)}
                    disabled={isResolving}
                    className="px-4 py-2 border border-rose-500/40 text-rose-400 hover:bg-rose-950/40 rounded-sm text-xs font-mono font-semibold tracking-wide transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" />
                    <span>Reject &amp; Void Hold</span>
                  </button>
                  <button
                    onClick={() => handleAction(item.transaction_id, true)}
                    disabled={isResolving}
                    className="px-5 py-2 bg-[#f0eef5] text-[#07090d] hover:bg-white rounded-sm text-xs font-mono font-bold tracking-wide transition-all hover:-translate-y-0.5 flex items-center gap-1.5 shadow-md disabled:opacity-50"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Approve &amp; Capture Payment</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ConsoleVerificationQueue;
