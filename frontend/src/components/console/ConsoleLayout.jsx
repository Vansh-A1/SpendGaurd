import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, Clock3, Database, LayoutDashboard, Layers, LogOut, ReceiptText, ShieldAlert } from "lucide-react";
import "./console.css";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "simulation", label: "Simulation Lab", icon: ShieldAlert },
  { id: "transactions", label: "Transactions", icon: ReceiptText },
  { id: "review", label: "Verification Queue", icon: Clock3 },
  { id: "sessions", label: "Purchase Sessions", icon: Layers },
];

export function ConsoleLayout({ currentTab, setTab, children, onSeedComplete, user, onLogout }) {
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

  const activeNav = navigation.find((item) => item.id === currentTab);

  return (
    <div className="console-shell" data-testid="console-layout">
      <aside className="console-sidebar" data-testid="console-sidebar">
        <button className="console-brand" onClick={() => setTab("landing")} data-testid="console-brand">
          <strong>SpendGuard</strong>
          <span>Console</span>
        </button>
        <button className="console-back" onClick={() => setTab("landing")} data-testid="console-back-button">
          <ArrowLeft size={14} />
          <span>Back to Product</span>
        </button>
        <nav className="console-nav" aria-label="Console navigation" data-testid="console-navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} onClick={() => setTab(item.id)} className={currentTab === item.id ? "active" : ""} data-testid={`console-nav-${item.id}`}>
                <Icon />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="console-sidebar-foot">
          <div className="console-user" data-testid="console-current-user">
            <span>{user?.email}</span>
            <strong>{user?.role}</strong>
          </div>
          <button className="console-button console-logout" onClick={onLogout} data-testid="console-logout-button">
            <LogOut size={13} />
            <span>Sign out</span>
          </button>
          <div className={`console-status ${health}`} data-testid="console-system-status">
            <i />
            <span>{health === "healthy" ? "Decision Engine Live" : health === "offline" ? "Backend Offline" : "Checking API"}</span>
          </div>
          {seedMessage && <div className="console-seed-message" data-testid="seed-message">{seedMessage}</div>}
        </div>
      </aside>

      <div className="console-main">
        <header className="console-topbar" data-testid="console-topbar">
          <span className="console-topbar-title">{activeNav?.label || "Transaction Detail"}</span>
          <div className="console-topbar-actions">
            {user?.role === "admin" && (
              <button className="console-button" onClick={handleSeed} disabled={seeding} data-testid="seed-scenarios-button">
                <Database size={13} />
                <span>{seeding ? "Seeding..." : "Seed 110 Scenarios"}</span>
              </button>
            )}
          </div>
        </header>
        <main className="console-content" data-testid="console-content">{children}</main>
      </div>
    </div>
  );
}

export default ConsoleLayout;
