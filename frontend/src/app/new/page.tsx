"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { createCase, CaseCreate, errorRequestId } from "@/lib/api";

export default function NewCasePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [form, setForm] = useState<CaseCreate>({
    title: "",
    description: "",
    region: "",
    analyst_notes: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError("Title is required");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      setRequestId(null);
      const result = await createCase(form);
      if (result.success && result.data) {
        router.push(`/cases/${result.data.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create case");
      setRequestId(errorRequestId(err) || null);
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (
    field: keyof CaseCreate,
    value: string | number | undefined,
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <AppShell>
      <div className="p-6 lg:p-8 max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link
            href="/"
            className="p-2 rounded-lg hover:bg-ocean-ice text-ocean-muted hover:text-ocean-slate transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-ocean-midnight">
              New Investigation
            </h1>
            <p className="text-sm text-ocean-muted mt-0.5">
              Register a new maritime oil-spill investigation case
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Title */}
          <div className="card px-6 py-5 space-y-4">
            <h2 className="text-sm font-semibold text-ocean-midnight uppercase tracking-wider">
              Case Details
            </h2>

            <div>
              <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                Title <span className="text-ocean-critical">*</span>
              </label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => updateField("title", e.target.value)}
                placeholder="e.g., Arabian Sea Suspected Spill — Jan 2024"
                className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                Description
              </label>
              <textarea
                value={form.description || ""}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="Brief description of the investigation..."
                rows={3}
                className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue resize-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                  Region
                </label>
                <input
                  type="text"
                  value={form.region || ""}
                  onChange={(e) => updateField("region", e.target.value)}
                  placeholder="e.g., Arabian Sea"
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                  Analyst Notes
                </label>
                <input
                  type="text"
                  value={form.analyst_notes || ""}
                  onChange={(e) =>
                    updateField("analyst_notes", e.target.value)
                  }
                  placeholder="Initial observations..."
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
            </div>
          </div>

          {/* Time information */}
          <div className="card px-6 py-5 space-y-4">
            <h2 className="text-sm font-semibold text-ocean-midnight uppercase tracking-wider">
              Temporal Information
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                  Incident Time (UTC)
                </label>
                <input
                  type="datetime-local"
                  value={form.incident_time?.replace("Z", "").slice(0, 16) || ""}
                  onChange={(e) =>
                    updateField(
                      "incident_time",
                      e.target.value ? new Date(e.target.value).toISOString() : undefined,
                    )
                  }
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ocean-slate mb-1.5">
                  Observation Time (UTC)
                </label>
                <input
                  type="datetime-local"
                  value={form.observation_time?.replace("Z", "").slice(0, 16) || ""}
                  onChange={(e) =>
                    updateField(
                      "observation_time",
                      e.target.value ? new Date(e.target.value).toISOString() : undefined,
                    )
                  }
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
            </div>
          </div>

          {/* Geographic bounds */}
          <div className="card px-6 py-5 space-y-4">
            <h2 className="text-sm font-semibold text-ocean-midnight uppercase tracking-wider">
              Geographic Bounds (WGS 84)
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-ocean-muted mb-1">
                  Min Latitude
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="-90"
                  max="90"
                  value={form.bbox_min_lat ?? ""}
                  onChange={(e) =>
                    updateField(
                      "bbox_min_lat",
                      e.target.value ? parseFloat(e.target.value) : undefined,
                    )
                  }
                  placeholder="15.0"
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ocean-muted mb-1">
                  Min Longitude
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="-180"
                  max="180"
                  value={form.bbox_min_lon ?? ""}
                  onChange={(e) =>
                    updateField(
                      "bbox_min_lon",
                      e.target.value ? parseFloat(e.target.value) : undefined,
                    )
                  }
                  placeholder="68.0"
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ocean-muted mb-1">
                  Max Latitude
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="-90"
                  max="90"
                  value={form.bbox_max_lat ?? ""}
                  onChange={(e) =>
                    updateField(
                      "bbox_max_lat",
                      e.target.value ? parseFloat(e.target.value) : undefined,
                    )
                  }
                  placeholder="16.0"
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-ocean-muted mb-1">
                  Max Longitude
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="-180"
                  max="180"
                  value={form.bbox_max_lon ?? ""}
                  onChange={(e) =>
                    updateField(
                      "bbox_max_lon",
                      e.target.value ? parseFloat(e.target.value) : undefined,
                    )
                  }
                  placeholder="69.0"
                  className="w-full px-3 py-2.5 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue"
                />
              </div>
            </div>
          </div>

          {/* Error display */}
          {error && (
            <div className="card px-5 py-3 bg-red-50 border-red-200 text-sm text-red-700">
              {error}
              {requestId && (
                <p className="text-xs text-red-400 font-mono mt-1">
                  Request ID: {requestId}
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3">
            <Link href="/" className="btn-secondary">
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting || !form.title.trim()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <div className="spinner" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Create Investigation
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
