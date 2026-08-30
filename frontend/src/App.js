import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import { jsPDF } from "jspdf";
import "@/App.css";

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

const metrics = [
  { value: 4, label: "TRUST SIGNALS" },
  { value: 17, label: "PRODUCTS OBSERVED" },
  { value: 12, label: "RISK SIGNALS REJECTED" },
  { value: 1, label: "DECISION TRAIL" },
];

const decisionSteps = [
  ["PURCHASE REQUEST", "Sony WH-1000XM6 · black · under ₹35,000", "RECEIVED"],
  ["AUTHORITY", "Within approved limit", "PASS"],
  ["INTENT", "Product family matched", "PASS"],
  ["BEHAVIOR", "Session pattern normal", "PASS"],
  ["EVIDENCE", "Merchant model mismatch", "CONFLICT"],
];

const receiptData = {
  id: "000184",
  requested: "Sony WH-1000XM6",
  intentDetail: "Black · ≤ ₹35,000",
  selected: "Sony WH-1000XM5",
  amount: "₹28,000",
  decision: "VERIFY",
  reason: "The requested XM6 was unavailable. The agent selected XM5 as a substitution.",
  checks: [["AUTHORITY", "PASS"], ["INTENT", "SUBSTITUTION"], ["EVIDENCE", "VERIFIED"], ["BEHAVIOR", "LOW RISK"]],
};

