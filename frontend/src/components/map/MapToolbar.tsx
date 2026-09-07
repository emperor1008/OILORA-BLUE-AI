"use client";

import { Layers, PanelRight, Database, Compass, Maximize2, Download } from "lucide-react";
import type { BasemapId } from "./MaritimeMap";

interface MapToolbarProps {
  basemapId: BasemapId;
  onBasemapChange: (id: BasemapId) => void;
  satelliteAvailable: boolean;
  onOpenLayers?: () => void;
  onOpenEvidence?: () => void;
  onOpenData?: () => void;
  onFitToCase?: () => void;
  onResetNorth?: () => void;
  onExportVisible?: () => void;
  canExport: boolean;
}

const BASEMAP_OPTIONS: { id: BasemapId; label: string }[] = [
  { id: "ocean", label: "Ocean / Street" },
  { id: "satellite", label: "Satellite Context" },
  { id: "minimal", label: "Minimal / Offline" },
];

// Kept separate so the distinction is explicit: optical context imagery is
// geographic reference only — it is never the Sentinel-1 SAR analytical input.
const SATELLITE_CONTEXT_TOOLTIP =
  "Optical satellite context for geographic reference. This layer is not the Sentinel-1 SAR image used for oil-spill analysis.";

export default function MapToolbar({
  basemapId,
  onBasemapChange,
  satelliteAvailable,
  onOpenLayers,
  onOpenEvidence,
  onOpenData,
  onFitToCase,
  onResetNorth,
  onExportVisible,
  canExport,
}: MapToolbarProps) {
  // 44x44 touch targets (mobile accessibility requirement).
  const toolbarButton =
    "w-11 h-11 rounded-lg bg-white border border-ocean-border text-ocean-muted hover:text-ocean-slate hover:border-ocean-blue shadow-card flex items-center justify-center transition-colors";

  return (
    <div className="absolute top-3 right-3 z-10 flex flex-col items-end gap-2">
      {/* Basemap selector */}
      <div className="bg-white border border-ocean-border rounded-lg shadow-card flex items-center overflow-hidden">
        {BASEMAP_OPTIONS.map((option) => {
          const disabled =
            option.id === "satellite" && !satelliteAvailable;
          return (
            <button
              key={option.id}
              type="button"
              disabled={disabled}
              onClick={() => onBasemapChange(option.id)}
              title={
                disabled
                  ? "Satellite context not configured (no legally usable tile source provided)."
                  : option.id === "satellite"
                    ? SATELLITE_CONTEXT_TOOLTIP
                    : `Switch to ${option.label} context`
              }
              aria-pressed={basemapId === option.id}
              className={`px-2.5 py-2 text-[11px] font-medium transition-colors border-r border-ocean-border last:border-r-0 ${
                basemapId === option.id
                  ? "bg-ocean-blue text-white"
                  : disabled
                    ? "text-ocean-border cursor-not-allowed bg-ocean-ice"
                    : "text-ocean-muted hover:text-ocean-slate"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {/* Context buttons */}
      <div className="flex items-center gap-1.5 flex-wrap justify-end">
        <button
          type="button"
          className={toolbarButton}
          onClick={onResetNorth}
          aria-label="Reset north orientation"
          title="Reset north"
        >
          <Compass className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={toolbarButton}
          onClick={onFitToCase}
          aria-label="Fit map to case bounds"
          title="Fit to case"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={toolbarButton}
          onClick={onExportVisible}
          disabled={!canExport}
          aria-label="Export GeoJSON"
          title={canExport ? "Export visible vector layers as GeoJSON" : "No exportable vector layers"}
        >
          <Download className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={`${toolbarButton} lg:hidden`}
          onClick={onOpenLayers}
          aria-label="Open layer panel"
        >
          <Layers className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={`${toolbarButton} xl:hidden`}
          onClick={onOpenEvidence}
          aria-label="Open evidence panel"
        >
          <PanelRight className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={`${toolbarButton} lg:hidden`}
          onClick={onOpenData}
          aria-label="Open data files panel"
        >
          <Database className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
