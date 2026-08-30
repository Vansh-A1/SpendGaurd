import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, ShieldCheck, Database, RefreshCw, AlertCircle } from "lucide-react";

export function ConsoleLayout({ currentTab, setTab, children, onSeedComplete }) {
  const [health, setHealth] = useState("checking");
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState(null);

  useEffect(() => {
    let mounted = true;
    const checkStatus = async () => {
      try {
        const res = await api.getHealth();
        if (mounted) setHealth(res?.status === "ok" ? "healthy" : "degraded");
      } catch (err) {
        if (mounted) setHealth("offline");
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleSeed = async () => {
    try {
      setSeeding(true);
      const res = await api.seedScenarios();
      setSeedMessage(`Successfully evaluated and seeded ${res.count} canonical scenarios.`);
      if (onSeedComplete) onSeedComplete();
      setTimeout(() => setSeedMessage(null), 5000);
    } catch (err) {
      setSeedMessage(`Seeding error: ${err.message}`);
      setTimeout(() => setSeedMessage(null), 5000);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#07090d] text-[#f0eef5] font-sans selection:bg-[#a99df2] selection:text-[#07090d]">
      {/* Top Console Navigation Bar */}
      <header className="sticky top-0 z-50 border-b border-[#dddee8]/10 bg-[#07090d]/90 backdrop-blur-md px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <button
              onClick={() => setTab("landing")}
              className="inline-flex items-center gap-1.5 text-xs text-[#8d94a1] hover:text-[#a99df2] transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Product</span>
            </button>

            <div className="h-4 w-px bg-[#dddee8]/15 hidden md:block" />

            <div className="flex items-center gap-2">
              <span className="font-serif text-lg font-bold tracking-tight text-[#f0eef5]">
                SPENDGUARD
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded bg-[#a99df2]/10 text-[#a99df2] border border-[#a99df2]/20">
                CONSOLE
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2 text-xs font-medium">
            {[
              { id: "overview", label: "Overview" },
              { id: "transactions", label: "Transactions" },
              { id: "review", label: "Verification Queue" },
              { id: "sessions", label: "Purchase Sessions" },
            ].map((nav) => (
              <button
                key={nav.id}
                onClick={() => setTab(nav.id)}
                className={`px-3 py-1.5 rounded-sm transition-all ${
                  currentTab === nav.id
                    ? "bg-[#dddee8]/10 text-[#f0eef5] font-semibold border-b border-[#a99df2]"
                    : "text-[#8d94a1] hover:text-[#f0eef5] hover:bg-[#dddee8]/5"
                }`}
              >
                {nav.label}
              </button>
            ))}
          </nav>

          {/* Actions & Health Status */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 rounded-sm text-[11px] font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-all disabled:opacity-50"
              title="Batch-evaluates and seeds all 110 canonical scenarios into the SQLite database"
            >
              <Database className="w-3 h-3 text-[#a99df2]" />
              <span>{seeding ? "Seeding..." : "Seed 110 Scenarios"}</span>
            </button>

            <div className="flex items-center gap-2 text-[11px] font-mono">
              <span
                className={`w-2 h-2 rounded-full ${
                  health === "healthy"
                    ? "bg-emerald-400 animate-pulse"
                    : health === "offline"
                    ? "bg-rose-400"
                    : "bg-amber-400"
                }`}
              />
              <span className="text-[#8d94a1] hidden sm:inline">
                {health === "healthy"
                  ? "Decision Engine Live"
                  : health === "offline"
                  ? "Backend Offline"
                  : "Checking API..."}
              </span>
            </div>
          </div>
        </div>

        {seedMessage && (
          <div className="max-w-7xl mx-auto mt-3 px-3 py-2 rounded bg-emerald-950/60 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            <span>{seedMessage}</span>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}

export default ConsoleLayout;