const scenarios = [
  {
    id: "allow",
    label: "ALLOW",
    kicker: "Exact match",
    title: "Sony WH-1000XM6",
    detail: "Black · ₹32,499",
    summary: "Every signal agrees. The purchase proceeds without interruption.",
    steps: [
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
    detail: "Black · ₹28,000",
    summary: "The requested XM6 is unavailable, so the substitution requires review.",
    steps: [
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
    title: "Sony WH-1000XM6",
    detail: "Black · under ₹35,000",
    summary: "The merchant model cannot be verified, so money does not move.",
    steps: [
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
  const [step, setStep] = useState(scenarios[0].steps.length - 1);
  const [isPlaying, setIsPlaying] = useState(false);
  const scenario = scenarios.find((item) => item.id === scenarioId) || scenarios[0];

  useEffect(() => {
    if (!isPlaying) return undefined;
    if (step === scenario.steps.length - 1) {
      setIsPlaying(false);
      return undefined;
    }
    const timer = setTimeout(() => setStep((current) => current + 1), 950);
    return () => clearTimeout(timer);
  }, [isPlaying, scenario.steps.length, step]);

  const playScenario = (id = scenarioId) => {
    const next = scenarios.find((item) => item.id === id) || scenarios[0];
    setScenarioId(next.id);
    if (reduced) {
      setStep(next.steps.length - 1);
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
          <p>Compare how the same four checks produce allow, verify, and block decisions.</p>
          <div className="scenario-list" role="tablist" aria-label="SpendGuard decision scenarios">
            {scenarios.map((item, index) => (
              <button className={`scenario-tab ${item.id === scenarioId ? "active" : ""}`} key={item.id} onClick={() => playScenario(item.id)} role="tab" aria-selected={item.id === scenarioId} data-testid={`scenario-tab-${item.id}`}>
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
            {scenario.steps.map(([name, copy, state], index) => (
              <div className={`scenario-step ${index <= step ? "active" : ""}${isPlaying && index === step ? " current" : ""}`} key={name} data-testid={`scenario-step-${name.toLowerCase()}`}>
                <span>{name}</span>
                <p>{copy}</p>
                <b>{state}</b>
              </div>
            ))}
          </div>
          <div className="scenario-footer">
            <div>
              <span aria-live="polite" data-testid="scenario-status">{isPlaying ? scenario.steps[step][0] : "FINAL DECISION"}</span>
              <strong className={`scenario-result ${scenario.id}`} data-testid="scenario-result">{scenario.label}</strong>
            </div>
            <button className="text-button" onClick={() => playScenario()} disabled={isPlaying} data-testid="scenario-replay-button">{isPlaying ? "Replaying…" : "Replay story ↻"}</button>
          </div>
          <p className="scenario-summary" data-testid="scenario-summary">{scenario.summary}</p>
        </Reveal>
      </div>
    </section>
  );
}

function downloadTrustReceipt() {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const width = doc.internal.pageSize.getWidth();
  const height = doc.internal.pageSize.getHeight();
  const margin = 56;
  const ink = [24, 26, 34];
  const muted = [102, 105, 116];
  const accent = [95, 80, 173];
  const rule = [190, 185, 177];

  doc.setProperties({ title: `SpendGuard Trust Receipt ${receiptData.id}` });
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
  doc.text(`TRUST RECEIPT / ${receiptData.id}`, width - margin, 66, { align: "right" });
  doc.line(margin, 82, width - margin, 82);

  doc.setFont("times", "normal");
  doc.setFontSize(34);
  doc.text("Trust Receipt", margin, 128);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("AUTONOMOUS PURCHASE DECISION · SAMPLE · JULY 2026", margin, 148);

  doc.setTextColor(...muted);
  doc.text("USER INTENT", margin, 192);
  doc.setTextColor(...ink);
  doc.setFont("times", "normal");
  doc.setFontSize(23);
  doc.text(receiptData.requested, margin, 220);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(...muted);
  doc.text("Black · up to INR 35,000", margin, 239);

  doc.line(margin, 262, width - margin, 262);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.text("SELECTED", margin, 292);
  doc.text("TRANSACTION", width / 2 + 16, 292);
  doc.setTextColor(...ink);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text(receiptData.selected, margin, 314);
  doc.text("INR 28,000", width / 2 + 16, 314);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...muted);
  doc.text("Substitution for requested XM6", margin, 331);
  doc.text(`Decision ID ${receiptData.id}`, width / 2 + 16, 331);

  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("TRUST EVALUATION", margin, 348);
  doc.text("AUTHORITY · INTENT · EVIDENCE · BEHAVIOR", width - margin, 348, { align: "right" });

  let y = 374;
  receiptData.checks.forEach(([label, value], index) => {
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
    y += index === receiptData.checks.length - 1 ? 0 : 31;
  });

  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("FINAL DECISION", margin, 534);
  doc.setTextColor(...accent);
  doc.setFont("times", "normal");
  doc.setFontSize(42);
  doc.text(receiptData.decision, margin, 577);
  doc.setFont("courier", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text("WHY", width / 2 + 16, 534);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(...ink);
  doc.text(doc.splitTextToSize(receiptData.reason, 205), width / 2 + 16, 552);

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
  doc.save(`spendguard-trust-receipt-${receiptData.id}.pdf`);
}

function App() {
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
          <button className="nav-cta" onClick={() => scrollTo("product")} data-testid="open-console-button">Open Console →</button>
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
              <button className="button-primary" onClick={() => scrollTo("problem")} data-testid="explore-spendguard-button">Explore SpendGuard →</button>
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
              <button className="text-button" onClick={downloadTrustReceipt} data-testid="download-receipt-button">Download receipt ↓</button>
            </div>
          </Reveal>
          <motion.div className="receipt" initial={reduced ? false : { opacity: 0, rotateY: -7, y: 40 }} whileInView={{ opacity: 1, rotateY: 0, y: 0 }} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 1.1 }} data-testid="trust-receipt">
            <div className="receipt-top"><strong>SPENDGUARD</strong><span>TRUST RECEIPT / {receiptData.id}</span></div>
            <div className="receipt-intent"><span>USER INTENT</span><h3>{receiptData.requested}</h3><p>{receiptData.intentDetail}</p></div>
            <div className="receipt-decision"><div><span>SELECTED</span><strong>{receiptData.selected}</strong><small>{receiptData.amount}</small></div><div><span>DECISION</span><strong className="verify">{receiptData.decision}</strong><small>Substitution</small></div></div>
            <div className="receipt-grid">{receiptData.checks.map(([a,b]) => <div key={a}><span>{a}</span><strong>{b}</strong></div>)}</div>
            <div className="receipt-why"><span>WHY?</span><p>{receiptData.reason}</p></div>
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
          {metrics.map((metric) => <Reveal className="metric" key={metric.label}><CountUp value={metric.value} /><span>{metric.label}</span></Reveal>)}
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
          <button className="button-primary open-product" onClick={() => scrollTo("top")} data-testid="open-spendguard-button">Open SpendGuard →</button>
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
          <button className="button-primary" onClick={() => scrollTo("top")} data-testid="enter-spendguard-button">Enter SpendGuard <ArrowUpRight size={16} /></button>
          <footer><span>SPENDGUARD</span><span>TRUST BEFORE THE TAP.</span><span>© 2026</span></footer>
        </div>
      </section>
    </main>
  );
}

export default App;
