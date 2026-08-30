import React, { useState } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, LockKeyhole, ShieldCheck, UserCheck, Eye } from "lucide-react";
import "./console.css";

export function ConsoleAuth({ onSuccess, onBack }) {
  const [email, setEmail] = useState("admin@spendguard.ai");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    if (event) event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const user = await api.login(email, password);
      onSuccess(user);
    } catch (err) {
      setError(err.message || "Unable to sign in. Please verify the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (roleEmail, rolePass) => {
    setEmail(roleEmail);
    setPassword(rolePass);
    setError("");
  };

  return (
    <main className="auth-shell" data-testid="console-auth-page">
      <button className="console-back" onClick={onBack} data-testid="auth-back-button">
        <ArrowLeft size={14} />
        <span>Back to Product</span>
      </button>

      <section className="auth-panel">
        <span className="console-kicker">Restricted Console</span>
        <h1>Operator sign in</h1>
        <p>Access transaction controls with an authorized SpendGuard role.</p>

        {/* Quick Role Fill Shortcuts */}
        <div className="mb-4 pt-2 pb-1">
          <span className="text-[10px] font-mono text-[#8d94a1] uppercase tracking-wider block mb-2">
            Quick Fill Demo Roles:
          </span>
          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            <button
              type="button"
              onClick={() => handleQuickFill("admin@spendguard.ai", "admin123")}
              className="px-2 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/20 hover:border-[#a99df2] text-[#f0eef5] text-center transition-colors flex items-center justify-center gap-1"
            >
              <ShieldCheck className="w-3 h-3 text-[#a99df2]" />
              <span>Admin</span>
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill("operator@spendguard.ai", "operator123")}
              className="px-2 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/20 hover:border-[#a99df2] text-[#f0eef5] text-center transition-colors flex items-center justify-center gap-1"
            >
              <UserCheck className="w-3 h-3 text-amber-400" />
              <span>Operator</span>
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill("viewer@spendguard.ai", "viewer123")}
              className="px-2 py-1.5 rounded bg-[#10141e] border border-[#dddee8]/20 hover:border-[#a99df2] text-[#f0eef5] text-center transition-colors flex items-center justify-center gap-1"
            >
              <Eye className="w-3 h-3 text-blue-400" />
              <span>Viewer</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} data-testid="console-login-form">
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              data-testid="login-email-input"
            />
          </label>
          <label className="auth-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              data-testid="login-password-input"
            />
          </label>
          {error && <div className="auth-error" data-testid="login-error">{error}</div>}
          <button
            className="console-button-primary auth-submit"
            type="submit"
            disabled={loading}
            data-testid="login-submit-button"
          >
            <LockKeyhole size={14} />
            <span>{loading ? "Signing in..." : "Sign in to Console"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}

export default ConsoleAuth;
