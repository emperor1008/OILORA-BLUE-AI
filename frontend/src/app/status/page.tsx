"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Database,
  HardDrive,
  Wifi,
  WifiOff,
  Cpu,
  CheckCircle,
  XCircle,
  HelpCircle,
  RefreshCw,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import {
  getHealth,
  getSystemStatus,
  SystemStatus,
  errorRequestId,
} from "@/lib/api";

type RowState = "ok" | "error" | "unknown";

interface StatusRow {
  label: string;
  state: RowState;
  detail: string;
  icon: typeof Activity;
}

function RowIcon({ state }: { state: RowState }) {
  if (state === "ok") return <CheckCircle className="w-5 h-5 text-ocean-success shrink-0" />;
  if (state === "error") return <XCircle className="w-5 h-5 text-ocean-critical shrink-0" />;
  return <HelpCircle className="w-5 h-5 text-ocean-muted shrink-0" />;
}

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);

  // Internet connectivity comes from the browser (navigator.onLine + events),
  // never from the backend — they measure different things.
  const [online, setOnline] = useState<boolean>(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  // API-service availability comes from a real /api/health probe.
  const [apiState, setApiState] = useState<"checking" | "operational" | "unavailable">(
    "checking",
  );

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const response = await getHealth();
        if (!cancelled) {
          setApiState(response?.success ? "operational" : "unavailable");
        }
      } catch {
        if (!cancelled) setApiState("unavailable");
      }
    };
    probe();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      setRequestId(null);
      const response = await getSystemStatus();
      if (response.success && response.data) {
        setStatus(response.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
      setRequestId(errorRequestId(err) || null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  // Each row reports exactly what it measures. "Unknown" is shown instead of a
  // green check whenever a value has not been verified.
  const items: StatusRow[] = [
    {
      label: "Internet connection",
      state: online ? "ok" : "error",
      detail: online ? "Online" : "Offline",
      icon: online ? Wifi : WifiOff,
    },
    {
      label: "API service",
      state:
        apiState === "operational"
          ? "ok"
          : apiState === "unavailable"
            ? "error"
            : "unknown",
      detail:
        apiState === "operational"
          ? "Operational"
          : apiState === "unavailable"
            ? "Unavailable"
            : "Checking…",
      icon: Activity,
    },
    {
      label: "Backend",
      state: status ? (status.backend_status === "healthy" ? "ok" : "error") : "unknown",
      detail: status ? status.backend_status : "Unknown",
      icon: Activity,
    },
    {
      label: "Database",
      state: status
        ? status.database_status === "connected"
          ? "ok"
          : "error"
        : "unknown",
      detail: status ? status.database_status : "Unknown",
      icon: Database,
    },
    {
      label: "Detection Model",
      state: status
        ? status.model_available
          ? "ok"
          : "error"
        : "unknown",
      detail: status ? (status.model_available ? "Available" : "Not loaded") : "Unknown",
      icon: Cpu,
    },
    {
      label: "Disk Space",
      state: status ? (status.disk_space_gb > 10 ? "ok" : "error") : "unknown",
      detail: status ? `${status.disk_space_gb} GB available` : "Unknown",
      icon: HardDrive,
    },
  ];

  const anyError = items.some((item) => item.state === "error");
  const anyUnknown = items.some((item) => item.state === "unknown");

  return (
    <AppShell>
      <div className="p-6 lg:p-8 max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-ocean-midnight">
              System Status
            </h1>
            <p className="text-sm text-ocean-muted mt-1">
              Application readiness and system health
            </p>
          </div>
          <button onClick={loadStatus} className="btn-secondary text-sm">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {loading && !status && !error && (
          <div className="card px-5 py-12 text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">Checking system status...</p>
          </div>
        )}

        {error && (
          <div className="card px-5 py-8 text-center mb-6">
            <XCircle className="w-12 h-12 text-ocean-critical mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">{error}</p>
            {requestId && (
              <p className="text-xs text-ocean-muted font-mono mt-2">
                Request ID: {requestId}
              </p>
            )}
            <p className="text-xs text-ocean-muted mt-3">
              Detailed readiness rows below still reflect what could be verified.
            </p>
          </div>
        )}

        <div className="space-y-4">
          {/* Overall status */}
          <div
            className={`card px-6 py-5 ${
              !anyError && !anyUnknown
                ? "border-emerald-200 bg-emerald-50/30"
                : "border-amber-200 bg-amber-50/30"
            }`}
          >
            <div className="flex items-center gap-3">
              {!anyError && !anyUnknown ? (
                <CheckCircle className="w-6 h-6 text-ocean-success" />
              ) : anyError ? (
                <XCircle className="w-6 h-6 text-ocean-warning" />
              ) : (
                <HelpCircle className="w-6 h-6 text-ocean-muted" />
              )}
              <div>
                <p className="text-lg font-semibold text-ocean-midnight">
                  {!anyError && !anyUnknown
                    ? "All Systems Operational"
                    : anyError
                      ? "Some Systems Unavailable"
                      : "Status Partially Unknown"}
                </p>
                <p className="text-xs text-ocean-muted">
                  {status ? (
                    <>
                      Version {status.app_version} ·{" "}
                      {status.local_demo_mode ? "Local Mode" : "Production"}
                    </>
                  ) : (
                    "Readiness values that could not be verified are shown as Unknown."
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Individual checks */}
          <div className="card divide-y divide-ocean-border">
            {items.map((item) => (
              <div key={item.label} className="flex items-center gap-4 px-6 py-4">
                <item.icon className="w-5 h-5 text-ocean-muted shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-ocean-slate">
                    {item.label}
                  </p>
                  <p className="text-xs text-ocean-muted">{item.detail}</p>
                </div>
                <RowIcon state={item.state} />
              </div>
            ))}
          </div>

          {/* Model checksum */}
          {status?.model_checksum && (
            <div className="card px-6 py-4">
              <p className="text-xs text-ocean-muted mb-1">Model Checksum (SHA-256)</p>
              <p className="font-mono text-xs text-ocean-slate break-all">
                {status.model_checksum}
              </p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}