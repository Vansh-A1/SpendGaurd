import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowUpRight, ChevronDown, RefreshCw } from "lucide-react";
import { jsPDF } from "jspdf";
import "@/App.css";

import { api } from "@/lib/api";
import { ConsoleLayout } from "@/components/console/ConsoleLayout";
import { ConsoleOverview } from "@/components/console/ConsoleOverview";
import { ConsoleTransactions } from "@/components/console/ConsoleTransactions";
import { ConsoleTransactionDetail } from "@/components/console/ConsoleTransactionDetail";
import { ConsoleVerificationQueue } from "@/components/console/ConsoleVerificationQueue";
import { ConsoleSessions } from "@/components/console/ConsoleSessions";
import { ConsoleAuth } from "@/components/console/ConsoleAuth";
import { ConsoleSimulationLab } from "@/components/console/ConsoleSimulationLab";

const checks = [
  { key: "01", name: "AUTHORITY", copy: "Can the agent make this purchase?", detail: "Verified spending limit and mandate.", plain: "The agent can spend only within the permissions and limits you set." },
  { key: "02", name: "INTENT", copy: "Is this what the user asked for?", detail: "Sony WH-1000XM6, black, under ₹35,000.", plain: "The purchase must match what you actually asked for, not just the category." },
  { key: "03", name: "BEHAVIOR", copy: "Does the agent still behave normally?", detail: "Session pattern remains within baseline.", plain: "SpendGuard watches the current session for unusual or risky spending patterns." },
  { key: "04", name: "EVIDENCE", copy: "Can the product claims be proven?", detail: "Model specification conflicts at checkout.", plain: "Important product claims are checked against observable merchant information." },
];

const events = [
  "Intent created",
  "Search initiated",
  "17 products found",
  "9 rejected — over budget",
  "3 rejected — requirement mismatch",
  "XM6 unavailable",
  "XM5 selected",
  "Human approval requested",
];

const decisionSteps = [
  ["PURCHASE REQUEST", "Sony WH-1000XM6 · black · under ₹35,000", "RECEIVED"],
  ["AUTHORITY", "Within approved limit", "PASS"],
  ["INTENT", "Product family matched", "PASS"],
  ["BEHAVIOR", "Session pattern normal", "PASS"],
  ["EVIDENCE", "Merchant model mismatch", "CONFLICT"],
];

const fallbackReceiptData = {
  id: "TX-000184",
  requested: "Sony WH-1000XM6",
  intentDetail: "Black · ≤ ₹35,000",
  selected: "Sony WH-1000XM5",
  amount: "₹28,000",
  decision: "VERIFY",
  reason: "The requested XM6 was unavailable. The agent selected XM5 as a substitution requiring review.",
  checks: [["AUTHORITY", "PASS"], ["INTENT", "SUBSTITUTION"], ["EVIDENCE", "VERIFIED"], ["BEHAVIOR", "LOW RISK"]],
};

