import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusBadge } from "./StatusBadge";
import { ArrowLeft, Clock, Check, X, Shield, Download, AlertTriangle, RefreshCw } from "lucide-react";
import { jsPDF } from "jspdf";

export function ConsoleTransactionDetail({ transactionId, onBack, onVerifySuccess }) {
  const [loading, setLoading] = useState(true);
  const [receipt, setReceipt] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyOutcome, setVerifyOutcome] = useState(null);

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

    doc.setFillColor(243, 241, 236);
    doc.rect(0, 0, width, height, "F");
    doc.setDrawColor(190, 185, 177);
    doc.setLineWidth(0.8);
    doc.rect(24, 24, width - 48, height - 48);

    doc.setTextColor(24, 26, 34);
    doc.setFont("courier", "bold");
    doc.setFontSize(10);
    doc.text("SPENDGUARD", margin, 66);
    doc.setFont("courier", "normal");
    doc.text(`TRUST RECEIPT / ${receipt.transaction_id || transactionId}`, width - margin, 66, { align: "right" });
    doc.line(margin, 82, width - margin, 82);

    doc.setFont("times", "normal");
    doc.setFontSize(28);
    doc.text("Trust Receipt", margin, 124);

    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(102, 105, 116);
    doc.text("DECISION RATIONALE", margin, 160);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(24, 26, 34);
    doc.text(doc.splitTextToSize(receipt.decision_reason || "Evaluated by SpendGuard.", 480), margin, 178);

    doc.line(margin, 210, width - margin, 210);
    doc.setFont("courier", "normal");
    doc.setFontSize(8);
    doc.setTextColor(102, 105, 116);
    doc.text("AMOUNT", margin, 236);
    doc.text("DECISION", width / 2, 236);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(24, 26, 34);
    doc.text(`INR ${parseFloat(receipt.amount || 0).toLocaleString()}`, margin, 256);
    doc.text(receipt.decision || "UNKNOWN", width / 2, 256);

    doc.save(`spendguard-receipt-${transactionId}.pdf`);
  };

  if (loading) {
    return (
      <div className="py-20 text-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-[#a99df2]" />
        <p className="text-sm font-mono text-[#8d94a1]">Loading investigation audit records...</p>
      </div>
    );
  }

  if (error || !receipt) {
    return (
      <div className="p-8 border border-rose-500/20 bg-rose-950/20 rounded-sm text-center space-y-4">
        <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto" />
        <h3 className="font-serif text-lg text-[#f0eef5]">Failed to load transaction</h3>
        <p className="text-xs font-mono text-[#8d94a1]">{error || "Transaction not found"}</p>
        <button
          onClick={onBack}
          className="px-4 py-1.5 bg-[#10141e] border border-[#dddee8]/20 text-xs font-mono hover:text-[#a99df2]"
        >
          Back to List
        </button>
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

  return (
    <div className="space-y-10 pb-24">
      {/* 1. Header & Actions */}
      <div className="space-y-4 border-b border-[#dddee8]/10 pb-6">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-mono text-[#8d94a1] hover:text-[#a99df2] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Transactions</span>
        </button>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-serif text-3xl sm:text-4xl text-[#f0eef5]">
                Transaction <span className="font-mono text-[#a99df2]">{receipt.transaction_id || transactionId}</span>
              </h1>
              <StatusBadge status={receipt.decision} />
            </div>
            <p className="text-[#8d94a1] text-xs sm:text-sm mt-1 font-mono">
              Evaluated on {receipt.timestamp ? new Date(receipt.timestamp).toLocaleString() : "Live"} • Agent: {receipt.agent_id}
            </p>
          </div>

          {receipt.decision === "VERIFY" && !verifyOutcome && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleVerify(false)}
                disabled={verifying}
                className="px-4 py-2 border border-rose-500/40 text-rose-400 hover:bg-rose-950/40 rounded-sm text-xs font-mono font-semibold tracking-wide transition-colors flex items-center gap-1.5 disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reject &amp; Void</span>
              </button>
              <button
                onClick={() => handleVerify(true)}
                disabled={verifying}
                className="px-5 py-2 bg-[#f0eef5] text-[#07090d] hover:bg-white rounded-sm text-xs font-mono font-bold tracking-wide transition-all hover:-translate-y-0.5 flex items-center gap-1.5 shadow-lg disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Approve &amp; Capture</span>
              </button>
            </div>
          )}

          {verifyOutcome && (
            <div
              className={`px-4 py-2 rounded-sm text-xs font-mono font-bold flex items-center gap-2 ${
                verifyOutcome === "APPROVED"
                  ? "bg-emerald-950/60 border border-emerald-500/30 text-emerald-400"
                  : "bg-rose-950/60 border border-rose-500/30 text-rose-400"
              }`}
            >
              <Shield className="w-4 h-4" />
              <span>OPERATOR DECISION RECORDED: {verifyOutcome}</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. Intent Investigation: Request vs Selected */}
      <div className="space-y-4">
        <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#a99df2]">
          INTENT FIDELITY INVESTIGATION
        </div>

        <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[#dddee8]/10 overflow-hidden">
          <div className="p-6 sm:p-8 space-y-4">
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

          <div className="p-6 sm:p-8 space-y-4 flex flex-col justify-between">
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
      </div>

      {/* 3. The 4-Pillar Evaluation Matrix */}
      <div className="space-y-4">
        <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#a99df2]">
          THE 4-PILLAR EVALUATION MATRIX
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Authority */}
          <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-5 space-y-3">
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
          <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-5 space-y-3">
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
          <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-5 space-y-3">
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
          <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-5 space-y-3">
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
      </div>

      {/* 4. Cryptographic Provenance Timeline */}
      {provenance.length > 0 && (
        <div className="space-y-4">
          <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#a99df2]">
            CRYPTOGRAPHIC PROVENANCE &amp; OBSERVABILITY TRAIL
          </div>

          <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-6 sm:p-8">
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
                    {typeof evt.payload === "string" ? evt.payload : JSON.stringify(evt.payload || evt.detail || "")}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 5. Trust Receipt & Export Action */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#a99df2]">
            IMMUTABLE TRUST RECEIPT
          </div>
          <button
            onClick={downloadPdf}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#10141e] border border-[#dddee8]/15 hover:border-[#a99df2]/40 rounded-sm text-xs font-mono text-[#8d94a1] hover:text-[#f0eef5] transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-[#a99df2]" />
            <span>Export Receipt PDF</span>
          </button>
        </div>

        <div className="bg-[#0b0e14] border border-[#dddee8]/15 rounded-sm p-6 sm:p-8 space-y-6">
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
      </div>
    </div>
  );
}

export default ConsoleTransactionDetail;
