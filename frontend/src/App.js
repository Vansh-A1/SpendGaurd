import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Check, ChevronDown, ShieldCheck } from "lucide-react";
import "@/App.css";

const checks = [
  { key: "01", name: "AUTHORITY", copy: "Can the agent make this purchase?", tone: "blue" },
  { key: "02", name: "INTENT", copy: "Is this what you actually asked for?", tone: "white" },
  { key: "03", name: "EVIDENCE", copy: "Can the important claims be verified?", tone: "blue" },
  { key: "04", name: "BEHAVIOR", copy: "Does the agent remain trustworthy?", tone: "white" },
];

const events = ["Intent created", "Search initiated", "17 products found", "9 rejected — over budget", "3 rejected — requirement mismatch", "XM6 unavailable", "XM5 selected", "Human approval requested"];

function Eyebrow({ children }) { return <span className="eyebrow" data-testid="section-eyebrow">{children}</span>; }
function Reveal({ children, className = "" }) { return <motion.div className={className} initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>{children}</motion.div>; }

function App() {
  const { scrollYProgress } = useScroll();
  const gateScale = useTransform(scrollYProgress, [0, 0.25], [1, 1.16]);
  const gateY = useTransform(scrollYProgress, [0, 0.25], [0, -30]);
  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return <main className="site-shell">
    <div className="grain" />
    <motion.header className="nav" initial={{ opacity: 0, y: -14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .2, duration: .8 }}>
      <button className="wordmark" onClick={() => scrollTo("top")} data-testid="brand-home-link">SPENDGUARD<span>®</span></button>
      <nav className="nav-links" aria-label="Primary navigation">
        <button onClick={() => scrollTo("product")} data-testid="nav-product-link">Product</button>
        <button onClick={() => scrollTo("checks")} data-testid="nav-trust-link">Trust</button>
        <button onClick={() => scrollTo("receipt")} data-testid="nav-demo-link">Demo</button>
        <button className="nav-cta" onClick={() => scrollTo("product")} data-testid="open-console-button">Open Console <ArrowUpRight size={14} /></button>
      </nav>
    </motion.header>

    <section className="hero" id="top" data-testid="hero-section">
      <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
      <motion.div className="gate-scene" style={{ scale: gateScale, y: gateY }} aria-hidden="true">
        <div className="gate-halo" /><div className="gate-ring ring-back" /><div className="gate-ring ring-front" />
        <div className="gate-core"><div className="core-line line-a" /><div className="core-line line-b" /><div className="core-pulse" /></div>
        {[...Array(12)].map((_, i) => <i className="particle" key={i} style={{ "--i": i }} />)}
      </motion.div>
      <div className="hero-copy">
        <Reveal><Eyebrow>THE TRUST LAYER FOR AUTONOMOUS PAYMENTS</Eyebrow></Reveal>
        <motion.h1 initial={{ opacity: 0, y: 35 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .45, duration: 1.1 }}>TRUST<br /><em>BEFORE</em><br />THE TAP<span className="period">.</span></motion.h1>
        <motion.div className="hero-bottom" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.1 }}>
          <p data-testid="hero-description">Evidence-backed trust for<br />autonomous payments.</p>
          <div className="hero-actions"><button className="button-primary" onClick={() => scrollTo("problem")} data-testid="explore-spendguard-button">Explore SpendGuard <ArrowDownRight size={17} /></button><button className="text-button" onClick={() => scrollTo("checks")} data-testid="see-how-it-works-button">See how it works <span>↗</span></button></div>
        </motion.div>
      </div>
      <div className="scroll-cue"><span>SCROLL TO ENTER</span><ChevronDown size={16} /></div>
    </section>

    <section className="problem section" id="problem" data-testid="problem-section"><div className="section-wrap problem-wrap"><Reveal><Eyebrow>THE NEW PAYMENT FRONTIER / 01</Eyebrow><h2>AI CAN NOW<br /><span>SPEND FOR YOU.</span></h2></Reveal><Reveal className="problem-aside"><p>But autonomy<br /><strong>needs trust.</strong></p><div className="signal-line" /></Reveal><div className="flow" data-testid="payment-flow"><div>USER</div><b>↓</b><div>AI AGENT</div><b>↓</b><div>MERCHANT</div><b>↓</b><div className="flow-final">PAYMENT</div><div className="interrupt">AUTHORIZED.<br /><strong>BUT WRONG.</strong></div></div></div></section>

    <section className="mismatch section" data-testid="intent-mismatch-section"><div className="section-wrap"><Reveal><Eyebrow>A TRUST FAILURE / 02</Eyebrow><h2 className="statement">WITHIN BUDGET.<br /><i>WRONG PURCHASE.</i></h2></Reveal><div className="mismatch-grid"><Reveal className="request"><label>USER REQUEST</label><p>“Buy me a <strong>Sony WH-1000XM6</strong>,<br />black, under <strong>₹35,000.</strong>”</p></Reveal><Reveal className="selection"><label>AGENT SELECTED</label><p>Generic Bluetooth<br />Headphones</p><strong className="price">₹8,999</strong><div className="checks"><span><Check size={13} /> BUDGET</span><span><Check size={13} /> CATEGORY</span><span className="fail">✕ INTENT</span></div><div className="blocked">BLOCKED <span>01</span></div></Reveal></div></div></section>

    <section className="checks-section section" id="checks" data-testid="trust-checks-section"><div className="section-wrap"><Reveal><Eyebrow>THE SPENDGUARD METHOD / 03</Eyebrow><h2>FOUR QUESTIONS.<br /><span>ONE TRUST DECISION.</span></h2></Reveal><div className="check-sequence">{checks.map((check, index) => <Reveal className={`check-row ${check.tone}`} key={check.name}><span className="check-number">{check.key}</span><div className="check-name">{check.name}</div><p>{check.copy}</p><div className="check-beam"><i style={{ animationDelay: `${index * .4}s` }} /></div><span className="check-status">{index < 2 ? "PASS" : "READY"}</span></Reveal>)}</div><div className="decision"><span>TRUST DECISION</span><strong>VERIFY</strong><div><b>ALLOW</b><b className="active">VERIFY</b><b>BLOCK</b></div></div></div></section>

    <section className="behavior section" data-testid="behavior-section"><div className="section-wrap behavior-wrap"><Reveal><Eyebrow>WHEN PATTERNS CHANGE / 04</Eyebrow><h2>EVERY TRANSACTION<br /><i>WAS ALLOWED.</i></h2><p className="section-lede">The behavior wasn't.</p></Reveal><div className="behavior-visual"><div className="payment-stack">{[1,2,3,4,5,6].map((n) => <div className="payment-chip" key={n}><span>₹9,000</span><small>AUTHORIZED ✓</small></div>)}</div><div className="risk-panel"><div className="risk-label">CUMULATIVE SESSION SPEND <strong>₹54,000</strong></div><svg viewBox="0 0 500 150" preserveAspectRatio="none" aria-label="Rising spend graph"><path d="M0 130 C80 130 100 116 150 114 S210 110 250 86 S320 75 350 50 S420 42 500 10" /></svg><div className="risk-states"><span>LOW</span><span>MEDIUM</span><span className="high">HIGH</span></div><div className="risk-block">BEHAVIORAL RISK <b>BLOCKED</b></div></div></div></div></section>

    <section className="evidence section" data-testid="evidence-section"><div className="section-wrap evidence-wrap"><Reveal><Eyebrow>CLAIM / PROOF / 05</Eyebrow><h2>DON'T TRUST THE CLAIM.<br /><i>VERIFY THE EVIDENCE.</i></h2></Reveal><div className="evidence-stage"><div className="evidence-node claim"><label>AGENT CLAIM</label><strong>RTX 4060</strong></div><div className="evidence-connector"><span>CONFLICT</span></div><div className="evidence-node"><label>MERCHANT SPECIFICATION</label><strong>RTX 3050</strong><label>CHECKOUT SKU</label><strong>RTX 3050</strong></div></div><div className="evidence-result"><span>EVIDENCE CONFLICT</span><strong>BLOCKED</strong></div></div></section>

    <section className="receipt-section section" id="receipt" data-testid="receipt-section"><div className="section-wrap receipt-wrap"><Reveal><Eyebrow>THE OUTPUT / 06</Eyebrow><h2>EVERY DECISION<br />LEAVES A <i>TRAIL.</i></h2></Reveal><div className="receipt-layout"><motion.div className="receipt" whileInView={{ rotateY: [8, 0], rotateX: [4, 0] }} viewport={{ once: true }} transition={{ duration: 1.3 }} data-testid="trust-receipt"><div className="receipt-top"><span>SPENDGUARD</span><ShieldCheck size={21} /><small>TRUST RECEIPT / 000184</small></div><div className="receipt-rule" /><label>USER INTENT</label><h3>Sony WH-1000XM6</h3><p>Black &nbsp; · &nbsp; ≤ ₹35,000</p><div className="receipt-row"><div><label>SELECTED</label><strong>Sony WH-1000XM5</strong><p>₹28,000</p></div><div><label>DECISION</label><strong className="verify">VERIFY</strong><p>Substitution</p></div></div><div className="receipt-grid">{[["AUTHORITY","PASS"],["INTENT","SUBSTITUTION"],["EVIDENCE","VERIFIED"],["BEHAVIOR","LOW RISK"]].map(([a,b]) => <div key={a}><label>{a}</label><strong>{b}</strong></div>)}</div><div className="receipt-why"><label>WHY?</label><p>The requested XM6 was unavailable. The agent selected XM5 as a substitution.</p></div><div className="receipt-foot"><span>SG / 24—06—26</span><span>◉ ◉ ◉</span></div></motion.div><Reveal className="receipt-copy"><p>A financial system should explain itself.</p><button className="button-primary" onClick={() => scrollTo("provenance")} data-testid="view-decision-trail-button">View decision trail <ArrowUpRight size={16} /></button></Reveal></div></div></section>

    <section className="provenance section" id="provenance" data-testid="provenance-section"><div className="section-wrap provenance-wrap"><Reveal><Eyebrow>OBSERVABLE EVENTS / 07</Eyebrow><h2>SEE HOW THE<br /><span>DECISION HAPPENED.</span></h2></Reveal><div className="timeline">{events.map((event, i) => <Reveal className={`event ${i === events.length - 1 ? "last" : ""}`} key={event}><span>{String(i + 1).padStart(2,"0")}</span><p>{event}</p>{i === events.length - 1 && <b>APPROVAL REQUIRED</b>}</Reveal>)}</div></div></section>

    <section className="product section" id="product" data-testid="product-section"><div className="section-wrap product-wrap"><Reveal><Eyebrow>THE FUTURE CONSOLE / 08</Eyebrow><h2>CONTROL, WITHOUT<br /><i>THE COMPLEXITY.</i></h2></Reveal><div className="console" data-testid="console-preview"><div className="console-top"><span>SPENDGUARD / CONSOLE</span><span>LIVE TRUST LAYER <i /></span></div><div className="console-body"><div className="console-title"><span>DECISION / 000184</span><h3>Substitution<br /><em>requires review.</em></h3><button data-testid="console-decision-button">VERIFY <ArrowUpRight size={14} /></button></div><div className="console-list">{[["01","INTENT","Sony WH-1000XM6","MATCHED"],["02","AUTHORITY","Purchase limit ₹35,000","PASSED"],["03","EVIDENCE","Merchant SKU verified","PASSED"],["04","BEHAVIOR","Session within normal range","LOW RISK"]].map(row => <div key={row[0]}><small>{row[0]}</small><label>{row[1]}</label><span>{row[2]}</span><b>{row[3]}</b></div>)}</div></div></div><button className="open-product" onClick={() => scrollTo("top")} data-testid="open-spendguard-button">Open SpendGuard <ArrowUpRight size={18} /></button></div></section>

    <section className="final section" data-testid="final-section"><div className="final-glow" /><div className="section-wrap final-wrap"><Eyebrow>THE NEXT MOVE</Eyebrow><h2>GIVE AI<br /><i>AUTONOMY.</i><br />KEEP CONTROL<span>.</span></h2><p>SpendGuard makes autonomous payments<br />safe, explainable, and accountable.</p><button className="button-primary" onClick={() => scrollTo("top")} data-testid="enter-spendguard-button">Enter SpendGuard <ArrowUpRight size={17} /></button><footer><span>SPENDGUARD®</span><span>TRUST BEFORE THE TAP.</span><span>© 2026</span></footer></div></section>
  </main>;
}

export default App;