const canonicalScenarios = [
  {
    id: "allow",
    label: "ALLOW",
    kicker: "Exact match",
    title: "Sony WH-1000XM5",
    detail: "Black · ₹29,990",
    summary: "Every signal agrees. The purchase proceeds without interruption.",
    txRequest: {
      id: "tx_0101_demo",
      agent_id: "agent_shopping_01",
      mandate_id: "mandate_shop_01",
      user_intent_id: "intent_0101",
      claimed_product: { brand: "Sony", model: "WH-1000XM5", category: "electronics", specs: { anc: true, battery_hours: 30, color: "black", form_factor: "over-ear", driver_mm: 30 } },
      actual_sku: "ELEC-SONY-WH1000XM5-BLK",
      amount: 29990,
      category: "electronics",
      merchant: "Sony Center",
      timestamp: "2026-08-30T12:00:00Z",
      scenario_type: "legitimate_unusual",
      expected_decision: "ALLOW",
    },
    defaultSteps: [
      ["AUTHORITY", "Purchase mandate within limit", "PASS"],
      ["INTENT", "Exact model and color matched", "PASS"],
      ["BEHAVIOR", "Session pattern remains normal", "PASS"],
      ["EVIDENCE", "Merchant model verified", "VERIFIED"],
    ],
  },
  {
    id: "verify",
    label: "VERIFY",
    kicker: "Substitution",
    title: "Sony WH-1000XM5",
    detail: "Black · ₹29,990",
    summary: "The requested XM6 is unavailable, so the substitution requires review.",
    txRequest: {
      id: "tx_0035_demo",
      agent_id: "agent_shopping_01",
      mandate_id: "mandate_shop_01",
      user_intent_id: "intent_0035",
      claimed_product: { brand: "Sony", model: "WH-1000XM5", category: "electronics", specs: { anc: true, battery_hours: 30, color: "black", form_factor: "over-ear", driver_mm: 30 } },
      actual_sku: "ELEC-SONY-WH1000XM5-BLK",
      amount: 29990,
      category: "electronics",
      merchant: "Sony Center",
      timestamp: "2026-08-30T12:00:00Z",
      scenario_type: "substitution",
      expected_decision: "VERIFY",
    },
    defaultSteps: [
      ["AUTHORITY", "Purchase mandate within limit", "PASS"],
      ["INTENT", "XM5 selected as substitution", "SUBSTITUTION"],
      ["BEHAVIOR", "Session risk remains low", "PASS"],
      ["EVIDENCE", "Merchant specification verified", "VERIFIED"],
    ],
  },
  {
    id: "block",
    label: "BLOCK",
    kicker: "Evidence conflict",
    title: "Sony WH-1000XM5",
    detail: "Black · under ₹35,000",
    summary: "The merchant model cannot be verified, so money does not move.",
    txRequest: {
      id: "tx_0066_demo",
      agent_id: "agent_shopping_01",
      mandate_id: "mandate_shop_01",
      user_intent_id: "intent_0066",
      claimed_product: { brand: "Sony", model: "WH-1000XM5", category: "electronics", specs: { driver_mm: 50, anc: true, battery_hours: 30 } },
      actual_sku: "ELEC-SONY-WH1000XM5-BLK",
      amount: 29990,
      category: "electronics",
      merchant: "Sony Center",
      timestamp: "2026-08-30T12:00:00Z",
      scenario_type: "evidence_conflict",
      expected_decision: "BLOCK",
    },
    defaultSteps: [
      ["AUTHORITY", "Purchase mandate within limit", "PASS"],
      ["INTENT", "Product family matched", "PASS"],
      ["BEHAVIOR", "Session pattern remains normal", "PASS"],
      ["EVIDENCE", "Merchant model mismatch", "CONFLICT"],
    ],
  },
];

function Eyebrow({ children }) {
  return <span className="eyebrow" data-testid="section-eyebrow">{children}</span>;
}

function Reveal({ children, className = "", ...props }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      {...props}
    >
      {children}
    </motion.div>
  );
}

function CountUp({ value }) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(reduced ? value : 0);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return undefined;
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      const start = performance.now();
      const duration = 1400;
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      observer.disconnect();
    }, { threshold: 0.45 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [reduced, value]);

  return <strong ref={ref} data-testid="metric-value">{display}</strong>;
}

