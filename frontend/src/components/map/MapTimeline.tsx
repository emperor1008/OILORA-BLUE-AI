"use client";

import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Clock,
} from "lucide-react";
import { formatUtc } from "@/lib/api";

interface MapTimelineProps {
  range: { start: string; end: string } | null;
  disabledReason?: string | null;
}

/**
 * Shared scientific timeline. Uses only backend-provided timestamps. Playback
 * is disabled until real time-indexed feature data exists (drift particles,
 * AIS positions, environmental steps) - no synthetic movement is ever shown.
 */
export default function MapTimeline({ range, disabledReason }: MapTimelineProps) {
  const hasRange = Boolean(range && range.start && range.end);

  return (
    <div className="flex items-center gap-3 px-3 lg:px-4 h-14 bg-white border-t border-ocean-border shrink-0">
      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          disabled
          aria-label="Previous time step (unavailable)"
          className="p-2 rounded-md text-ocean-border cursor-not-allowed"
          title="Playback unavailable"
        >
          <SkipBack className="w-4 h-4" />
        </button>
        <button
          type="button"
          disabled
          aria-label="Play timeline (unavailable)"
          aria-disabled
          title={
            disabledReason ||
            "Timeline playback requires time-indexed feature data"
          }
          className="p-2 rounded-md text-ocean-border cursor-not-allowed"
        >
          <Play className="w-4 h-4" />
        </button>
        <button
          type="button"
          disabled
          aria-label="Next time step (unavailable)"
          className="p-2 rounded-md text-ocean-border cursor-not-allowed"
        >
          <SkipForward className="w-4 h-4" />
        </button>
      </div>

      <input
        type="range"
        disabled
        className="flex-1 min-w-0 accent-ocean-teal opacity-40 cursor-not-allowed"
        aria-label="Timeline scrubber (unavailable)"
      />

      <div className="flex items-center gap-3 text-[11px] text-ocean-muted shrink-0 font-mono">
        <Clock className="w-3.5 h-3.5 text-ocean-muted" />
        {hasRange ? (
          <>
            <span>{formatUtc(range?.start ?? null)}</span>
            <span aria-hidden>→</span>
            <span>{formatUtc(range?.end ?? null)}</span>
          </>
        ) : (
          <span>No time-indexed data</span>
        )}
      </div>

      <select
        disabled
        aria-label="Playback speed (unavailable)"
        className="shrink-0 text-[11px] border border-ocean-border rounded-md px-1.5 py-1 bg-ocean-ice text-ocean-border cursor-not-allowed"
      >
        <option>1×</option>
      </select>

      <button
        type="button"
        disabled
        aria-label="Reset timeline (unavailable)"
        className="p-2 rounded-md text-ocean-border cursor-not-allowed"
      >
        <RotateCcw className="w-4 h-4" />
      </button>

      {/* Honest coverage note */}
      <p className="hidden md:block text-[10px] text-ocean-muted max-w-[220px] truncate" title={disabledReason ?? undefined}>
        {disabledReason ||
          "Timeline playback becomes available when time-indexed scientific data (drift, AIS, environmental steps) is registered and processed."}
      </p>
      {hasRange && <Pause className="hidden w-3.5 h-3.5 text-ocean-muted" aria-hidden />}
    </div>
  );
}
