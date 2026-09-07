"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Layers, Info } from "lucide-react";
import type { MapLayerInfo } from "@/lib/api";
import { layerStateMeta } from "@/lib/api";

const CATEGORY_ORDER = [
  "Context",
  "Satellite",
  "Detection",
  "Drift",
  "Environment",
  "Vessels",
];

interface MapLayerPanelProps {
  layers: MapLayerInfo[];
  visibility: Record<string, boolean>;
  onToggle: (id: string) => void;
  opacities: Record<string, number>;
  onOpacity: (id: string, value: number) => void;
  selectedId: string | null;
  onSelectLayer: (id: string) => void;
  loading: boolean;
  error: string | null;
  /** Opens the data-registration flow for a genuine Sentinel-1 raster. */
  onRegisterSar?: () => void;
}

function LegendSwatch({ item }: { item: { color: string; dash?: number[]; fill?: string } }) {
  if (item.fill) {
    return (
      <span
        aria-hidden
        className="inline-block w-4 h-3 rounded-sm border border-ocean-border shrink-0"
        style={{ backgroundColor: item.fill }}
      />
    );
  }
  if (item.dash && item.dash.length > 0) {
    return (
      <span aria-hidden className="inline-block w-4 h-0.5 shrink-0 my-auto">
        <svg width="16" height="3" viewBox="0 0 16 3">
          <line x1="0" y1="1.5" x2="16" y2="1.5" stroke={item.color} strokeWidth="2" strokeDasharray="3 2" />
        </svg>
      </span>
    );
  }
  return (
    <span
      aria-hidden
      className="inline-block w-4 h-0.5 shrink-0 my-auto"
      style={{ backgroundColor: item.color, height: 2.5 }}
    />
  );
}

