"use client";

import { useEffect, useState } from "react";
import { Menu, Anchor } from "lucide-react";
import { getHealth } from "@/lib/api";

interface HeaderProps {
  onMenuToggle?: () => void;
}

type BackendState = "checking" | "operational" | "unavailable";

const HEALTH_POLL_INTERVAL_MS = 15_000;
const HEALTH_TIMEOUT_MS = 5_000;

/**
 * Real backend health probe. The indicator never claims "Operational" until a
 * genuine `/api/health` request succeeds; the probe re-runs on a slow interval
 * (not rapid polling) so a stopped backend flips to Unavailable.
 */
function useBackendHealth(): BackendState {
  const [state, setState] = useState<BackendState>("checking");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const check = async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
      try {
        const response = await getHealth(controller.signal);
        if (!cancelled) {
          setState(response?.success ? "operational" : "unavailable");
        }
      } catch {
        if (!cancelled) setState("unavailable");
      } finally {
        clearTimeout(timeout);
        if (!cancelled) {
          timer = setTimeout(check, HEALTH_POLL_INTERVAL_MS);
        }
      }
    };

    check();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return state;
}

const STATUS_META: Record<BackendState, { dot: string; label: string; text: string }> = {
  checking: {
    dot: "bg-ocean-warning",
    label: "Checking backend connection",
    text: "Checking…",
  },
  operational: {
    dot: "bg-ocean-success",
    label: "Backend operational",
    text: "Operational",
  },
  unavailable: {
    dot: "bg-ocean-critical",
    label: "Backend unavailable",
    text: "Unavailable",
  },
};

export default function Header({ onMenuToggle }: HeaderProps) {
  const backend = useBackendHealth();
  const meta = STATUS_META[backend];

  return (
    <header className="h-14 bg-white border-b border-ocean-border flex items-center px-4 lg:px-6 shrink-0">
      {/* Mobile menu button */}
      <button
        onClick={onMenuToggle}
        className="lg:hidden p-2 -ml-2 mr-2 text-ocean-muted hover:text-ocean-slate"
        aria-label="Toggle navigation menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile brand */}
      <div className="lg:hidden flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-ocean-blue to-ocean-aqua flex items-center justify-center">
          <Anchor className="w-4 h-4 text-white" />
        </div>
        <span className="text-sm font-bold text-ocean-midnight">OILORA BLUE AI</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right side */}
      <div className="flex items-center gap-3 text-xs text-ocean-muted">
        <span className="hidden sm:inline">Local Mode</span>
        <span
          role="status"
          aria-live="polite"
          title={meta.label}
          className="flex items-center gap-1.5"
        >
          <span
            aria-hidden
            className={`w-2 h-2 rounded-full ${meta.dot} ${
              backend === "checking" ? "animate-pulse" : ""
            }`}
          />
          <span className="text-[11px]">{meta.text}</span>
        </span>
      </div>
    </header>
  );
}