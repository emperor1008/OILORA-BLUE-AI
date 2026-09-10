"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  GeoJSONFeatureCollection,
  GeoJSONBounds,
} from "@/lib/geojson";
import type { MapViewport, SarOverlay } from "@/lib/api";

// MapLibre CSS is bundled once by webpack; the maplibre-gl JS module itself is
// only loaded lazily after a WebGL capability check (never during SSR/jsdom).
import "maplibre-gl/dist/maplibre-gl.css";
import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

export type BasemapId = "ocean" | "satellite" | "minimal";

// NASA Global Imagery Browse Services (GIBS) — public, keyless, attribution-
// compliant WMTS tiles. Blue Marble Next Generation is a static 2004 monthly
// cloud-free composite suitable for general Earth-observation context.
// Documented endpoint: https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/
// TMS `GoogleMapsCompatible_Level8` serves zoom levels 0-8.
const SATELLITE_DEFAULT_URL =
  "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/2004-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg";
const SATELLITE_DEFAULT_ATTRIBUTION =
  "Imagery © NASA / GIBS — Blue Marble Next Generation";
const SATELLITE_MAX_ZOOM = 8;

// Maximum useful zoom per basemap (used for the "maximum imagery resolution
// reached" notice instead of stretching tiles deceptively).
export const BASEMAP_MAX_ZOOM: Record<BasemapId, number> = {
  ocean: 19,
  satellite: SATELLITE_MAX_ZOOM,
  minimal: 18,
};

/**
 * Resolve a basemap to its tile URL / attribution / background. Exporting this
 * pure function keeps the behaviour unit-testable (e.g. "minimal makes no
 * external tile request", "satellite resolves to the GIBS source").
 */
export function resolveBasemap(
  id: BasemapId,
  isOffline: boolean,
): { url: string | null; attribution: string; background: string; maxZoom: number } {
  if (isOffline || id === "minimal") {
    return {
      url: null,
      attribution: "",
      background: "#0B2A3D",
      maxZoom: BASEMAP_MAX_ZOOM.minimal,
    };
  }
  if (id === "satellite") {
    return {
      url: process.env.NEXT_PUBLIC_SATELLITE_TILES || SATELLITE_DEFAULT_URL,
      attribution:
        process.env.NEXT_PUBLIC_SATELLITE_ATTRIBUTION ||
        SATELLITE_DEFAULT_ATTRIBUTION,
      background: "#071E2E",
      maxZoom: SATELLITE_MAX_ZOOM,
    };
  }
  return {
    url:
      process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL ||
      "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    attribution: OCEAN_ATTRIBUTION,
    background: "#CBDDE5",
    maxZoom: BASEMAP_MAX_ZOOM.ocean,
  };
}

export interface VectorLayerView {
  id: string;
  name: string;
  features: GeoJSONFeatureCollection;
}

export interface MaritimeMapApi {
  fitToCase: () => void;
  resetNorth: () => void;
}

interface MaritimeMapProps {
  bounds: GeoJSONBounds | null;
  vectorLayers: VectorLayerView[];
  sarOverlay: SarOverlay | null;
  showSar: boolean;
  sarOpacity: number;
  basemapId: BasemapId;
  initialViewport: MapViewport | null;
  selectedId: string | null;
  onSelect?: (layerId: string) => void;
  onViewportChange?: (viewport: MapViewport) => void;
  onExportGeojson?: (layerId: string) => void;
  onApi?: (api: MaritimeMapApi) => void;
  /** Fired when the active basemap reports tile/source failures. */
  onBasemapError?: (id: BasemapId) => void;
  isOffline?: boolean;
}

const OCEAN_ATTRIBUTION = "© OpenStreetMap contributors © CARTO";

/** True when a WebGL rendering context can be created in this browser. */
function webglSupported(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    return gl !== null && gl !== undefined;
  } catch {
    return false;
  }
}

const NEUTRAL_CENTER: [number, number] = [71.0, 19.0]; // Arabian Sea overview

// Source/layer ids on the map are stable and prefixed to avoid collisions.
function layerIds(id: string) {
  return { source: `src-${id}`, fill: `fill-${id}`, line: `line-${id}` };
}

