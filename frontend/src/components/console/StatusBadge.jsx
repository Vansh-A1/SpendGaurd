import React from "react";

export function StatusBadge({ status }) {
  if (!status) return null;
  const normalized = String(status).toUpperCase().replace(/\s+/g, "-").toLowerCase();
  return <span className={`status-badge status-${normalized}`} data-testid={`status-${normalized}`}>{status}</span>;
}

export default StatusBadge;
