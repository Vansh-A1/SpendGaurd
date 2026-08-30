import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import "@/App.css";

const checks = [
  { key: "01", name: "AUTHORITY", copy: "Can the agent make this purchase?", detail: "Verified spending limit and mandate." },
  { key: "02", name: "INTENT", copy: "Is this what the user asked for?", detail: "Sony WH-1000XM6, black, under ₹35,000." },
  { key: "03", name: "BEHAVIOR", copy: "Does the agent still behave normally?", detail: "Session pattern remains within baseline." },
  { key: "04", name: "EVIDENCE", copy: "Can the product claims be proven?", detail: "Model specification conflicts at checkout." },
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

function App() {
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const orbitScale = useTransform(scrollYProgress, [0, 0.22], [1, 1.18]);
  const orbitY = useTransform(scrollYProgress, [0, 0.22], [0, -42]);
  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });

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
                <h3>{check.name}</h3>
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
          </Reveal>
          <Reveal className="decision-sequence" data-testid="decision-sequence">
            {[
              ["AUTHORITY", "Within approved limit", "PASS"],
              ["INTENT", "Product family matched", "PASS"],
              ["BEHAVIOR", "Session pattern normal", "PASS"],
              ["EVIDENCE", "Merchant model mismatch", "CONFLICT"],
            ].map(([name, copy, state], index) => (
              <div className={state === "CONFLICT" ? "conflict" : ""} key={name}>
                <span>0{index + 1} / {name}</span>
                <p>{copy}</p>
                <b>{state}</b>
              </div>
            ))}
            <strong className="blocked" data-testid="decision-blocked">BLOCKED <small>EVIDENCE CONFLICT</small></strong>
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
            <button className="text-button" onClick={() => scrollTo("timeline")} data-testid="view-decision-trail-button">View decision trail →</button>
          </Reveal>
          <motion.div className="receipt" initial={reduced ? false : { opacity: 0, rotateY: -7, y: 40 }} whileInView={{ opacity: 1, rotateY: 0, y: 0 }} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 1.1 }} data-testid="trust-receipt">
            <div className="receipt-top"><strong>SPENDGUARD</strong><span>TRUST RECEIPT / 000184</span></div>
            <div className="receipt-intent"><span>USER INTENT</span><h3>Sony WH-1000XM6</h3><p>Black · ≤ ₹35,000</p></div>
            <div className="receipt-decision"><div><span>SELECTED</span><strong>Sony WH-1000XM5</strong><small>₹28,000</small></div><div><span>DECISION</span><strong className="verify">VERIFY</strong><small>Substitution</small></div></div>
            <div className="receipt-grid">{[["AUTHORITY","PASS"],["INTENT","SUBSTITUTION"],["EVIDENCE","VERIFIED"],["BEHAVIOR","LOW RISK"]].map(([a,b]) => <div key={a}><span>{a}</span><strong>{b}</strong></div>)}</div>
            <div className="receipt-why"><span>WHY?</span><p>The requested XM6 was unavailable. The agent selected XM5 as a substitution.</p></div>
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

      <section className="metrics" data-testid="metrics-section">
        <div className="metrics-wrap">
          {metrics.map((metric) => <Reveal className="metric" key={metric.label}><CountUp value={metric.value} /><span>{metric.label}</span></Reveal>)}
        </div>
      </section>

      <section className="section product" id="product" data-testid="product-section">
        <div className="section-wrap product-wrap">
          <Reveal className="product-intro">
            <span className="chapter">07 / PRODUCT</span>
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