function ScenarioLibrary() {
  const reduced = useReducedMotion();
  const [scenarioId, setScenarioId] = useState("allow");
  const [step, setStep] = useState(canonicalScenarios[0].defaultSteps.length - 1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [realResults, setRealResults] = useState({});

  const scenario = canonicalScenarios.find((item) => item.id === scenarioId) || canonicalScenarios[0];

  // Execute real evaluation on tab change
  useEffect(() => {
    let mounted = true;
    const runEvaluation = async () => {
      try {
        const res = await api.evaluateTransaction(scenario.txRequest);
        if (mounted && res) {
          const pillars = res.pillars || {};
          const steps = [
            ["AUTHORITY", pillars.authority?.reason || "Limit check verified", pillars.authority?.passed !== false ? "PASS" : "FAIL"],
            ["INTENT", pillars.intent?.reason || "Intent fidelity checked", pillars.intent?.substitution ? "SUBSTITUTION" : pillars.intent?.passed !== false ? "PASS" : "FAIL"],
            ["BEHAVIOR", pillars.behavior?.reason || "Velocity score normal", pillars.behavior?.risk_score > 0.7 ? "FAIL" : "PASS"],
            ["EVIDENCE", pillars.evidence?.reason || "Catalog spec verified", pillars.evidence?.conflict ? "CONFLICT" : "VERIFIED"],
          ];
          setRealResults((prev) => ({
            ...prev,
            [scenario.id]: {
              decision: res.decision,
              steps,
              reason: res.decision_reason,
            },
          }));
        }
      } catch (err) {
        // Fallback gracefully to preset steps if backend is warming up
      }
    };
    runEvaluation();
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario.id]);

  const currentScenarioData = realResults[scenarioId] || {
    decision: scenario.label,
    steps: scenario.defaultSteps,
    reason: scenario.summary,
  };

  const stepsToRender = currentScenarioData.steps || scenario.defaultSteps;

  useEffect(() => {
    if (!isPlaying) return undefined;
    if (step === stepsToRender.length - 1) {
      setIsPlaying(false);
      return undefined;
    }
    const timer = setTimeout(() => setStep((current) => current + 1), 950);
    return () => clearTimeout(timer);
  }, [isPlaying, stepsToRender.length, step]);

  const playScenario = (id = scenarioId) => {
    const next = canonicalScenarios.find((item) => item.id === id) || canonicalScenarios[0];
    setScenarioId(next.id);
    if (reduced) {
      setStep(stepsToRender.length - 1);
      setIsPlaying(false);
      return;
    }
    setStep(0);
    setIsPlaying(true);
  };

  return (
    <section className="section scenarios" data-testid="scenario-library-section">
      <div className="section-wrap scenario-layout">
        <Reveal className="scenario-intro">
          <span className="chapter">07 / SCENARIO LIBRARY</span>
          <h2>THREE OUTCOMES.<br /><span>ONE TRUST MODEL.</span></h2>
          <p>Compare how the same four checks produce allow, verify, and block decisions in the live decision engine.</p>
          <div className="scenario-list" role="tablist" aria-label="SpendGuard decision scenarios">
            {canonicalScenarios.map((item, index) => (
              <button
                className={`scenario-tab ${item.id === scenarioId ? "active" : ""}`}
                key={item.id}
                onClick={() => playScenario(item.id)}
                role="tab"
                aria-selected={item.id === scenarioId}
                data-testid={`scenario-tab-${item.id}`}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{item.label}</strong>
                <small>{item.kicker}</small>
              </button>
            ))}
          </div>
        </Reveal>
        <Reveal className="scenario-stage" data-testid="scenario-stage">
          <div className="scenario-heading">
            <span>{scenario.kicker}</span>
            <h3 data-testid="scenario-title">{scenario.title}</h3>
            <p>{scenario.detail}</p>
          </div>
          <div className="scenario-steps">
            {stepsToRender.map(([name, copy, state], index) => (
              <div
                className={`scenario-step ${index <= step ? "active" : ""}${isPlaying && index === step ? " current" : ""}`}
                key={name}
                data-testid={`scenario-step-${name.toLowerCase()}`}
              >
                <span>{name}</span>
                <p>{copy}</p>
                <b>{state}</b>
              </div>
            ))}
          </div>
          <div className="scenario-footer">
            <div>
              <span aria-live="polite" data-testid="scenario-status">
                {isPlaying ? stepsToRender[step][0] : "BACKEND DECISION"}
              </span>
              <strong className={`scenario-result ${scenario.id}`} data-testid="scenario-result">
                {currentScenarioData.decision}
              </strong>
            </div>
            <button
              className="text-button"
              onClick={() => playScenario()}
              disabled={isPlaying}
              data-testid="scenario-replay-button"
            >
              {isPlaying ? "Replaying…" : "Replay story ↻"}
            </button>
          </div>
          <p className="scenario-summary" data-testid="scenario-summary">
            {currentScenarioData.reason || scenario.summary}
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function downloadTrustReceipt(data = fallbackReceiptData) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const width = doc.internal.pageSize.getWidth();
  const height = doc.internal.pageSize.getHeight();
  const margin = 56;
  const ink = [24, 26, 34];
  const muted = [102, 105, 116];
  const accent = [95, 80, 173];
  const rule = [190, 185, 177];

  doc.setProperties({ title: `SpendGuard Trust Receipt ${data.id}` });
  doc.setFillColor(243, 241, 236);
  doc.rect(0, 0, width, height, "F");
  doc.setDrawColor(...rule);
  doc.setLineWidth(0.8);
  doc.rect(24, 24, width - 48, height - 48);

  doc.setTextColor(...ink);
  doc.setFont("courier", "bold");
  doc.setFontSize(10);
  doc.text("SPENDGUARD", margin, 66);
  doc.setFont("courier", "normal");
  doc.text(`TRUST RECEIPT / ${data.id}`, width - margin, 66, { align: "right" });
  doc.line(margin, 82, width - margin, 82);

  doc.setFont("times", "normal");
  doc.setFontSize(34);
  doc.text("Trust Receipt", margin, 128);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("AUTONOMOUS PURCHASE DECISION · EVIDENCE SEALED · 2026", margin, 148);

  doc.setTextColor(...muted);
  doc.text("USER INTENT", margin, 192);
  doc.setTextColor(...ink);
  doc.setFont("times", "normal");
  doc.setFontSize(23);
  doc.text(data.requested, margin, 220);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(...muted);
  doc.text(data.intentDetail, margin, 239);

  doc.line(margin, 262, width - margin, 262);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.text("SELECTED", margin, 292);
  doc.text("TRANSACTION", width / 2 + 16, 292);
  doc.setTextColor(...ink);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text(data.selected, margin, 314);
  doc.text(data.amount, width / 2 + 16, 314);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...muted);
  doc.text("Substitution for requested product", margin, 331);
  doc.text(`Decision ID ${data.id}`, width / 2 + 16, 331);

  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("TRUST EVALUATION", margin, 348);
  doc.text("AUTHORITY · INTENT · EVIDENCE · BEHAVIOR", width - margin, 348, { align: "right" });

  let y = 374;
  data.checks.forEach(([label, value], index) => {
    doc.setDrawColor(...rule);
    doc.line(margin, y - 19, width - margin, y - 19);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text(label, margin, y);
    doc.setTextColor(...ink);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text(value, width - margin, y, { align: "right" });
    y += index === data.checks.length - 1 ? 0 : 31;
  });

  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("FINAL DECISION", margin, 534);
  doc.setTextColor(...accent);
  doc.setFont("times", "normal");
  doc.setFontSize(42);
  doc.text(data.decision, margin, 577);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("WHY", width / 2 + 16, 534);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(...ink);
  doc.text(doc.splitTextToSize(data.reason, 205), width / 2 + 16, 552);

  doc.setDrawColor(...rule);
  doc.line(margin, 626, width - margin, 626);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("OBSERVABLE DECISION TRAIL", margin, 650);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  events.forEach((event, index) => {
    const column = index < 4 ? margin : width / 2 + 16;
    const rowY = 676 + (index % 4) * 28;
    doc.setTextColor(...accent);
    doc.text(String(index + 1).padStart(2, "0"), column, rowY);
    doc.setTextColor(...ink);
    doc.text(event, column + 28, rowY);
  });

  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("SPENDGUARD · TRUST BEFORE THE TAP.", margin, height - 54);
  doc.text("EVIDENCE-BACKED AUTONOMY", width - margin, height - 54, { align: "right" });
  doc.save(`spendguard-trust-receipt-${data.id}.pdf`);
}

function App() {
  const [view, setView] = useState("landing"); // "landing" or "console"
  const [consoleTab, setConsoleTab] = useState("overview"); // overview, transactions, review, sessions
  const [selectedTxId, setSelectedTxId] = useState(null);
  const [authUser, setAuthUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const [liveMetrics, setLiveMetrics] = useState({
    signals: 4,
    evaluations: 17,
    blocked: 12,
    trails: 1,
  });

  useEffect(() => {
    let mounted = true;
    api.getCurrentUser()
      .then((user) => { if (mounted) setAuthUser(user); })
      .catch(() => { if (mounted) setAuthUser(null); })
      .finally(() => { if (mounted) setAuthLoading(false); });
    return () => { mounted = false; };
  }, []);

  // Fetch live backend metrics on landing page
  useEffect(() => {
    let mounted = true;
    const loadLiveCounts = async () => {
      try {
        const txs = await api.getTransactions();
        if (mounted && Array.isArray(txs) && txs.length > 0) {
          const blocked = txs.filter((t) => t.decision === "BLOCK").length;
          setLiveMetrics({
            signals: 4,
            evaluations: txs.length,
            blocked: blocked,
            trails: txs.length,
          });
        }
      } catch (err) {
        // Keep default telemetry
      }
    };
    loadLiveCounts();
    return () => { mounted = false; };
  }, []);

  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const orbitScale = useTransform(scrollYProgress, [0, 0.22], [1, 1.18]);
  const orbitY = useTransform(scrollYProgress, [0, 0.22], [0, -42]);
  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  const [replayStep, setReplayStep] = useState(decisionSteps.length - 1);
  const [isReplaying, setIsReplaying] = useState(false);

  useEffect(() => {
    if (!isReplaying) return undefined;
    if (replayStep === decisionSteps.length - 1) {
      setIsReplaying(false);
      return undefined;
    }
    const timer = setTimeout(() => setReplayStep((step) => step + 1), 1050);
    return () => clearTimeout(timer);
  }, [isReplaying, replayStep]);

  const replayDecision = () => {
    if (reduced) {
      setReplayStep(decisionSteps.length - 1);
      setIsReplaying(false);
      return;
    }
    setReplayStep(0);
    setIsReplaying(true);
  };

  const openConsole = (tab = "overview") => {
    setSelectedTxId(null);
    setConsoleTab(tab);
    setView("console");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      setAuthUser(null);
      setSelectedTxId(null);
      setView("landing");
    }
  };

  // If in Console View, render Console Experience
  if (view === "console") {
    if (authLoading) return <div className="console-shell"><div className="console-loading"><RefreshCw size={14} /><span>Checking operator session...</span></div></div>;
    if (!authUser) return <ConsoleAuth onBack={() => setView("landing")} onSuccess={setAuthUser} />;

    return (
      <ConsoleLayout
        currentTab={selectedTxId ? "detail" : consoleTab}
        setTab={(tab) => {
          if (tab === "landing") {
            setView("landing");
          } else {
            setSelectedTxId(null);
            setConsoleTab(tab);
          }
        }}
        user={authUser}
        onLogout={handleLogout}
      >
        {selectedTxId ? (
          <ConsoleTransactionDetail
            transactionId={selectedTxId}
            onBack={() => setSelectedTxId(null)}
            onVerifySuccess={() => {}}
            user={authUser}
          />
        ) : consoleTab === "overview" ? (
          <ConsoleOverview
            onSelectTransaction={(id) => setSelectedTxId(id)}
            setTab={(tab) => setConsoleTab(tab)}
          />
        ) : consoleTab === "simulation" ? (
          <ConsoleSimulationLab />
        ) : consoleTab === "transactions" ? (
          <ConsoleTransactions
            onSelectTransaction={(id) => setSelectedTxId(id)}
          />
        ) : consoleTab === "review" ? (
          <ConsoleVerificationQueue
            onSelectTransaction={(id) => setSelectedTxId(id)}
            user={authUser}
          />
        ) : consoleTab === "sessions" ? (
          <ConsoleSessions
            onSelectTransaction={(id) => setSelectedTxId(id)}
          />
        ) : null}
      </ConsoleLayout>
    );
  }

  // Otherwise render the Cinematic SpendGuard Landing Page
  return (
    <main className="site-shell">
      <div className="ambient" />
      <div className="grain" />

      <motion.header className="nav" initial={reduced ? false : { opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.8 }}>
        <button className="wordmark" onClick={() => scrollTo("top")} data-testid="brand-home-link">SpendGuard</button>
        <nav className="nav-links" aria-label="Primary navigation">
          <button onClick={() => scrollTo("product")} data-testid="nav-product-link">Product</button>
          <button onClick={() => scrollTo("how")} data-testid="nav-how-link">How it works</button>
          <button onClick={() => scrollTo("trust")} data-testid="nav-trust-link">Trust</button>
          <button onClick={() => scrollTo("demo")} data-testid="nav-demo-link">Demo</button>
          <button className="nav-cta" onClick={() => openConsole("overview")} data-testid="open-console-button">Open Console →</button>
        </nav>
      </motion.header>

      <section className="hero" id="top" data-testid="hero-section">
        <motion.div className="trust-orbit" style={reduced ? undefined : { scale: orbitScale, y: orbitY }} aria-hidden="true">
          <div className="orbit-field" />
          <div className="orbit-ring outer" />
          <div className="orbit-ring middle" />
          <div className="orbit-core" />
          {[...Array(9)].map((_, i) => <i className="signal" key={i} style={{ "--i": i }} />)}
        </motion.div>
        <div className="hero-copy">
          <Reveal><Eyebrow>EVIDENCE-DRIVEN TRUST FOR AUTONOMOUS PAYMENTS</Eyebrow></Reveal>
          <h1 data-testid="hero-heading">
            <motion.span initial={reduced ? false : { y: "110%" }} animate={{ y: 0 }} transition={{ delay: 0.3, duration: 1 }}>TRUST FOR</motion.span>
            <motion.span initial={reduced ? false : { y: "110%" }} animate={{ y: 0 }} transition={{ delay: 0.43, duration: 1 }}>AUTONOMOUS</motion.span>
            <motion.span className="accent" initial={reduced ? false : { y: "110%" }} animate={{ y: 0 }} transition={{ delay: 0.56, duration: 1 }}>SPENDING.</motion.span>
          </h1>
          <motion.div className="hero-bottom" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.15, duration: 0.8 }}>
            <p data-testid="hero-description">SpendGuard evaluates authority, intent, behavior, and evidence before money moves.</p>
            <div className="hero-actions">
              <button className="button-primary" onClick={() => openConsole("overview")} data-testid="explore-spendguard-button">Open Live Console →</button>
              <button className="text-button" onClick={() => scrollTo("how")} data-testid="see-how-it-works-button">See how it works ↗</button>
            </div>
          </motion.div>
        </div>
        <button className="scroll-cue" onClick={() => scrollTo("problem")} data-testid="scroll-cue-button"><span>ENTER</span><ChevronDown size={15} /></button>
      </section>

      <section className="section problem" id="problem" data-testid="problem-section">
        <div className="section-wrap problem-wrap">
          <Reveal>
            <span className="chapter">01 / THE PROBLEM</span>
            <h2>AI CAN SPEND.<br /><span>BUT SHOULD IT?</span></h2>
          </Reveal>
          <Reveal className="problem-side" data-testid="payment-flow">
            <p>USER</p><i>↓</i><p>AI AGENT</p><i>↓</i><p>MERCHANT</p><i>↓</i><p>PAYMENT</p>
            <strong>AUTHORIZED. <em>BUT WRONG.</em></strong>
          </Reveal>
        </div>
      </section>

      <section className="section trust" id="how" data-testid="trust-checks-section">
        <div className="section-wrap">
          <Reveal className="section-intro">
            <span className="chapter">02 / HOW IT WORKS</span>
            <h2>FOUR CHECKS.<br /><span>ONE DECISION.</span></h2>
          </Reveal>
          <div className="trust-rows">
            {checks.map((check, index) => (
              <Reveal className="trust-row" key={check.name} data-testid={`trust-check-${check.name.toLowerCase()}`}>
                <span>{check.key}</span>
                <h3>
                  <button type="button" className="glossary-term" aria-describedby={`glossary-${check.name.toLowerCase()}`} data-testid={`glossary-term-${check.name.toLowerCase()}`}>
                    {check.name}
                    <span className="glossary-tip" role="tooltip" id={`glossary-${check.name.toLowerCase()}`} data-testid={`glossary-tip-${check.name.toLowerCase()}`}>{check.plain}</span>
                  </button>
                </h3>
                <p>{check.copy}<small>{check.detail}</small></p>
                <b>{index === 3 ? "CONFLICT" : "PASS"}</b>
              </Reveal>
            ))}
          </div>
          <Reveal className="decision-strip" data-testid="trust-decision-strip">
            <span>TRUST DECISION</span>
            <div><b>ALLOW</b><b className="active">VERIFY</b><b>BLOCK</b></div>
          </Reveal>
        </div>
      </section>

      <section className="marquee" aria-hidden="true">
        <div>AUTHORITY · INTENT · BEHAVIOR · EVIDENCE · TRUST DECISION ·&nbsp;</div>
        <div>AUTHORITY · INTENT · BEHAVIOR · EVIDENCE · TRUST DECISION ·&nbsp;</div>
      </section>

      <section className="section live-decision" id="trust" data-testid="live-decision-section">
        <div className="section-wrap decision-grid">
          <Reveal>
            <span className="chapter">03 / LIVE TRUST DECISION</span>
            <h2>WITHIN BUDGET.<br /><span>WRONG PURCHASE.</span></h2>
            <p className="request" data-testid="purchase-request">“Buy me a Sony WH-1000XM6,<br />black, under ₹35,000.”</p>
            <div className="decision-actions">
              <button className="text-button replay-button" onClick={replayDecision} disabled={isReplaying} data-testid="replay-decision-button">{isReplaying ? "Replaying…" : "Replay decision ↻"}</button>
              <span className="replay-status" aria-live="polite" data-testid="replay-status">{isReplaying ? `${decisionSteps[replayStep][0]} · ${decisionSteps[replayStep][2]}` : "FINAL DECISION · BLOCKED"}</span>
            </div>
          </Reveal>
          <Reveal className="decision-sequence" data-testid="decision-sequence">
            {decisionSteps.map(([name, copy, state], index) => (
              <div className={`${state === "CONFLICT" ? "conflict " : ""}${index <= replayStep ? "active" : ""}${isReplaying && index === replayStep ? " current" : ""}`} key={name} data-testid={`decision-step-${name.toLowerCase().replace(" ", "-")}`}>
                <span>0{index + 1} / {name}</span>
                <p>{copy}</p>
                <b>{state}</b>
              </div>
            ))}
            <strong className={`blocked${replayStep === decisionSteps.length - 1 ? " active" : ""}`} data-testid="decision-blocked">BLOCKED <small>EVIDENCE CONFLICT</small></strong>
          </Reveal>
        </div>
      </section>

      <section className="section evidence" data-testid="evidence-section">
        <div className="section-wrap evidence-wrap">
          <Reveal>
            <span className="chapter">04 / EVIDENCE</span>
            <h2>DON’T TRUST THE CLAIM.<br /><span>VERIFY THE EVIDENCE.</span></h2>
          </Reveal>
          <div className="evidence-comparison" data-testid="evidence-comparison">
            <Reveal className="claim"><span>AGENT CLAIM</span><strong>RTX 4060</strong></Reveal>
            <div className="conflict-line"><i /></div>
            <Reveal className="proof">
              <span>MERCHANT SPECIFICATION</span><strong>RTX 3050</strong>
              <span>CHECKOUT SKU</span><strong>RTX 3050</strong>
            </Reveal>
          </div>
          <Reveal className="evidence-result" data-testid="evidence-conflict">EVIDENCE CONFLICT <b>BLOCKED</b></Reveal>
        </div>
      </section>

      <section className="section receipt-section" id="demo" data-testid="receipt-section">
        <div className="section-wrap receipt-wrap">
          <Reveal className="receipt-intro">
            <span className="chapter">05 / TRUST RECEIPT</span>
            <h2>EVERY DECISION<br /><span>LEAVES PROOF.</span></h2>
            <p>Every approval, substitution, and block becomes an auditable financial artifact.</p>
            <div className="receipt-actions">
              <button className="text-button" onClick={() => scrollTo("timeline")} data-testid="view-decision-trail-button">View decision trail →</button>
              <button className="text-button" onClick={() => downloadTrustReceipt()} data-testid="download-receipt-button">Download receipt ↓</button>
            </div>
          </Reveal>
          <motion.div className="receipt" initial={reduced ? false : { opacity: 0, rotateY: -7, y: 40 }} whileInView={{ opacity: 1, rotateY: 0, y: 0 }} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 1.1 }} data-testid="trust-receipt">
            <div className="receipt-top"><strong>SPENDGUARD</strong><span>TRUST RECEIPT / {fallbackReceiptData.id}</span></div>
            <div className="receipt-intent"><span>USER INTENT</span><h3>{fallbackReceiptData.requested}</h3><p>{fallbackReceiptData.intentDetail}</p></div>
            <div className="receipt-decision"><div><span>SELECTED</span><strong>{fallbackReceiptData.selected}</strong><small>{fallbackReceiptData.amount}</small></div><div><span>DECISION</span><strong className="verify">{fallbackReceiptData.decision}</strong><small>Substitution</small></div></div>
            <div className="receipt-grid">{fallbackReceiptData.checks.map(([a,b]) => <div key={a}><span>{a}</span><strong>{b}</strong></div>)}</div>
            <div className="receipt-why"><span>WHY?</span><p>{fallbackReceiptData.reason}</p></div>
          </motion.div>
        </div>
      </section>

      <section className="section timeline-section" id="timeline" data-testid="provenance-section">
        <div className="section-wrap timeline-wrap">
          <Reveal>
            <span className="chapter">06 / OBSERVABILITY</span>
            <h2>SEE HOW THE<br /><span>DECISION HAPPENED.</span></h2>
          </Reveal>
          <div className="timeline" data-testid="event-timeline">
            {events.map((event, i) => <Reveal className="event" key={event}><span>{String(i + 1).padStart(2, "0")}</span><p>{event}</p></Reveal>)}
          </div>
        </div>
      </section>

      <ScenarioLibrary />

      <section className="metrics" data-testid="metrics-section">
        <div className="metrics-wrap">
          <Reveal className="metric"><CountUp value={liveMetrics.signals} /><span>TRUST SIGNALS</span></Reveal>
          <Reveal className="metric"><CountUp value={liveMetrics.evaluations} /><span>PRODUCTS OBSERVED</span></Reveal>
          <Reveal className="metric"><CountUp value={liveMetrics.blocked} /><span>RISK SIGNALS REJECTED</span></Reveal>
          <Reveal className="metric"><CountUp value={liveMetrics.trails} /><span>DECISION TRAILS</span></Reveal>
        </div>
      </section>

      <section className="section product" id="product" data-testid="product-section">
        <div className="section-wrap product-wrap">
          <Reveal className="product-intro">
            <span className="chapter">08 / PRODUCT</span>
            <h2>CONTROL, WITHOUT<br /><span>THE COMPLEXITY.</span></h2>
          </Reveal>
          <Reveal className="console" data-testid="console-preview">
            <div className="console-head"><span>SPENDGUARD CONSOLE</span><b>TRUST DECISION / 000184</b></div>
            <div className="console-decision"><span>SUBSTITUTION REVIEW</span><strong>VERIFY</strong></div>
            <div className="console-lines">{["INTENT — XM6 requested", "AUTHORITY — limit passed", "EVIDENCE — merchant verified", "BEHAVIOR — low risk"].map((line) => <p key={line}>{line}</p>)}</div>
          </Reveal>
          <button className="button-primary open-product" onClick={() => openConsole("overview")} data-testid="open-spendguard-button">Open SpendGuard Console →</button>
        </div>
      </section>

      <section className="section founder" data-testid="founder-note-section">
        <div className="section-wrap founder-wrap">
          <Reveal>
            <span className="chapter">09 / FOUNDER NOTE</span>
            <blockquote data-testid="founder-note-quote">“Autonomy should never require blind faith.”</blockquote>
            <p data-testid="founder-note-copy">AI agents will compare, choose, and pay at machine speed. SpendGuard exists to make every action observable before money moves — authority first, intent always, evidence before trust, behavior over time.</p>
            <footer>— SPENDGUARD</footer>
          </Reveal>
        </div>
      </section>

      <section className="section final" data-testid="final-section">
        <div className="final-orb" />
        <div className="section-wrap final-wrap">
          <Eyebrow>THE NEXT MOVE</Eyebrow>
          <h2>GIVE AI<br /><span>AUTONOMY.</span><br />KEEP CONTROL.</h2>
          <p>SpendGuard makes autonomous payments safe, explainable, and accountable.</p>
          <button className="button-primary" onClick={() => openConsole("overview")} data-testid="enter-spendguard-button">Enter SpendGuard <ArrowUpRight size={16} /></button>
          <footer><span>SPENDGUARD</span><span>TRUST BEFORE THE TAP.</span><span>© 2026</span></footer>
        </div>
      </section>
    </main>
  );
}

export default App;
