"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  CheckCircle,
  Clock,
  Globe,
  KeyRound,
  Loader2,
  RefreshCw,
  Satellite,
  ShieldCheck,
  Waves,
  Wind,
  XCircle,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import {
  listSources,
  testSource,
  SourceInfo,
  SourceStatus,
  errorRequestId,
} from "@/lib/api";

const STATUS_META: Record<
  SourceStatus,
  { label: string; chip: string; dot: string }
> = {
  connected: { label: "Connected", chip: "chip-success", dot: "bg-ocean-success" },
  authentication_required: {
    label: "Authentication required",
    chip: "chip-warning",
    dot: "bg-ocean-warning",
  },
  source_unavailable: {
    label: "Source unavailable",
    chip: "chip-critical",
    dot: "bg-ocean-critical",
  },
  not_configured: { label: "Not configured", chip: "chip-default", dot: "bg-ocean-muted" },
  local_file_workflow: {
    label: "Local-file workflow",
    chip: "chip-info",
    dot: "bg-ocean-teal",
  },
  not_verified: { label: "Not verified", chip: "chip-default", dot: "bg-ocean-muted" },
};

const CATEGORY_ICON: Record<string, typeof Activity> = {
  satellite_radar: Satellite,
  optical_context: Globe,
  ocean_physics: Waves,
  atmospheric: Wind,
  vessel_ais: Activity,
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "Never verified";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Never verified";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceInfo[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, string>>({});

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setRequestId(null);
      const response = await listSources();
      if (response.success && response.data) {
        setSources(response.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data sources");
      setRequestId(errorRequestId(err) || null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runTest = async (sourceId: string) => {
    setTesting(sourceId);
    setTestResult((prev) => ({ ...prev, [sourceId]: "" }));
    try {
      const response = await testSource(sourceId);
      if (response.success && response.data) {
        const status = STATUS_META[response.data.configured_status];
        setTestResult((prev) => ({
          ...prev,
          [sourceId]: status.label,
        }));
        // Refresh the full list so persisted state is visible everywhere.
        await load();
      }
    } catch (err) {
      setTestResult((prev) => ({
        ...prev,
        [sourceId]: err instanceof Error ? err.message : "Test failed",
      }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <AppShell>
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-2xl font-bold text-ocean-midnight">Data Sources</h1>
            <p className="text-sm text-ocean-muted mt-1">
              Official provider registry. No source reports Connected without a
              successful real probe.
            </p>
          </div>
          <button
            onClick={load}
            className="btn-secondary text-sm"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="card px-5 py-4 text-center mb-6">
            <XCircle className="w-10 h-10 text-ocean-critical mx-auto mb-2" />
            <p className="text-sm text-ocean-muted">{error}</p>
            {requestId && (
              <p className="text-xs text-ocean-muted font-mono mt-2">
                Request ID: {requestId}
              </p>
            )}
          </div>
        )}

        {loading && !sources && !error && (
          <div className="card px-5 py-12 text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">Loading source registry...</p>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 mt-6">
          {sources?.map((source) => {
            const meta = STATUS_META[source.configured_status];
            const Icon = CATEGORY_ICON[source.data_category] || Activity;
            return (
              <div key={source.source_id} className="card p-5 flex flex-col">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-ocean-ice flex items-center justify-center shrink-0">
                    <Icon className="w-5 h-5 text-ocean-blue" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h2 className="text-sm font-semibold text-ocean-midnight leading-snug">
                      {source.source_name}
                    </h2>
                    <p className="text-[11px] text-ocean-muted mt-0.5">
                      {source.organization}
                    </p>
                  </div>
                  <span className={`chip ${meta.chip} text-[10px] shrink-0`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${meta.dot} inline-block mr-1`} />
                    {meta.label}
                  </span>
                </div>

                <p className="text-[11px] text-ocean-slate mt-3 leading-snug">
                  {source.access_method}
                </p>

                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[11px] text-ocean-muted">
                  <span>Coverage: {source.spatial_coverage}</span>
                  <span>Refresh: {source.refresh_frequency}</span>
                </div>
                <div className="text-[11px] text-ocean-muted mt-1">
                  Format: {source.expected_format}
                </div>

                {/* Credential status — masked boolean only */}
                <div className="mt-3 flex items-start gap-1.5 text-[11px]">
                  {source.authentication_required ? (
                    source.authentication_configured ? (
                      <span className="text-ocean-success flex items-center gap-1">
                        <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                        Credentials configured on the backend
                      </span>
                    ) : (
                      <span className="text-ocean-warning flex items-center gap-1">
                        <KeyRound className="w-3.5 h-3.5 shrink-0" />
                        Authentication required
                      </span>
                    )
                  ) : (
                    <span className="text-ocean-muted flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5 shrink-0" />
                      No credentials needed
                    </span>
                  )}
                </div>
                {source.authentication_note && (
                  <p className="text-[10px] text-ocean-muted mt-1.5 leading-snug">
                    {source.authentication_note}
                  </p>
                )}

                <div className="mt-3 flex items-center gap-1 text-[10px] text-ocean-muted">
                  <Clock className="w-3 h-3 shrink-0" />
                  Last verified: {formatTimestamp(source.last_successful_access)}
                  {source.last_failed_access && (
                    <span className="text-ocean-critical">
                      {" "}
                      · last failure {formatTimestamp(source.last_failed_access)}
                    </span>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-ocean-border flex items-center justify-between gap-2">
                  {source.documentation_url ? (
                    <a
                      href={source.documentation_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-ocean-blue hover:underline inline-flex items-center gap-1"
                    >
                      Documentation <ArrowUpRight className="w-3 h-3" />
                    </a>
                  ) : (
                    <span className="text-[11px] text-ocean-muted">{source.licence}</span>
                  )}
                  <button
                    onClick={() => runTest(source.source_id)}
                    disabled={testing === source.source_id}
                    className="btn-secondary text-[11px] px-2.5 py-1.5"
                  >
                    {testing === source.source_id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Activity className="w-3.5 h-3.5" />
                    )}
                    Test connection
                  </button>
                </div>

                {testResult[source.source_id] && (
                  <p className="mt-2 text-[11px] text-ocean-slate flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5 text-ocean-success shrink-0" />
                    {testResult[source.source_id]}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {sources && sources.length === 0 && (
          <div className="card px-5 py-12 text-center mt-6">
            <p className="text-sm text-ocean-muted">
              No data sources are registered on this backend.
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}