interface StyleRule {
  lineColor: string;
  lineWidth: number;
  lineDash: number[];
  fill?: string;
  fillOpacity: number;
}

// Visual rules mirror the backend legend palette (single maritime palette).
const STYLE_RULES: Record<string, StyleRule> = {
  investigation_area: {
    lineColor: "#0E7490",
    lineWidth: 2,
    lineDash: [4, 3],
    fill: "#0E7490",
    fillOpacity: 0.06,
  },
  case_boundary_dataset: {
    lineColor: "#0B2A3D",
    lineWidth: 1.5,
    lineDash: [],
    fill: "#0B2A3D",
    fillOpacity: 0.05,
  },
  detection_predicted: {
    lineColor: "#F59E0B",
    lineWidth: 2,
    lineDash: [5, 4],
    fill: "#F59E0B",
    fillOpacity: 0.12,
  },
  detection_reviewed: {
    lineColor: "#EF5B5B",
    lineWidth: 2.5,
    lineDash: [],
    fill: "#EF5B5B",
    fillOpacity: 0.15,
  },
  detection_ground_truth: {
    lineColor: "#10B981",
    lineWidth: 1.5,
    lineDash: [2, 2],
    fill: "#10B981",
    fillOpacity: 0.08,
  },
  drift_backward_contour_50: {
    lineColor: "#0B2A3D",
    lineWidth: 2.5,
    lineDash: [],
    fill: "#0B2A3D",
    fillOpacity: 0.05,
  },
  drift_backward_contour_75: {
    lineColor: "#0E7490",
    lineWidth: 2,
    lineDash: [],
    fill: "#0E7490",
    fillOpacity: 0.06,
  },
  drift_backward_contour_90: {
    lineColor: "#22D3EE",
    lineWidth: 1.5,
    lineDash: [],
    fill: "#22D3EE",
    fillOpacity: 0.08,
  },
  drift_forward_contours: {
    lineColor: "#0891B2",
    lineWidth: 1.5,
    lineDash: [3, 3],
    fill: "#0891B2",
    fillOpacity: 0.08,
  },
  drift_coastline_contact: {
    lineColor: "#EF5B5B",
    lineWidth: 2,
    lineDash: [6, 3],
    fill: "#EF5B5B",
    fillOpacity: 0.1,
  },
  ais_tracks: {
    lineColor: "#94A3B8",
    lineWidth: 1.5,
    lineDash: [],
    fill: "#94A3B8",
    fillOpacity: 0,
  },
  ais_candidate_tracks: {
    lineColor: "#0891B2",
    lineWidth: 2,
    lineDash: [],
    fill: "#0891B2",
    fillOpacity: 0,
  },
  ais_gap_segments: {
    lineColor: "#F59E0B",
    lineWidth: 1.5,
    lineDash: [2, 2],
    fill: "#F59E0B",
    fillOpacity: 0,
  },
};

const SELECTED_COLOR = "#EF5B5B";

