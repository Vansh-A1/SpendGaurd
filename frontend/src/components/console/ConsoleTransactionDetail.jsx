import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { ArrowLeft, Clock, Check, X, Shield, Download, AlertTriangle, RefreshCw } from "lucide-react";
import { jsPDF } from "jspdf";

export function ConsoleTransactionDetail({ transactionId, onBack, onVerifySuccess, user }) {
  const [loading, setLoading] = useState(true);
  const [receipt, setReceipt] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyOutcome, setVerifyOutcome] = useState(null);
  const canVerify = ["admin", "operator"].includes(user?.role);

  const loadDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const [r, s] = await Promise.all([
        api.getTransactionReceipt(transactionId),
        api.getTransactionSnapshot(transactionId).catch(() => null),
      ]);
      setReceipt(r);
      setSnapshot(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (transactionId) loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transactionId]);

  const handleVerify = async (approved) => {
    try {
      setVerifying(true);
      const updated = await api.verifyTransaction(transactionId, approved);
      setReceipt(updated);
      setVerifyOutcome(approved ? "APPROVED" : "REJECTED");
      if (onVerifySuccess) onVerifySuccess();
    } catch (err) {
      alert(`Verification action failed: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  const downloadPdf = () => {
    if (!receipt) return;
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const width = doc.internal.pageSize.getWidth();
    const height = doc.internal.pageSize.getHeight();
    const margin = 56;
    const ink = [24, 26, 34];
    const muted = [102, 105, 116];
    const accent = [95, 80, 173];
    const rule = [190, 185, 177];
    const decisionId = receipt.transaction_id || transactionId;

    doc.setProperties({ title: `SpendGuard Trust Receipt ${decisionId}` });
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
    doc.text(`TRUST RECEIPT / ${decisionId}`, width - margin, 66, { align: "right" });
    doc.line(margin, 82, width - margin, 82);

    doc.setFont("times", "normal");
    doc.setFontSize(34);
    doc.text("Trust Receipt", margin, 128);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text("AUTONOMOUS PURCHASE DECISION · LIVE RECORD", margin, 148);

    doc.text("USER INTENT", margin, 192);
    doc.setTextColor(...ink);
    doc.setFont("times", "normal");
    doc.setFontSize(23);
    doc.text(doc.splitTextToSize(promptDescription, 430), margin, 220);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(...muted);
    doc.text(`Agent ${receipt.agent_id || "unknown"} · ${categoryName}`, margin, 248);

    doc.line(margin, 274, width - margin, 274);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.text("SELECTED", margin, 304);
    doc.text("TRANSACTION", width / 2 + 16, 304);
    doc.setTextColor(...ink);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text(doc.splitTextToSize(productName, 210), margin, 326);
    doc.text(`INR ${parseFloat(receipt.amount || 0).toLocaleString()}`, width / 2 + 16, 326);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(...muted);
    doc.text(merchantName, margin, 344);
    doc.text(`Receipt ID ${decisionId}`, width / 2 + 16, 344);

    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.text("TRUST EVALUATION", margin, 382);
    doc.text("AUTHORITY · INTENT · EVIDENCE · BEHAVIOR", width - margin, 382, { align: "right" });

    const checkRows = [
      ["AUTHORITY", authority.passed !== false ? "PASS" : "FAIL"],
      ["INTENT", intent.substitution ? "SUBSTITUTION" : intent.passed !== false ? "PASS" : "FAIL"],
      ["EVIDENCE", evidence.conflict ? "CONFLICT" : "VERIFIED"],
      ["BEHAVIOR", behavior.risk_score > 0.7 ? "HIGH RISK" : behavior.risk_score > 0.35 ? "MEDIUM RISK" : "LOW RISK"],
    ];
    let y = 412;
    checkRows.forEach(([label, value], index) => {
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
      y += index === checkRows.length - 1 ? 0 : 31;
    });

    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text("FINAL DECISION", margin, 532);
    doc.setTextColor(...accent);
    doc.setFont("times", "normal");
    doc.setFontSize(40);
    doc.text(receipt.decision || "UNKNOWN", margin, 572);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text("WHY", width / 2 + 16, 532);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(...ink);
    doc.text(doc.splitTextToSize(receipt.decision_reason || "Evaluated by SpendGuard.", 205), width / 2 + 16, 550);

    doc.setDrawColor(...rule);
    doc.line(margin, 624, width - margin, 624);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text("OBSERVABLE DECISION TRAIL", margin, 648);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    provenance.slice(0, 6).forEach((event, index) => {
      const rowY = 674 + index * 22;
      doc.setTextColor(...accent);
      doc.text(String(event.seq || index + 1).padStart(2, "0"), margin, rowY);
      doc.setTextColor(...ink);
      doc.text(`${event.event_type || "audit event"} — ${formatEventPayload(event)}`, margin + 30, rowY);
    });

    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...muted);
    doc.text("SPENDGUARD · TRUST BEFORE THE TAP.", margin, height - 54);
    doc.text("EVIDENCE-BACKED AUTONOMY", width - margin, height - 54, { align: "right" });
    doc.save(`spendguard-receipt-${decisionId}.pdf`);
  };

  if (loading) {
    return <div className="console-loading"><RefreshCw size={14} /><span>Loading investigation audit records...</span></div>;
  }

  if (error || !receipt) {
    return (
      <div className="console-empty" data-testid="transaction-detail-error">
        <AlertTriangle size={18} />
        <h3>Failed to load transaction</h3>
        <p>{error || "Transaction not found"}</p>
        <button className="console-button" onClick={onBack}>Back to List</button>
      </div>
    );
  }

  const pillars = receipt.pillars || {};
  const authority = pillars.authority || receipt.authorization || snapshot?.authorization_result || {};
  const intent = pillars.intent || receipt.intent_fidelity || snapshot?.intent_fidelity || {};
  const evidence = pillars.evidence || receipt.evidence || snapshot?.evidence_result || {};
  const behavior = pillars.behavior || receipt.behavioral_risk || snapshot?.behavioral_risk || {};
  const provenance = receipt.provenance || receipt.provenance_trail || snapshot?.provenance_reference || [];

  const claimed = receipt.claimed_product || {};
  const productName = claimed.model || claimed.name || claimed.brand || receipt.actual_sku || "Item";
  const brandName = claimed.brand || "";
  const categoryName = receipt.category || claimed.category || "Electronics";
  const merchantName = receipt.merchant || "Authorized Merchant";
  const promptDescription = claimed.description || (brandName ? `Purchase ${brandName} ${productName}` : `Procure ${productName}`);

  const formatEventPayload = (evt) => {
    const payload = evt.payload || evt.detail;
    if (typeof payload === "string") return payload;
    if (!payload || typeof payload !== "object") return "";
    if (payload.reason) return payload.reason;
    if (payload.query) return [payload.query.brand, payload.query.model, payload.query.category].filter(Boolean).join(" · ");
    if (payload.eliminated_count !== undefined) return `${payload.eliminated_count} candidates eliminated by mandate and product requirements.`;
    if (payload.sku) return `Selected ${[payload.brand, payload.model].filter(Boolean).join(" ") || payload.sku}${payload.price ? ` at ₹${parseFloat(payload.price).toLocaleString()}` : ""}.`;
    return Object.entries(payload).slice(0, 3).map(([key, value]) => `${key.replace(/_/g, " ")}: ${typeof value === "object" ? "recorded" : value}`).join(" · ");
  };

  return (
    <div className="console-page" data-testid="transaction-detail-page">
      <header className="console-page-header">
        <div>
          <button className="console-back" onClick={onBack} data-testid="transaction-back-button">
            <ArrowLeft size={14} />
            <span>Back to Transactions</span>
          </button>
          <span className="console-kicker">Investigation Record</span>
          <h1 className="console-title">Transaction <span className="tx-id">{receipt.transaction_id || transactionId}</span></h1>
          <p className="console-subtitle">Evaluated on {receipt.timestamp ? new Date(receipt.timestamp).toLocaleString() : "Live"} · Agent: {receipt.agent_id}</p>
        </div>
        <div className="console-topbar-actions">
          <StatusBadge status={receipt.decision} />
          {receipt.decision === "VERIFY" && !verifyOutcome && canVerify && (
            <>
              <button className="console-button-danger" onClick={() => handleVerify(false)} disabled={verifying} data-testid="detail-reject-button">
                <X size={13} />
                <span>Reject &amp; Void</span>
              </button>
              <button className="console-button-primary" onClick={() => handleVerify(true)} disabled={verifying} data-testid="detail-approve-button">
                <Check size={13} />
                <span>Approve &amp; Capture</span>
              </button>
            </>
          )}
          {receipt.decision === "VERIFY" && !canVerify && <span className="status-badge">Read-only viewer</span>}
          {verifyOutcome && <span className={`status-badge status-${verifyOutcome.toLowerCase()}`} data-testid="operator-decision-status">OPERATOR DECISION RECORDED: {verifyOutcome}</span>}
        </div>
      </header>

      <section className="console-page" data-testid="intent-investigation">
        <div className="console-kicker">Intent Fidelity Investigation</div>

        <div className="detail-grid">
          <div className="detail-cell">
            <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">
              USER MANDATE REQUIREMENT
            </div>
            <p className="font-serif text-xl sm:text-2xl text-[#f0eef5] leading-relaxed">
              “{promptDescription}”
            </p>
            <div className="text-xs text-[#8d94a1] space-y-1 font-mono pt-2 border-t border-[#dddee8]/10">
              <div>Agent ID: <span className="text-[#f0eef5]">{receipt.agent_id}</span></div>
              <div>Category: <span className="text-[#f0eef5]">{categoryName}</span></div>
              <div>Merchant: <span className="text-[#f0eef5]">{merchantName}</span></div>
              <div>SKU: <span className="text-[#a99df2]">{receipt.actual_sku || "ELEC-SKU-001"}</span></div>
            </div>
          </div>

          <div className="detail-cell">
            <div>
              <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase mb-2">
                SELECTED ITEM &amp; AMOUNT
              </div>
              <h3 className="font-serif text-xl sm:text-2xl text-[#f0eef5]">
                {productName}
              </h3>
              <div className="text-2xl sm:text-3xl font-mono font-semibold text-[#a99df2] mt-1">
                ₹{(parseFloat(receipt.amount) || 0).toLocaleString()}
              </div>
            </div>

            <div className="pt-4 border-t border-[#dddee8]/10 space-y-2">
              <div className="text-xs font-sans text-[#dddee8] leading-relaxed">
                <strong>Decision Rationale:</strong> {receipt.decision_reason}
              </div>
              {receipt.payment_hold_id && (
                <div className="flex items-center gap-2 text-xs font-mono text-amber-400">
                  <Clock className="w-3.5 h-3.5" />
                  <span>PRE-AUTH HOLD ACTIVE: {receipt.payment_hold_id}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="console-page" data-testid="pillar-evaluation-matrix">
        <div className="console-kicker">The 4-Pillar Evaluation Matrix</div>

        <div className="pillar-grid">
          {/* Authority */}
          <div className="pillar-card">
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-mono text-[#8d94a1]">01 / AUTHORITY</span>
              <StatusBadge status={authority.passed !== false ? "PASS" : "FAIL"} size="sm" />
            </div>
            <div>
              <div className="font-serif text-lg text-[#f0eef5]">Policy Mandate</div>
              <p className="text-xs text-[#8d94a1] mt-1 leading-relaxed">{authority.reason || "Mandate checks evaluated."}</p>
            </div>
          </div>

          {/* Intent */}
          <div className="pillar-card">
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-mono text-[#8d94a1]">02 / INTENT</span>
              <StatusBadge status={intent.substitution ? "SUBSTITUTION" : intent.passed !== false ? "PASS" : "FAIL"} size="sm" />
            </div>
            <div>
              <div className="font-serif text-lg text-[#f0eef5]">Fidelity Score</div>
              <p className="text-xs text-[#8d94a1] mt-1 leading-relaxed">{intent.reason || "Product requirements evaluated."}</p>
            </div>
            {intent.score !== undefined && (
              <div className="pt-2 border-t border-[#dddee8]/10 text-[11px] font-mono text-[#8d94a1]">
                Fidelity: {(intent.score * 100).toFixed(0)}%
              </div>
            )}
          </div>

          {/* Evidence */}
          <div className="pillar-card">
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-mono text-[#8d94a1]">03 / EVIDENCE</span>
              <StatusBadge status={evidence.conflict ? "CONFLICT" : "VERIFIED"} size="sm" />
            </div>
            <div>
              <div className="font-serif text-lg text-[#f0eef5]">SKU Verification</div>
              <p className="text-xs text-[#8d94a1] mt-1 leading-relaxed">{evidence.reason || "Merchant specification verified."}</p>
            </div>
          </div>

          {/* Behavior */}
          <div className="pillar-card">
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-mono text-[#8d94a1]">04 / BEHAVIOR</span>
              <StatusBadge status={behavior.risk_score > 0.7 ? "HIGH RISK" : behavior.risk_score > 0.35 ? "MEDIUM RISK" : "LOW RISK"} size="sm" />
            </div>
            <div>
              <div className="font-serif text-lg text-[#f0eef5]">ML Risk Engine</div>
              <p className="text-xs text-[#8d94a1] mt-1 leading-relaxed">{behavior.reason || "Velocity baseline monitored."}</p>
            </div>
            {behavior.risk_score !== undefined && (
              <div className="pt-2 border-t border-[#dddee8]/10 text-[11px] font-mono text-[#8d94a1]">
                Risk Score: {behavior.risk_score.toFixed(2)}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 4. Cryptographic Provenance Timeline */}
      {provenance.length > 0 && (
        <section className="console-page" data-testid="provenance-timeline">
          <div className="console-kicker">Cryptographic Provenance &amp; Observability Trail</div>

          <div className="timeline-panel">
            <div className="relative border-l border-[#dddee8]/15 ml-3 pl-6 sm:pl-8 space-y-6">
              {provenance.map((evt, idx) => (
                <div key={idx} className="relative">
                  <span className="absolute -left-[31px] sm:-left-[37px] top-1.5 w-2 h-2 rounded-full bg-[#07090d] border-2 border-[#a99df2]" />
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                    <span className="font-mono text-xs font-bold text-[#a99df2]">
                      {String(evt.seq || idx + 1).padStart(2, "0")}
                    </span>
                    <span className="text-xs sm:text-sm font-sans font-bold text-[#f0eef5]">
                      {evt.event_type || evt.title || "Audit Event"}
                    </span>
                    {evt.event_hash && (
                      <span className="font-mono text-[10px] text-[#8d94a1] bg-[#07090d] px-1.5 py-0.5 rounded border border-[#dddee8]/10">
                        SHA256: {evt.event_hash.slice(0, 8)}...
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#8d94a1] mt-1 leading-relaxed">
                    {formatEventPayload(evt)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="console-page" data-testid="transaction-receipt-panel">
        <div className="console-panel-header">
          <div>
            <span className="console-kicker">Immutable Trust Receipt</span>
            <h2 className="console-panel-title">Trust Receipt</h2>
          </div>
          <button className="console-button" onClick={downloadPdf} data-testid="export-receipt-pdf-button">
            <Download size={13} />
            <span>Export Receipt PDF</span>
          </button>
        </div>

        <div className="console-panel">
          <div className="flex justify-between items-center pb-5 border-b border-[#dddee8]/10">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-[#a99df2]" />
              <span className="font-serif text-sm font-bold text-[#f0eef5]">SPENDGUARD TRUST RECEIPT</span>
            </div>
            <span className="font-mono text-xs text-[#8d94a1]">ID / {receipt.transaction_id || transactionId}</span>
          </div>

          <div className="space-y-2">
            <div className="text-[10px] font-mono font-bold tracking-widest text-[#8d94a1] uppercase">DECISION</div>
            <div className="flex items-center gap-3">
              <StatusBadge status={receipt.decision} />
              <span className="text-xs text-[#8d94a1] font-mono">Confidence: {(parseFloat(receipt.confidence || 1) * 100).toFixed(0)}%</span>
            </div>
            <p className="text-xs text-[#dddee8] leading-relaxed pt-2">
              {receipt.decision_reason}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default ConsoleTransactionDetail;
