"use client";

import { statusColor } from "@/lib/api";

interface StatusChipProps {
  status: string;
}

/**
 * Shared status chip: maps a backend case/job status to the standard
 * ocean-slate chip colour set and renders the human-readable label.
 */
export default function StatusChip({ status }: StatusChipProps) {
  return (
    <span className={`chip ${statusColor(status)}`}>
      {status.replace("_", " ")}
    </span>
  );
}