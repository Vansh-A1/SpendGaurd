import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { Search, Filter, RefreshCw, ArrowRight } from "lucide-react";

export function ConsoleTransactions({ onSelectTransaction }) {
  const [loading, setLoading] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [decisionFilter, setDecisionFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("ALL");

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

  const filteredTxs = transactions.filter((tx) => {
    if (agentFilter !== "ALL" && tx.agent_id !== agentFilter) return false;
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
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#dddee8]/10 pb-6">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
            AUDIT TRAIL
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5] font-normal mt-1">
            Transaction Activity Feed
          </h1>
          <p className="text-[#8d94a1] text-sm mt-1">
            Immutable log of multi-agent evaluations, policy checks, and gateway hold states.
          </p>
        </div>

        <button
          onClick={loadTransactions}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Search Controls */}
      <div className="flex flex-col md:flex-row gap-4 justify-between items-stretch md:items-center">
        {/* Decision Filter Pills */}
        <div className="flex items-center gap-1.5 font-mono text-xs overflow-x-auto pb-2 md:pb-0">
          {["ALL", "ALLOW", "VERIFY", "BLOCK"].map((status) => (
            <button
              key={status}
              onClick={() => setDecisionFilter(status)}
              className={`px-3 py-1.5 rounded-sm font-semibold tracking-wider uppercase transition-all ${
                decisionFilter === status
                  ? "bg-[#f0eef5] text-[#07090d]"
                  : "bg-[#0b0e14] border border-[#dddee8]/15 text-[#8d94a1] hover:text-[#f0eef5]"
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        {/* Search & Agent Filter */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#8d94a1]" />
            <input
              type="text"
              placeholder="Search ID, Merchant, SKU..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm pl-9 pr-3 py-1.5 text-xs text-[#f0eef5] placeholder:text-[#8d94a1]/60 focus:outline-none focus:border-[#a99df2]"
            />
          </div>

          {agents.length > 0 && (
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm px-3 py-1.5 text-xs text-[#8d94a1] focus:outline-none focus:border-[#a99df2]"
            >
              <option value="ALL">All Agents</option>
              {agents.map((ag) => (
                <option key={ag} value={ag}>
                  {ag}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Transaction List Feed */}
      <div className="space-y-3">
        {loading && transactions.length === 0 ? (
          <div className="py-20 text-center text-sm font-mono text-[#8d94a1]">
            Loading audit records...
          </div>
        ) : filteredTxs.length === 0 ? (
          <div className="p-12 border border-[#dddee8]/10 bg-[#0b0e14] rounded-sm text-center text-sm font-mono text-[#8d94a1]">
            No transactions match the selected filter criteria.
          </div>
        ) : (
          filteredTxs.map((tx) => (
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
                    {tx.session_id && (
                      <span className="text-[10px] font-mono text-[#8d94a1] bg-[#07090d] px-1.5 py-0.5 rounded border border-[#dddee8]/10">
                        Session: {tx.session_id}
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
                    {tx.confidence !== undefined && (
                      <>
                        <span>•</span>
                        <span>Confidence: <strong className="text-[#f0eef5]">{(parseFloat(tx.confidence) * 100).toFixed(0)}%</strong></span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between md:justify-end gap-6 pt-3 md:pt-0 border-t md:border-t-0 border-[#dddee8]/10 font-mono">
                  <div className="text-left md:text-right">
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
          ))
        )}
      </div>
    </div>
  );
}

export default ConsoleTransactions;
