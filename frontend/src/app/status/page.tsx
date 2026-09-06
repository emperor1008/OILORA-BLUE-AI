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
  RefreshCw,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import { getSystemStatus, SystemStatus } from "@/lib/api";

export default function StatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getSystemStatus();
      if (response.success && response.data) {
        setStatus(response.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const items = status
    ? [
        {
          label: "Backend",
          status: status.backend_status === "healthy",
          detail: status.backend_status,
          icon: Activity,
        },
        {
          label: "Database",
          status: status.database_status === "connected",
          detail: status.database_status,
          icon: Database,
        },
        {
          label: "Detection Model",
          status: status.model_available,
          detail: status.model_available ? "Available" : "Not loaded",
          icon: Cpu,
        },
        {
          label: "Disk Space",
          status: status.disk_space_gb > 10,
          detail: `${status.disk_space_gb} GB available`,
          icon: HardDrive,
        },
        {
          label: "Network",
          status: true,
          detail: status.offline_ready
            ? "Offline-ready"
            : "Online required",
          icon: status.offline_ready ? WifiOff : Wifi,
        },
      ]
    : [];

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

        {loading && !status && (
          <div className="card px-5 py-12 text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">Checking system status...</p>
          </div>
        )}

        {error && (
          <div className="card px-5 py-8 text-center">
            <XCircle className="w-12 h-12 text-ocean-critical mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">{error}</p>
          </div>
        )}

        {status && (
          <div className="space-y-4">
            {/* Overall status */}
            <div
              className={`card px-6 py-5 ${
                items.every((i) => i.status)
                  ? "border-emerald-200 bg-emerald-50/30"
                  : "border-amber-200 bg-amber-50/30"
              }`}
            >
              <div className="flex items-center gap-3">
                {items.every((i) => i.status) ? (
                  <CheckCircle className="w-6 h-6 text-ocean-success" />
                ) : (
                  <XCircle className="w-6 h-6 text-ocean-warning" />
                )}
                <div>
                  <p className="text-lg font-semibold text-ocean-midnight">
                    {items.every((i) => i.status)
                      ? "All Systems Operational"
                      : "Some Systems Unavailable"}
                  </p>
                  <p className="text-xs text-ocean-muted">
                    Version {status.app_version} ·{" "}
                    {status.local_demo_mode ? "Local Demo Mode" : "Production"}
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
                  {item.status ? (
                    <CheckCircle className="w-5 h-5 text-ocean-success shrink-0" />
                  ) : (
                    <XCircle className="w-5 h-5 text-ocean-critical shrink-0" />
                  )}
                </div>
              ))}
            </div>

            {/* Model checksum */}
            {status.model_checksum && (
              <div className="card px-6 py-4">
                <p className="text-xs text-ocean-muted mb-1">Model Checksum (SHA-256)</p>
                <p className="font-mono text-xs text-ocean-slate break-all">
                  {status.model_checksum}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
