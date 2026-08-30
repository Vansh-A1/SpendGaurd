import React from "react";

export function StatusBadge({ status, size = "md" }) {
  if (!status) return null;
  const s = String(status).toUpperCase();

  let styles = "bg-slate-800/80 text-slate-300 border-slate-700/60";

  if (
    s === "ALLOW" ||
    s === "PASS" ||
    s === "MATCHED" ||
    s === "VERIFIED" ||
    s === "LOW RISK" ||
    s === "ACTIVE" ||
    s === "CAPTURED" ||
    s === "APPROVED"
  ) {
    styles = "bg-emerald-950/60 text-emerald-400 border-emerald-500/30";
  } else if (
    s === "VERIFY" ||
    s === "SUBSTITUTION" ||
    s === "MEDIUM RISK" ||
    s === "AUTHORIZED" ||
    s === "HOLD ACTIVE" ||
    s === "PENDING"
  ) {
    styles = "bg-amber-950/60 text-amber-400 border-amber-500/30";
  } else if (
    s === "BLOCK" ||
    s === "FAIL" ||
    s === "FAILED" ||
    s === "CONFLICT" ||
    s === "HIGH RISK" ||
    s === "RESTRICTED" ||
    s === "VOIDED" ||
    s === "DENIED" ||
    s === "REJECTED"
  ) {
    styles = "bg-rose-950/60 text-rose-400 border-rose-500/30";
  } else if (s === "UNVERIFIABLE" || s === "COMPLETED") {
    styles = "bg-blue-950/60 text-blue-400 border-blue-500/30";
  }

  const sizeStyles =
    size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center font-mono font-medium tracking-wider uppercase rounded border ${styles} ${sizeStyles}`}
    >
      {status}
    </span>
  );
}

export default StatusBadge;
