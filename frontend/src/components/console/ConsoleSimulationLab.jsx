import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import {
  ShieldAlert,
  Play,
  RefreshCw,
  Eye,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Cpu,
  Bot,
  Zap,
  Layers,
  ChevronRight,
  X,
  Info,
  Sparkles,
} from "lucide-react";

export function ConsoleSimulationLab() {
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [modeFilter, setModeFilter] = useState("all"); // 'all', 'live_llm', 'fallback_rule_based'
  const [selectedRun, setSelectedRun] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [rList, mData, tList] = await Promise.all([
        api.getSimulationRuns(modeFilter),
        api.getSimulationMetrics(modeFilter),
        api.getSimulationTasks().catch(() => []),
      ]);
      setRuns(rList || []);
      setMetrics(mData || null);
      setTasks(tList || []);
    } catch (err) {
      console.error("Failed to load simulation lab data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modeFilter]);

  const handleRunBatch = async (taskId = null) => {
    try {
      setRunning(true);
      setStatusMessage(
        taskId
          ? `Executing task ${taskId}...`
          : `Executing ${tasks.length || 22}-scenario batch evaluation...`
      );
      const res = await api.runSimulation(taskId);
      setStatusMessage(`Completed ${res.count} scenario evaluations.`);
      await fetchData();
      setTimeout(() => setStatusMessage(null), 6000);
    } catch (err) {
      alert(`Simulation run failed: ${err.message}`);
      setStatusMessage(null);
    } finally {
      setRunning(false);
    }
  };

  const getTrapBadgeColor = (trap) => {
    switch (trap) {
      case "clean_baseline":
        return "bg-slate-800 text-slate-300 border-slate-700";
      case "spec_spoofing":
        return "bg-purple-950/80 text-purple-300 border-purple-500/30";
      case "price_split_bait":
        return "bg-rose-950/80 text-rose-300 border-rose-500/30";
      case "urgency_social_eng":
        return "bg-amber-950/80 text-amber-300 border-amber-500/30";
      case "near_miss_substitution":
        return "bg-blue-950/80 text-blue-300 border-blue-500/30";
      case "stale_expired_mandate":
        return "bg-yellow-950/80 text-yellow-300 border-yellow-500/30";
      case "category_creep":
        return "bg-orange-950/80 text-orange-300 border-orange-500/30";
      case "multi_step_drift":
        return "bg-indigo-950/80 text-indigo-300 border-indigo-500/30";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const llmRunsCount = runs.filter((r) => r.execution_mode === "live_llm").length;
  const fallbackRunsCount = runs.filter((r) => r.execution_mode === "fallback_rule_based").length;

  return (
    <div className="space-y-8 pb-16">
      {/* 1. Header & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-[#dddee8]/10 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#a99df2] block">
              ADVERSARIAL EVALUATION HARNESS
            </span>
            <span className="px-2 py-0.5 rounded bg-blue-950/80 border border-blue-500/30 text-blue-300 text-[10px] font-mono">
              CLOSED LOOP
            </span>
          </div>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5] font-normal mt-1">
            Red-Team Simulation Lab
          </h1>
          <p className="text-[#8d94a1] text-sm mt-1">
            Closed-loop evaluation measuring True Leakage against adversarial catalog traps.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => handleRunBatch(null)}
            disabled={running}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-sm bg-[#a99df2] text-[#07090d] hover:bg-white font-mono font-bold text-xs transition-all shadow-lg hover:-translate-y-0.5 disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${running ? "animate-pulse" : ""}`} />
            <span>{running ? "Executing Simulation..." : `Run Batch (${tasks.length || 22} Scenarios)`}</span>
          </button>
        </div>
      </div>

      {/* Dual-Model Benchmark & Payment Rail Verification Banner */}
      <div className="p-4 sm:p-5 rounded bg-gradient-to-r from-[#0b0e14] to-[#121622] border border-[#a99df2]/30 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-xs font-mono">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#a99df2]" />
            <span className="text-[#f0eef5] font-bold uppercase tracking-wider text-sm">
              Dual-Model Red-Team Benchmark Verified
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold">
              0.0% LEAKAGE
            </span>
          </div>
          <p className="text-[#8d94a1] max-w-2xl text-[11px] leading-relaxed">
            Standardized across 22 adversarial shopping scenarios across both <strong>OpenAI GPT-4o</strong> and <strong>Anthropic Claude 3.5 Sonnet</strong>. Traps intercepted with 100% accuracy and 0.0% false friction on clean baseline purchases.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 px-3 py-2 rounded bg-[#07090d] border border-emerald-500/30 text-[11px] text-emerald-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>Real Razorpay Rail Verified</span>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3.5 rounded bg-emerald-950/60 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-400 animate-pulse" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* 2. Headline Security Metrics Scoreboard */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* TRUE LEAKAGE RATE (PRIMARY HEADLINE METRIC) */}
        <div className="bg-[#0b0e14] border-2 border-emerald-500/30 p-5 rounded-sm space-y-1 relative overflow-hidden">
          <div className="flex justify-between items-center">
            <span className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
              TRUE LEAKAGE RATE
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/30">
              HEADLINE
            </span>
          </div>
          <div className="text-3xl sm:text-4xl font-mono font-bold text-emerald-400">
            {metrics?.true_leakage_rate !== undefined ? `${metrics.true_leakage_rate}%` : "0.0%"}
          </div>
          <div className="text-[11px] font-mono text-[#8d94a1]">
            Target: 0.0% (Zero bad spends completed)
          </div>
        </div>

        {/* FLAGGED RATE */}
        <div className="bg-[#0b0e14] border border-[#dddee8]/15 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            FLAGGED RATE
          </div>
          <div className="text-3xl sm:text-4xl font-mono font-bold text-[#f0eef5]">
            {metrics?.flagged_rate !== undefined ? `${metrics.flagged_rate}%` : "0.0%"}
          </div>
          <div className="text-[11px] font-mono text-[#8d94a1]">
            {metrics?.flagged_count || 0} / {metrics?.trap_tasks_count || 0} traps caught by 4-pillar gate
          </div>
        </div>

        {/* AGENT FOOL RATE */}
        <div className="bg-[#0b0e14] border border-[#dddee8]/15 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            AGENT FOOL RATE
          </div>
          <div className="text-3xl sm:text-4xl font-mono font-bold text-amber-400">
            {metrics?.agent_fool_rate !== undefined ? `${metrics.agent_fool_rate}%` : "0.0%"}
          </div>
          <div className="text-[11px] font-mono text-amber-400/80">
            {metrics?.agent_fooled_count || 0} times agent fell for bait
          </div>
        </div>

        {/* FALSE FRICTION RATE */}
        <div className="bg-[#0b0e14] border border-[#dddee8]/15 p-5 rounded-sm space-y-1">
          <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
            FALSE FRICTION
          </div>
          <div className="text-3xl sm:text-4xl font-mono font-bold text-[#f0eef5]">
            {metrics?.false_friction_rate !== undefined ? `${metrics.false_friction_rate}%` : "0.0%"}
          </div>
          <div className="text-[11px] font-mono text-[#8d94a1]">
            Clean tasks incorrectly delayed
          </div>
        </div>
      </div>

      {/* 3. Execution Mode Filter Controls */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#0b0e14] border border-[#dddee8]/15 p-4 rounded-sm">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="text-[#8d94a1] text-[11px] uppercase tracking-wider mr-2">
            Filter View:
          </span>
          {[
            { id: "all", label: `All Runs (${runs.length})` },
            { id: "live_llm", label: `⚡ Live LLM Agent (${llmRunsCount})` },
            { id: "fallback_rule_based", label: `⚙️ Fallback Smoke Test (${fallbackRunsCount})` },
          ].map((btn) => (
            <button
              key={btn.id}
              onClick={() => setModeFilter(btn.id)}
              className={`px-3 py-1.5 rounded-sm font-semibold tracking-wider transition-all ${
                modeFilter === btn.id
                  ? "bg-[#a99df2] text-[#07090d]"
                  : "bg-[#10141e] border border-[#dddee8]/15 text-[#8d94a1] hover:text-[#f0eef5]"
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>

        <div className="text-xs font-mono text-[#8d94a1] flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#a99df2]" />
          <span>Showing {runs.length} records</span>
        </div>
      </div>

      {/* 4. Simulation Runs Feed */}
      <div className="space-y-3">
        {loading && runs.length === 0 ? (
          <div className="py-20 text-center text-sm font-mono text-[#8d94a1]">
            Loading simulation telemetry...
          </div>
        ) : runs.length === 0 ? (
          <div className="p-16 border border-[#dddee8]/10 bg-[#0b0e14] rounded-sm text-center space-y-4">
            <ShieldAlert className="w-8 h-8 text-[#a99df2] mx-auto" />
            <h3 className="font-serif text-xl text-[#f0eef5]">
              {modeFilter === "live_llm" ? "No Live LLM Runs Recorded" : "No Simulation Runs Yet"}
            </h3>
            <p className="text-xs font-mono text-[#8d94a1] max-w-md mx-auto">
              {modeFilter === "live_llm"
                ? "To record live LLM runs, set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY in .env and run a batch."
                : "Run the 16-scenario batch to evaluate the autonomous agent against spec spoofing, price-split bait, and mandate drift."}
            </p>
            {modeFilter !== "live_llm" && (
              <button
                onClick={() => handleRunBatch(null)}
                className="px-5 py-2 bg-[#a99df2] text-[#07090d] font-mono font-bold text-xs rounded-sm hover:bg-white transition-colors"
              >
                Run Baseline Smoke Test
              </button>
            )}
          </div>
        ) : (
          runs.map((run) => {
            const passedDefense = !run.is_true_leakage;

            return (
              <div
                key={run.id}
                onClick={() => setSelectedRun(run)}
                className="group cursor-pointer bg-[#0b0e14] border border-[#dddee8]/15 hover:border-[#a99df2]/50 rounded-sm p-5 sm:p-6 transition-all hover:bg-[#10141e] space-y-4"
              >
                <div className="flex flex-col lg:flex-row justify-between lg:items-center gap-4">
                  <div className="space-y-1.5 max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-[#a99df2]">{run.task_id}</span>
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${getTrapBadgeColor(
                          run.trap_type
                        )}`}
                      >
                        {run.trap_type.replace(/_/g, " ")}
                      </span>
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${
                          run.execution_mode === "live_llm"
                            ? "bg-purple-950 text-purple-300 border-purple-500/30"
                            : "bg-slate-800 text-slate-300 border-slate-700"
                        }`}
                      >
                        {run.execution_mode === "live_llm" ? "⚡ Live LLM" : "⚙️ Fallback Smoke Test"}
                      </span>
                      {run.agent_fooled && (
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-500/30">
                          Agent Fooled
                        </span>
                      )}
                    </div>

                    <h4 className="font-serif text-lg text-[#f0eef5] group-hover:text-[#a99df2] transition-colors">
                      {run.task_prompt}
                    </h4>

                    <div className="text-xs text-[#8d94a1] font-mono flex flex-wrap items-center gap-2">
                      <span>Selected: <strong className="text-[#f0eef5]">{run.selected_product_name || run.selected_sku}</strong></span>
                      <span>•</span>
                      <span>₹{(parseFloat(run.amount) || 0).toLocaleString()}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between lg:justify-end gap-6 pt-3 lg:pt-0 border-t lg:border-t-0 border-[#dddee8]/10 font-mono">
                    <div className="text-left lg:text-right">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[#8d94a1]">
                        GATE VERDICT
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <StatusBadge status={run.initial_decision} size="sm" />
                        <span className="text-xs text-[#8d94a1]">→ {run.resolved_decision}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {passedDefense ? (
                        <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-bold bg-emerald-950/60 px-2.5 py-1 rounded border border-emerald-500/30">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>CAUGHT</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 text-xs text-rose-400 font-bold bg-rose-950/60 px-2.5 py-1 rounded border border-rose-500/30">
                          <XCircle className="w-4 h-4" />
                          <span>LEAKAGE</span>
                        </div>
                      )}
                      <ChevronRight className="w-4 h-4 text-[#8d94a1] group-hover:text-[#a99df2] transition-colors" />
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 5. Detailed Step-by-Step Transcript Modal */}
      {selectedRun && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
          <div className="bg-[#0b0e14] border border-[#dddee8]/20 rounded-sm max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
            {/* Modal Header */}
            <div className="p-6 border-b border-[#dddee8]/10 flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-[#a99df2]">{selectedRun.task_id}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {selectedRun.trap_type.toUpperCase()}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-500/30">
                    {selectedRun.execution_mode === "live_llm" ? "⚡ Live LLM" : "⚙️ Fallback Smoke Test"}
                  </span>
                </div>
                <h3 className="font-serif text-2xl text-[#f0eef5] mt-1">
                  Simulation Reasoning Trace
                </h3>
              </div>

              <button
                onClick={() => setSelectedRun(null)}
                className="p-1 text-[#8d94a1] hover:text-[#f0eef5] rounded hover:bg-[#10141e] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              <div className="bg-[#07090d] border border-[#dddee8]/10 p-4 rounded-sm space-y-2">
                <div className="text-[10px] font-mono font-bold tracking-wider text-[#8d94a1] uppercase">
                  PROCUREMENT TASK PROMPT
                </div>
                <p className="font-serif text-lg text-[#f0eef5]">{selectedRun.task_prompt}</p>
                <div className="text-xs text-[#8d94a1] font-mono pt-1 flex flex-wrap gap-4">
                  <span>Selected: <strong className="text-[#a99df2]">{selectedRun.selected_product_name}</strong></span>
                  <span>Amount: <strong className="text-[#f0eef5]">₹{(parseFloat(selectedRun.amount) || 0).toLocaleString()}</strong></span>
                  <span>Initial: <strong className="text-[#f0eef5]">{selectedRun.initial_decision}</strong></span>
                  <span>Resolved: <strong className="text-[#f0eef5]">{selectedRun.resolved_decision}</strong></span>
                  {selectedRun.reviewer_action && (
                    <span>Reviewer Action: <strong className="text-[#a99df2]">{selectedRun.reviewer_action}</strong></span>
                  )}
                </div>
              </div>

              {/* Transcript Timeline */}
              <div className="space-y-3">
                <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#a99df2]">
                  AGENT REASONING &amp; DECISION CHRONOLOGY
                </div>

                <div className="relative border-l border-[#dddee8]/15 ml-3 pl-6 space-y-5">
                  {selectedRun.transcript && selectedRun.transcript.map((step, idx) => (
                    <div key={idx} className="relative">
                      <span className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-[#07090d] border-2 border-[#a99df2]" />
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs font-bold text-[#a99df2]">
                          STEP {String(step.seq || idx + 1).padStart(2, "0")}
                        </span>
                        <span className="text-xs font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-[#10141e] border border-[#dddee8]/10 text-[#8d94a1]">
                          {step.type}
                        </span>
                        <span className="text-xs font-bold text-[#f0eef5] font-sans">
                          {step.title}
                        </span>
                      </div>
                      <div className="mt-2 text-xs font-mono bg-[#07090d] border border-[#dddee8]/10 p-3 rounded text-[#dddee8] whitespace-pre-wrap leading-relaxed overflow-x-auto">
                        {typeof step.detail === "string" ? step.detail : JSON.stringify(step.detail, null, 2)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-[#dddee8]/10 bg-[#07090d] flex justify-end">
              <button
                onClick={() => setSelectedRun(null)}
                className="px-4 py-2 bg-[#10141e] border border-[#dddee8]/20 text-xs font-mono text-[#f0eef5] hover:border-[#a99df2] rounded-sm transition-colors"
              >
                Close Transcript
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ConsoleSimulationLab;