function WebGLFallback({
  vectorLayers,
  bounds,
  onExportGeojson,
}: {
  vectorLayers: VectorLayerView[];
  bounds: GeoJSONBounds | null;
  onExportGeojson?: (layerId: string) => void;
}) {
  return (
    <div
      className="h-full w-full overflow-y-auto bg-ocean-ice p-6"
      role="status"
      aria-label="Interactive map unavailable"
    >
      <div className="max-w-2xl mx-auto">
        <h3 className="text-sm font-semibold text-ocean-midnight mb-1">
          Interactive map unavailable in this browser
        </h3>
        <p className="text-xs text-ocean-muted mb-4">
          WebGL rendering is not available here, so the live map cannot start.
          Geographic data for this investigation is listed below and remains
          available for export.
        </p>
        {bounds && (
          <p className="text-xs font-mono text-ocean-muted mb-4">
            Bounds: {bounds.min_lat.toFixed(3)}°–{bounds.max_lat.toFixed(3)}° N,{" "}
            {bounds.min_lon.toFixed(3)}°–{bounds.max_lon.toFixed(3)}° E
          </p>
        )}
        {vectorLayers.length === 0 ? (
          <p className="text-sm text-ocean-muted">
            No geospatial evidence registered — register a real SAR,
            environmental or AIS file to see data here.
          </p>
        ) : (
          <ul className="space-y-2">
            {vectorLayers.map((layer) => (
              <li
                key={layer.id}
                className="flex items-center justify-between gap-3 px-4 py-3 bg-white border border-ocean-border rounded-lg"
              >
                <span className="text-sm font-medium text-ocean-slate">
                  {layer.name}
                </span>
                <span className="text-xs text-ocean-muted">
                  {layer.features.features.length} feature
                  {layer.features.features.length === 1 ? "" : "s"}
                </span>
                {onExportGeojson && (
                  <button
                    onClick={() => onExportGeojson(layer.id)}
                    className="btn-secondary text-xs px-3 py-1.5"
                  >
                    Export GeoJSON
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function MaritimeMap({
  bounds,
  vectorLayers,
  sarOverlay,
  showSar,
  sarOpacity,
  basemapId,
  initialViewport,
  selectedId,
  onSelect,
  onViewportChange,
  onExportGeojson,
  onApi,
  onBasemapError,
  isOffline = false,
}: MaritimeMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<{ map: unknown; setData: () => void } | null>(null);
  const vectorLayerRef = useRef<string[]>([]);
  const [supported] = useState<boolean>(() => webglSupported());
  const [styleLoaded, setStyleLoaded] = useState(false);
  const [zoom, setZoom] = useState<number | null>(null);
  const base = useMemo(() => resolveBasemap(basemapId, isOffline), [basemapId, isOffline]);

  // ── Initialise MapLibre once (client only, after WebGL capability check) ──
  useEffect(() => {
    if (!supported || !containerRef.current) return;
    let disposed = false;
    let maplibregl: typeof import("maplibre-gl") | null = null;
    // A basemap switch removes and recreates the map; until the fresh map
    // fires `load`, dependent effects must not touch the (unloaded) style.
    setStyleLoaded(false);

    (async () => {
      try {
        maplibregl = await import("maplibre-gl");
      } catch {
        return;
      }
      if (disposed || !containerRef.current || !maplibregl) return;

      // Consecutive basemap tile errors before surfacing a notice. A single
      // transient MapLibre error (e.g. one retried tile) must not alarm the
      // analyst; only a genuinely failing provider reaches the threshold.
      let basemapErrorCount = 0;

      const baseLayers: LayerSpecification[] = [
        {
          id: "background",
          type: "background",
          paint: { "background-color": base.background },
        },
      ];
      if (base.url) {
        baseLayers.push({
          id: "basemap-raster",
          type: "raster",
          source: "basemap",
          paint: { "raster-opacity": 1 },
        });
      }
      const styleSpec: StyleSpecification = {
        version: 8,
        sources: base.url
          ? ({
              basemap: {
                type: "raster",
                tiles: [base.url],
                tileSize: 256,
                attribution: base.attribution,
                maxzoom: base.maxZoom,
              },
            } as StyleSpecification["sources"])
          : {},
        layers: baseLayers,
      };

      // Guard against a corrupted/invalid persisted viewport (NaN or out-of-
      // range values) so the map always starts at a usable position.
      const savedViewport =
        initialViewport &&
        Number.isFinite(initialViewport.center_lon) &&
        Number.isFinite(initialViewport.center_lat) &&
        Number.isFinite(initialViewport.zoom) &&
        initialViewport.center_lon >= -180 &&
        initialViewport.center_lon <= 180 &&
        initialViewport.center_lat >= -90 &&
        initialViewport.center_lat <= 90
          ? initialViewport
          : null;

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: styleSpec,
        center: savedViewport
          ? [savedViewport.center_lon, savedViewport.center_lat]
          : NEUTRAL_CENTER,
        zoom: savedViewport ? savedViewport.zoom : 3.8,
        bearing: savedViewport?.bearing ?? 0,
        pitch: savedViewport?.pitch ?? 0,
        maxZoom: 18,
      });

      const trackViewport = () => {
        if (!map) return;
        const center = map.getCenter();
        onViewportChange?.({
          center_lon: Number(center.lng.toFixed(6)),
          center_lat: Number(center.lat.toFixed(6)),
          zoom: Number(map.getZoom().toFixed(3)),
          bearing: Number(map.getBearing().toFixed(1)),
          pitch: Number(map.getPitch().toFixed(1)),
        });
      };
      let debounceTimer: ReturnType<typeof setTimeout> | null = null;
      const syncZoom = () => setZoom(map.getZoom());
      map.on("zoom", syncZoom);
      map.on("load", syncZoom);
      map.on("moveend", () => {
        syncZoom();
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(trackViewport, 400);
      });
      map.on("click", (event) => {
        const interactive = (map.queryRenderedFeatures(event.point, {
          layers: vectorLayerRef.current,
        }) as Array<{ layer: { id: string } }>)[0];
        if (interactive) {
          onSelect?.(interactive.layer.id.replace(/^(fill|line|src)-/, ""));
        }
      });
      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
      try {
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
      } catch {
        // Scale control is optional
      }

      map.on("load", () => {
        if (disposed) return;
        if (bounds && !initialViewport) {
          map.fitBounds(
            [
              [bounds.min_lon, bounds.min_lat],
              [bounds.max_lon, bounds.max_lat],
            ],
            { padding: 60, maxZoom: 13 },
          );
        }
        const fitToCase = () => {
          if (bounds) {
            map.fitBounds(
              [
                [bounds.min_lon, bounds.min_lat],
                [bounds.max_lon, bounds.max_lat],
              ],
              { padding: 60, maxZoom: 13 },
            );
          } else {
            map.jumpTo({ center: NEUTRAL_CENTER, zoom: 3.8 });
          }
        };
        const resetNorth = () => map.resetNorth();
        onApi?.({ fitToCase, resetNorth });
        setStyleLoaded(true);
      });
      map.on("error", (event) => {
        // Surface basemap tile/source failures honestly (e.g. satellite
        // service unreachable) instead of silently blanking the map. Only
        // the active external basemap is reported; analysis layers are
        // independent and remain usable.
        const err = event as unknown as {
          sourceId?: string;
          error?: { message?: string };
        };
        if (basemapId !== "minimal" && !isOffline) {
          const isBasemap = !err.sourceId || err.sourceId === "basemap";
          if (isBasemap) {
            basemapErrorCount += 1;
            if (basemapErrorCount >= 3) {
              onBasemapError?.(basemapId);
            }
          }
        }
      });

      mapRef.current = { map, setData: () => {} };
    })();

    return () => {
      disposed = true;
      const entry = mapRef.current;
      mapRef.current = null;
      if (entry) {
        try {
          (entry.map as { remove: () => void }).remove();
        } catch {
          // already removed
        }
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported, base.url, base.background, base.attribution, bounds, initialViewport]);

  // Reference to currently visible interactive layers for click queries.
  useEffect(() => {
    vectorLayerRef.current = vectorLayers.flatMap((layer) => {
      const ids = layerIds(layer.id);
      return [ids.fill, ids.line].filter((id) => Boolean(id));
    });
  }, [vectorLayers]);

  // ── Render/unrender visible vector layers (stable ids, diffed updates) ──
  useEffect(() => {
    if (!styleLoaded || !mapRef.current) return;
    const map = mapRef.current.map as {
      getSource: (id: string) => unknown;
      addSource: (id: string, def: unknown) => void;
      removeSource: (id: string) => void;
      addLayer: (def: unknown) => void;
      removeLayer: (id: string) => void;
      moveLayer: (id: string, before?: string) => void;
      getLayer: (id: string) => unknown;
    };
    const visible = new Set(vectorLayers.map((layer) => layer.id));

    for (const layer of vectorLayers) {
      const { source, fill, line } = layerIds(layer.id);
      const rule = STYLE_RULES[layer.id] || {
        lineColor: "#0E7490",
        lineWidth: 1.5,
        lineDash: [],
        fill: "#0E7490",
        fillOpacity: 0.1,
      };
      if (!map.getSource(source)) {
        map.addSource(source, {
          type: "geojson",
          data: layer.features,
        } as unknown);
        if (rule.fillOpacity > 0 && rule.fill) {
          map.addLayer({
            id: fill,
            type: "fill",
            source,
            paint: {
              "fill-color": rule.fill,
              "fill-opacity": rule.fillOpacity,
            },
          } as unknown);
        }
        map.addLayer({
          id: line,
          type: "line",
          source,
          paint: {
            "line-color": rule.lineColor,
            "line-width": rule.lineWidth,
            "line-dasharray": rule.lineDash.length > 0 ? rule.lineDash : undefined,
          },
        } as unknown);
        // Keep scientific layers above the basemap raster.
        try {
          map.moveLayer(line, "basemap-raster");
          if (fill && rule.fillOpacity > 0) map.moveLayer(fill, "basemap-raster");
        } catch {
          // moving is best-effort
        }
      }
    }
    // Remove sources/layers that became invisible (toggles off).
    for (const candidate of Object.keys(STYLE_RULES)) {
      const { source, fill, line } = layerIds(candidate);
      if (map.getSource(source) && !visible.has(candidate)) {
        try {
          map.removeLayer(fill);
        } catch {
          // fill may not exist for line-only layers
        }
        try {
          map.removeLayer(line);
        } catch {
          // already removed
        }
        try {
          map.removeSource(source);
        } catch {
          // already removed
        }
      }
    }
  }, [vectorLayers, styleLoaded]);

  // ── Selection emphasis ─────────────────────────────────────────────
  useEffect(() => {
    if (!styleLoaded || !mapRef.current) return;
    const map = mapRef.current.map as {
      getLayer: (id: string) => unknown;
      setPaintProperty: (id: string, prop: string, value: unknown) => void;
    };
    for (const layer of vectorLayers) {
      const { line } = layerIds(layer.id);
      if (!map.getLayer(line)) continue;
      const rule = STYLE_RULES[layer.id];
      const isSelected = layer.id === selectedId;
      map.setPaintProperty(line, "line-color", isSelected ? SELECTED_COLOR : rule.lineColor);
      map.setPaintProperty(
        line,
        "line-width",
        isSelected ? rule.lineWidth + 1.5 : rule.lineWidth,
      );
    }
  }, [vectorLayers, selectedId, styleLoaded]);

  // ── SAR grayscale preview overlay ──────────────────────────────────
  useEffect(() => {
    if (!styleLoaded || !mapRef.current) return;
    const map = mapRef.current.map as {
      getSource: (id: string) => unknown;
      addSource: (id: string, def: unknown) => void;
      removeSource: (id: string) => void;
      getLayer: (id: string) => unknown;
      addLayer: (def: unknown) => void;
      removeLayer: (id: string) => void;
      setPaintProperty: (id: string, prop: string, value: unknown) => void;
    };
    const active =
      showSar && sarOverlay?.available && sarOverlay.url && sarOverlay.bounds;
    if (!active) {
      try {
        map.removeLayer("sar-raster");
        map.removeSource("src-sar");
      } catch {
        // nothing to remove
      }
      return;
    }
    const [w, s, e, n] = sarOverlay.bounds as [number, number, number, number];
    const url = sarOverlay.url as string;
    if (!map.getSource("src-sar")) {
      map.addSource("src-sar", {
        type: "image",
        url,
        coordinates: [
          [w, s],
          [e, s],
          [e, n],
          [w, n],
        ],
      } as unknown);
    }
    if (!map.getLayer("sar-raster")) {
      map.addLayer({
        id: "sar-raster",
        type: "raster",
        source: "src-sar",
        paint: { "raster-opacity": sarOpacity },
        layout: { visibility: "visible" },
      } as unknown);
    }
    map.setPaintProperty("sar-raster", "raster-opacity", sarOpacity);
  }, [showSar, sarOverlay, sarOpacity, styleLoaded]);

  if (!supported) {
    return (
      <WebGLFallback
        vectorLayers={vectorLayers}
        bounds={bounds}
        onExportGeojson={onExportGeojson}
      />
    );
  }

  const beyondMaxZoom =
    zoom !== null && base.maxZoom > 0 && zoom > base.maxZoom;

  return (
    <div
      ref={containerRef}
      className="h-full w-full relative"
      data-testid="maritime-map"
      aria-label="Maritime intelligence map"
      role="region"
    >
      {beyondMaxZoom && base.url && (
        <div className="absolute bottom-9 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
          <div className="bg-ocean-midnight/85 text-white text-[10px] px-3 py-1.5 rounded-md border border-ocean-teal/40 shadow-card">
            Maximum imagery resolution reached — switch to Ocean / Street for
            closer detail.
          </div>
        </div>
      )}
    </div>
  );
}
