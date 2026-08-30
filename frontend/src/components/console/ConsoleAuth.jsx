import React, { useState } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import "./console.css";

export function ConsoleAuth({ onSuccess, onBack }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const user = await api.login(email, password);
      onSuccess(user);
    } catch (err) {
      setError(err.message || "Unable to sign in");
    } finally {
      setLoading(false);
    }
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
        <form onSubmit={handleSubmit} data-testid="console-login-form">
          <label className="auth-field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required data-testid="login-email-input" />
          </label>
          <label className="auth-field">
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required data-testid="login-password-input" />
          </label>
          {error && <div className="auth-error" data-testid="login-error">{error}</div>}
          <button className="console-button-primary auth-submit" type="submit" disabled={loading} data-testid="login-submit-button">
            <LockKeyhole size={14} />
            <span>{loading ? "Signing in..." : "Sign in"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}

export default ConsoleAuth;