function LayerRow({
  layer,
  visible,
  onToggle,
  opacity,
  onOpacity,
  isSelected,
  onSelectLayer,
}: {
  layer: MapLayerInfo;
  visible: boolean;
  onToggle: () => void;
  opacity: number;
  onOpacity: (value: number) => void;
  isSelected: boolean;
  onSelectLayer: () => void;
}) {
  const state = layerStateMeta(layer.state);
  const canShow = layer.state === "ready";
  const firstItem = layer.legend?.items?.[0];
  const isRaster = layer.kind === "raster";

  return (
    <div
      className={`px-3 py-2 rounded-lg transition-colors ${
        isSelected ? "bg-ocean-teal/10 ring-1 ring-ocean-teal/30" : ""
      }`}
    >
      <div className="flex items-center gap-2.5">
        {/* Visibility toggle (only meaningful for layers with real data) */}
        <button
          type="button"
          disabled={!canShow}
          onClick={onToggle}
          aria-pressed={visible}
          aria-label={`${canShow ? "Show or hide" : "Layer unavailable"} ${layer.name}`}
          title={
            canShow
              ? visible
                ? "Hide layer"
                : "Show layer"
              : layer.reason || state.label
          }
          className={`relative w-8 h-8 shrink-0 rounded-md border transition-colors flex items-center justify-center disabled:cursor-not-allowed ${
            visible && canShow
              ? "bg-ocean-blue border-ocean-blue text-white"
              : canShow
                ? "bg-white border-ocean-border text-ocean-muted hover:border-ocean-blue"
                : "bg-ocean-ice border-ocean-border text-ocean-border"
          }`}
        >
          <span
            aria-hidden
            className={`w-3.5 h-3.5 rounded-sm border ${
              canShow ? "border-current" : "border-ocean-border bg-white"
            }`}
            style={
              visible && canShow
                ? { backgroundColor: "#22D3EE" }
                : canShow
                  ? {}
                  : { backgroundColor: "#E2E8F0" }
            }
          />
        </button>

        {/* Layer body */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`text-xs font-medium truncate ${
                isSelected ? "text-ocean-teal" : "text-ocean-slate"
              }`}
            >
              {layer.name}
            </span>
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${state.dot} ${
                layer.state === "processing" ? "animate-pulse" : ""
              }`}
              title={state.label}
            />
          </div>
          {canShow ? (
            <div className="flex items-center gap-1.5 mt-1">
              {firstItem && <LegendSwatch item={firstItem} />}
              <span className="text-[10px] text-ocean-muted truncate">
                {firstItem?.label || state.label}
              </span>
              <span className="ml-auto text-[10px] text-ocean-muted font-mono shrink-0">
                {layer.crs}
              </span>
            </div>
          ) : (
            <p className="text-[10px] text-ocean-muted leading-snug mt-0.5">
              {layer.reason || state.label}
            </p>
          )}
        </div>

        {/* Opacity for raster layers */}
        {isRaster && canShow && (
          <input
            type="range"
            min={0.05}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(e) => onOpacity(Number(e.target.value))}
            className="w-14 shrink-0 accent-ocean-teal"
            aria-label={`${layer.name} opacity`}
          />
        )}

        {/* Select for vector layers */}
        {canShow && layer.selectable && (
          <button
            type="button"
            onClick={onSelectLayer}
            aria-label={`Inspect ${layer.name}`}
            className={`p-1.5 rounded-md shrink-0 transition-colors ${
              isSelected
                ? "text-ocean-teal bg-ocean-teal/15"
                : "text-ocean-muted hover:bg-ocean-ice"
            }`}
            title="Inspect layer in evidence panel"
          >
            <Info className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function MapLayerPanel({
  layers,
  visibility,
  onToggle,
  opacities,
  onOpacity,
  selectedId,
  onSelectLayer,
  loading,
  error,
  onRegisterSar,
}: MapLayerPanelProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const readyCount = layers.filter((l) => l.state === "ready").length;

  const grouped = CATEGORY_ORDER.map((category) => ({
    category,
    items: layers.filter((l) => l.category === category),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-2 border-b border-ocean-border">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-ocean-blue" />
          <h2 className="text-sm font-semibold text-ocean-midnight">Map Layers</h2>
          <span className="ml-auto chip chip-default text-[10px]">
            {readyCount} ready
          </span>
        </div>
        <p className="text-[11px] text-ocean-muted mt-1 leading-snug">
          Only layers backed by real registered data are shown as ready.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {loading && (
          <p className="text-xs text-ocean-muted px-1 py-6 text-center">
            Loading layer metadata…
          </p>
        )}
        {error && (
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            {error}
          </div>
        )}
        {!loading && !error && grouped.length === 0 && (
          <p className="text-xs text-ocean-muted px-1 py-6 text-center">
            No map layers available for this case.
          </p>
        )}
        {!loading &&
          grouped.map((group) => {
            const isCollapsed = collapsed[group.category];
            // Honest SAR source empty state: a context basemap is never SAR.
            const sarLayer = group.items.find((l) => l.id === "sar_raster");
            const showSarNotice =
              group.category === "Satellite" &&
              sarLayer?.state === "missing_input" &&
              onRegisterSar;
            return (
              <div key={group.category}>
                <button
                  type="button"
                  onClick={() =>
                    setCollapsed((prev) => ({
                      ...prev,
                      [group.category]: !prev[group.category],
                    }))
                  }
                  aria-expanded={!isCollapsed}
                  className="w-full flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ocean-muted hover:text-ocean-slate py-1"
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-3 h-3" />
                  ) : (
                    <ChevronDown className="w-3 h-3" />
                  )}
                  {group.category}
                  <span className="text-[10px] font-normal normal-case text-ocean-border">
                    {group.items.filter((i) => i.state === "ready").length}/
                    {group.items.length}
                  </span>
                </button>
                {!isCollapsed && (
                  <div className="space-y-0.5 mt-1">
                    {group.items.map((layer) => (
                      <LayerRow
                        key={layer.id}
                        layer={layer}
                        visible={Boolean(visibility[layer.id])}
                        onToggle={() => onToggle(layer.id)}
                        opacity={opacities[layer.id] ?? layer.opacity_default ?? 1}
                        onOpacity={(value) => onOpacity(layer.id, value)}
                        isSelected={selectedId === layer.id}
                        onSelectLayer={() => onSelectLayer(layer.id)}
                      />
                    ))}
                    {showSarNotice && (
                      <div className="mt-2 px-3 py-3 bg-ocean-ice border border-dashed border-ocean-blue/40 rounded-lg">
                        <p className="text-xs font-semibold text-ocean-midnight">
                          Sentinel-1 SAR source not registered
                        </p>
                        <p className="text-[11px] text-ocean-muted mt-1 leading-snug">
                          Register an authentic georeferenced Sentinel-1 raster
                          to create an analytical overlay.
                        </p>
                        <button
                          type="button"
                          onClick={onRegisterSar}
                          className="mt-2 btn-secondary text-[11px] px-2.5 py-1.5"
                        >
                          Register SAR File
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
