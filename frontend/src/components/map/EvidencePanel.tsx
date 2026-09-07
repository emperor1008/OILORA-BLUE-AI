"use client";

import { useState } from "react";
import {
  X,
  FileSearch,
  Database,
  ShieldCheck,
  Layers,
  Download,
  FileDigit,
} from "lucide-react";
import {
  MapSummary,
  MapLayerInfo,
  MapProvenance,
  MapLayerFeatureState,
  formatCoord,
  formatUtc,
  formatFileSize,
  layerStateMeta,
} from "@/lib/api";

interface EvidencePanelProps {
  summary: MapSummary | null;
  selectedLayer: MapLayerInfo | null;
  layerFeatures: Record<string, MapLayerFeatureState>;
  provenance: MapProvenance | null;
  /** Desktop: deselect the current layer (panel stays visible). */
  onClose?: () => void;
  /** Small screens: close the drawer itself (panel is a modal overlay). */
  onCloseDrawer?: () => void;
  onExportGeojson?: (layerId: string) => void;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <span className="text-xs text-ocean-muted shrink-0">{label}</span>
      <span className="text-xs text-ocean-slate text-right font-mono break-all">
        {value}
      </span>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ocean-muted mb-2">
      {children}
    </h3>
  );
}

function Overview({
  summary,
}: {
  summary: MapSummary;
}) {
  const readyNames = summary.available_layer_ids.length;
  const reasons = summary.missing_data.slice(0, 5);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileSearch className="w-4 h-4 text-ocean-blue" />
        <h2 className="text-sm font-semibold text-ocean-midnight">Evidence</h2>
      </div>

      {!summary.has_geospatial_data && (
        <div className="px-3 py-3 rounded-lg border border-dashed border-ocean-border bg-ocean-ice">
          <p className="text-xs font-medium text-ocean-slate">
            No geospatial case data registered
          </p>
          <p className="text-[11px] text-ocean-muted mt-1 leading-snug">
            Register a genuine SAR, environmental or AIS file (or set case
            bounds) to populate the map. Nothing is simulated.
          </p>
        </div>
      )}

      <div className="card px-4 py-3">
        <SectionTitle>Map Readiness</SectionTitle>
        <div className="divide-y divide-ocean-border/60">
          <Field label="Geospatial data" value={summary.has_geospatial_data ? "Present" : "None"} />
          <Field label="Data integrity" value={summary.data_integrity.toUpperCase()} />
          <Field label="Ready layers" value={`${readyNames} of ${summary.available_layer_ids.length + summary.unavailable_layer_ids.length}`} />
          <Field
            label="Bounds"
            value={
              summary.bounds
                ? `${formatCoord(summary.bounds.min_lat, 3)}–${formatCoord(
                    summary.bounds.max_lat,
                    3,
                  )}°N, ${formatCoord(summary.bounds.min_lon, 3)}–${formatCoord(
                    summary.bounds.max_lon,
                    3,
                  )}°E`
                : "Not available"
            }
          />
          <Field
            label="Time range"
            value={
              summary.time_range
                ? `${formatUtc(summary.time_range.start)} → ${formatUtc(
                    summary.time_range.end,
                  )}`
                : "Not available"
            }
          />
          {Object.entries(summary.registered_files).length > 0 && (
            <Field
              label="Registered datasets"
              value={Object.entries(summary.registered_files)
                .map(([type, count]) => `${type}: ${count}`)
                .join(" · ")}
            />
          )}
        </div>
      </div>

      {reasons.length > 0 && (
        <div className="card px-4 py-3">
          <SectionTitle>Why Layers Are Unavailable</SectionTitle>
          <ul className="space-y-1.5">
            {reasons.map((reason) => (
              <li key={reason} className="flex items-start gap-2 text-[11px] text-ocean-muted">
                <span aria-hidden className="w-1.5 h-1.5 rounded-full bg-ocean-border mt-1 shrink-0" />
                <span>{reason}</span>
              </li>
            ))}
            {summary.missing_data.length > reasons.length && (
              <li className="text-[11px] text-ocean-border">
                +{summary.missing_data.length - reasons.length} more
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function SelectionDetails({
  layer,
  featureState,
  onExportGeojson,
}: {
  layer: MapLayerInfo;
  featureState: MapLayerFeatureState | undefined;
  onExportGeojson?: (layerId: string) => void;
}) {
  const state = layerStateMeta(layer.state);
  const count = featureState?.features?.features.length ?? 0;
  const source =
    layer.id === "investigation_area"
      ? "Case bounding box (SQLite)"
      : layer.id === "case_boundary_dataset"
        ? "Registered GeoJSON boundary file"
        : "Not available";

  const firstFeature = featureState?.features?.features[0];
  const geometryType = firstFeature?.geometry?.type || null;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-ocean-teal" />
          <h2 className="text-sm font-semibold text-ocean-midnight">
            {layer.name}
          </h2>
        </div>
        <p className="text-[11px] text-ocean-muted mt-0.5">
          {layer.category} · {layer.crs}
        </p>
      </div>

      <div className="card px-4 py-3">
        <SectionTitle>Layer Details</SectionTitle>
        <div className="divide-y divide-ocean-border/60">
          <Field label="Status" value={state.label} />
          <Field label="Source dataset" value={source} />
          <Field label="Features" value={String(count)} />
          <Field
            label="Geometry"
            value={geometryType || "Not available"}
          />
          <Field
            label="Observation time"
            value={
              layer.timestamps?.start
                ? formatUtc(layer.timestamps.start)
                : "Not available"
            }
          />
          <Field
            label="Source attribution"
            value={
              layer.legend?.title
                ? layer.legend.title
                : "Not available"
            }
          />
        </div>
      </div>

      {onExportGeojson && layer.exportable && featureState?.features && (
        <button
          type="button"
          onClick={() => onExportGeojson(layer.id)}
          className="btn-secondary w-full text-xs"
        >
          <Download className="w-3.5 h-3.5" />
          Export GeoJSON
        </button>
      )}
    </div>
  );
}

function ProvenanceView({ provenance }: { provenance: MapProvenance }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Database className="w-4 h-4 text-ocean-blue" />
        <h2 className="text-sm font-semibold text-ocean-midnight">Provenance</h2>
      </div>

      <div className="card px-4 py-3">
        <SectionTitle>
          Source Datasets ({provenance.sources.length})
        </SectionTitle>
        {provenance.sources.length === 0 ? (
          <p className="text-[11px] text-ocean-muted">
            No datasets have been registered for this case.
          </p>
        ) : (
          <ul className="space-y-3">
            {provenance.sources.map((source) => (
              <li key={source.file_id} className="space-y-1">
                <div className="flex items-center gap-2">
                  <FileDigit className="w-3.5 h-3.5 text-ocean-muted shrink-0" />
                  <p className="text-xs font-medium text-ocean-slate truncate">
                    {source.original_filename}
                  </p>
                </div>
                <div className="pl-6 space-y-0.5">
                  <Field label="Type" value={source.file_type} />
                  <Field label="Size" value={formatFileSize(source.file_size)} />
                  <Field
                    label="Registered"
                    value={formatUtc(source.registered_at)}
                  />
                </div>
                <p className="pl-6 text-[10px] font-mono text-ocean-muted break-all">
                  SHA-256 {source.sha256_checksum}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card px-4 py-3">
        <SectionTitle>
          Derived Artifacts ({provenance.derived_artifacts.length})
        </SectionTitle>
        {provenance.derived_artifacts.length === 0 ? (
          <p className="text-[11px] text-ocean-muted">
            No derived artifacts have been generated yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {provenance.derived_artifacts.map((artifact, index) => (
              <li key={`${artifact.file_id}-${index}`} className="space-y-1">
                <p className="text-xs font-medium text-ocean-slate">
                  {artifact.artifact.replace(/_/g, " ")}
                </p>
                <div className="pl-1 space-y-0.5">
                  <Field
                    label="Source"
                    value={artifact.source_filename || "Not available"}
                  />
                  <Field
                    label="Generated"
                    value={formatUtc(artifact.generated_at)}
                  />
                  <Field
                    label="Dimensions"
                    value={
                      artifact.width && artifact.height
                        ? `${artifact.width} × ${artifact.height} px`
                        : "Not available"
                    }
                  />
                </div>
                <p className="text-[10px] font-mono text-ocean-muted break-all">
                  SHA-256 {artifact.sha256_checksum || "Not available"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-[10px] text-ocean-muted leading-snug">
        {provenance.note}
      </p>
    </div>
  );
}

export default function EvidencePanel({
  summary,
  selectedLayer,
  layerFeatures,
  provenance,
  onClose,
  onCloseDrawer,
  onExportGeojson,
}: EvidencePanelProps) {
  const [tab, setTab] = useState<"overview" | "provenance">("overview");
  const activeLayer =
    selectedLayer && selectedLayer.state === "ready" ? selectedLayer : null;

  return (
    <div className="flex flex-col h-full min-h-0 bg-white">
      <div className="flex items-center gap-1 px-4 pt-4 pb-2 border-b border-ocean-border shrink-0">
        <button
          type="button"
          onClick={() => setTab("overview")}
          aria-pressed={tab === "overview"}
          className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
            tab === "overview"
              ? "bg-ocean-ice text-ocean-slate"
              : "text-ocean-muted hover:text-ocean-slate"
          }`}
        >
          Evidence
        </button>
        <button
          type="button"
          onClick={() => setTab("provenance")}
          aria-pressed={tab === "provenance"}
          className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
            tab === "provenance"
              ? "bg-ocean-ice text-ocean-slate"
              : "text-ocean-muted hover:text-ocean-slate"
          }`}
        >
          Provenance
        </button>
        <div className="flex-1" />
        <button
          type="button"
          onClick={onCloseDrawer}
          className="p-2 -mr-1 rounded-md text-ocean-muted hover:bg-ocean-ice xl:hidden"
          aria-label="Close evidence drawer"
          title="Close drawer"
        >
          <X className="w-4 h-4" />
        </button>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="hidden xl:inline-flex p-1.5 rounded-md text-ocean-muted hover:bg-ocean-ice"
            aria-label="Deselect layer"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        {tab === "provenance" ? (
          provenance ? (
            <ProvenanceView provenance={provenance} />
          ) : (
            <p className="text-xs text-ocean-muted">Loading provenance…</p>
          )
        ) : activeLayer ? (
          <SelectionDetails
            layer={activeLayer}
            featureState={
              layerFeatures[activeLayer.id] || undefined
            }
            onExportGeojson={onExportGeojson}
          />
        ) : summary ? (
          <Overview summary={summary} />
        ) : (
          <div className="py-10 text-center text-xs text-ocean-muted">
            <ShieldCheck className="w-8 h-8 mx-auto mb-2 text-ocean-border" />
            Loading evidence…
          </div>
        )}
      </div>
    </div>
  );
}
