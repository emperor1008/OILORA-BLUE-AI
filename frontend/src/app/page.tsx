"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Plus,
  FolderOpen,
  RefreshCw,
  AlertCircle,
  Clock,
  FileText,
  Anchor,
  ArrowRight,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import StatusChip from "@/components/StatusChip";
import {
  listCases,
  CaseSummary,
  formatDate,
  stageLabel,
  errorRequestId,
} from "@/lib/api";

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);

  const loadCases = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setRequestId(null);
      const response = await listCases(0, 100);
      setCases(response.data || []);
      setTotal(response.total || 0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load investigations",
      );
      setRequestId(errorRequestId(err) || null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  return (
    <AppShell>
      <div className="p-6 lg:p-8 max-w-7xl mx-auto">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-ocean-midnight">
              Investigation Dashboard
            </h1>
            <p className="text-sm text-ocean-muted mt-1">
              Maritime oil-spill intelligence investigations
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadCases}
              disabled={loading}
              className="btn-secondary text-sm"
              aria-label="Refresh case list"
            >
              <RefreshCw
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
              />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <Link href="/new" className="btn-primary text-sm">
              <Plus className="w-4 h-4" />
              New Investigation
            </Link>
          </div>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="card px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-ocean-blue/10 flex items-center justify-center">
                <FolderOpen className="w-5 h-5 text-ocean-blue" />
              </div>
              <div>
                <p className="text-2xl font-bold text-ocean-midnight">
                  {total}
                </p>
                <p className="text-xs text-ocean-muted">Total Investigations</p>
              </div>
            </div>
          </div>
          <div className="card px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
                <Anchor className="w-5 h-5 text-ocean-success" />
              </div>
              <div>
                <p className="text-2xl font-bold text-ocean-midnight">
                  {cases.filter((c) => c.status === "completed").length}
                </p>
                <p className="text-xs text-ocean-muted">Completed</p>
              </div>
            </div>
          </div>
          <div className="card px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center">
                <Clock className="w-5 h-5 text-ocean-warning" />
              </div>
              <div>
                <p className="text-2xl font-bold text-ocean-midnight">
                  {cases.filter(
                    (c) =>
                      c.status === "processing" ||
                      c.status === "awaiting_review",
                  ).length}
                </p>
                <p className="text-xs text-ocean-muted">In Progress</p>
              </div>
            </div>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="card px-5 py-4 mb-6 bg-red-50 border-red-200">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-700">
                  Failed to load investigations
                </p>
                <p className="text-xs text-red-500 mt-0.5">{error}</p>
                {requestId && (
                  <p className="text-[10px] text-red-400 mt-1 font-mono">
                    Request ID: {requestId}
                  </p>
                )}
              </div>
              <button onClick={loadCases} className="btn-ghost text-xs ml-auto">
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && cases.length === 0 && (
          <div className="card px-5 py-12 text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">Loading investigations...</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && cases.length === 0 && (
          <div className="card px-5 py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-ocean-ice mx-auto mb-4 flex items-center justify-center">
              <FileText className="w-8 h-8 text-ocean-muted" />
            </div>
            <h3 className="text-lg font-semibold text-ocean-midnight mb-2">
              Begin a Maritime Analysis
            </h3>
            <p className="text-sm text-ocean-muted max-w-md mx-auto mb-6">
              Create a case to register satellite imagery, review geospatial
              evidence, and document an environmental incident.
            </p>
            <Link href="/new" className="btn-primary inline-flex">
              <Plus className="w-4 h-4" />
              Create Case
            </Link>
            <p className="text-xs text-ocean-muted mt-4">
              No cases have been created yet.
            </p>
          </div>
        )}

        {/* Case list */}
        {!loading && cases.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-ocean-muted uppercase tracking-wider">
              Investigations ({total})
            </h2>
            {cases.map((caseItem) => (
              <Link
                key={caseItem.id}
                href={`/cases/${caseItem.id}`}
                className="card px-5 py-4 flex items-center gap-4 hover:shadow-panel transition-shadow group"
              >
                {/* Status indicator */}
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                    caseItem.status === "completed"
                      ? "bg-emerald-50"
                      : caseItem.status === "failed"
                        ? "bg-red-50"
                        : caseItem.status === "processing" ||
                            caseItem.status === "awaiting_review"
                          ? "bg-amber-50"
                          : "bg-ocean-ice"
                  }`}
                >
                  <FolderOpen
                    className={`w-5 h-5 ${
                      caseItem.status === "completed"
                        ? "text-ocean-success"
                        : caseItem.status === "failed"
                          ? "text-ocean-critical"
                          : caseItem.status === "processing" ||
                              caseItem.status === "awaiting_review"
                            ? "text-ocean-warning"
                            : "text-ocean-muted"
                    }`}
                  />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-ocean-midnight truncate">
                      {caseItem.title}
                    </h3>
                    <StatusChip status={caseItem.status} />
                  </div>
                  <div className="flex items-center gap-4 text-xs text-ocean-muted">
                    <span>{stageLabel(caseItem.current_stage)}</span>
                    {caseItem.region && <span>{caseItem.region}</span>}
                    <span>{caseItem.file_count} files</span>
                    <span>{formatDate(caseItem.updated_at)}</span>
                  </div>
                </div>

                {/* Arrow */}
                <ArrowRight className="w-4 h-4 text-ocean-border group-hover:text-ocean-blue transition-colors shrink-0" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
