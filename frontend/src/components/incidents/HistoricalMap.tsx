"use client";

/**
 * Historical Incident Map
 *
 * A MapLibre map rendering source-registered historical incidents as clustered
 * points. Clicking a cluster expands toward it; clicking an incident point
 * selects it (parent syncs sidebar/URL/detail).
 *
 * The SSR-safe form announces a stable "hydrating" skeleton on both the server
 * and the first client render, then runs WebGL detection only inside a client
 * effect. Until WebGL support is known, the interactive map is never created and
 * the server HTML matches the client HTML exactly. MapLibre itself is imported
 * only inside the client-side init effect so its module initialisation never
 * touches the server runtime.
 *
 * Text labels require a glyphs endpoint, so they are only added when an
 * external basemap is active; Minimal/Offline mode stays free of external
 * requests and relies on the incident list as the accessible alternative.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CircleLayerSpecification,
  GeoJSONSource,
  LayerSpecification,
  Map,
  MapLayerMouseEvent,
  StyleSpecification,
  SymbolLayerSpecification,
} from "maplibre-gl";
import type { HistoricalMapResponse } from "@/lib/api";
import {
  BASEMAP_MAX_ZOOM,
  resolveBasemap,
  type BasemapId,
} from "../map/MaritimeMap";

import "maplibre-gl/dist/maplibre-gl.css";

export interface HistoricalMapApi {
  flyTo: (lon: number, lat: number, zoom?: number) => void;
  resetNorth: () => void;
}

interface HistoricalMapProps {
  features: HistoricalMapResponse;
  basemapId: BasemapId;
  selectedId: string | null;
  isOffline?: boolean;
  onSelect?: (incidentId: string) => void;
  onApi?: (api: HistoricalMapApi) => void;
}

export type MapRuntimeState =
  | "hydrating"
  | "supported"
  | "unsupported"
  | "initialization_error";

const CLUSTER_CENTER: [number, number] = [70, 20];
const SELECTED_LAYER_ID = "incident-selected";
const GLYPHS_URL = "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf";

// ─── WebGL detection (browser only, called inside effects) ─────────────

function detectWebGLSupport(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    return gl !== null && gl !== undefined;
  } catch {
    return false;
  }
}

// ─── Static helpers ─────────────────────────────────────────────────────

/** Stable shape when the runtime state is still being resolved. */
function HydratingSkeleton() {
  return (
    <div
      className="h-full w-full flex items-center justify-center bg-ocean-ice p-6"
      data-testid="historical-map-loading"
      role="status"
      aria-label="Loading historical incidents map"
    >
      <p className="text-sm text-ocean-muted">Loading map&hellip;</p>
    </div>
  );
}

/** Stable shape when the browser does not support WebGL. */
function UnavailableSkeleton() {
  return (
    <div
      className="h-full w-full flex items-center justify-center bg-ocean-ice p-6"
      data-testid="historical-map-unavailable"
      role="status"
      aria-label="Interactive map unavailable"
    >
      <div
        className="flex items-center justify-center text-center"
        data-testid="historical-map-unsupported"
      >
        <div className="max-w-md">
          <p className="text-sm text-ocean-muted">
            Interactive map is unavailable because this browser does not support
            WebGL. Incidents remain fully browsable in the incident list.
          </p>
          <div className="sr-only" role="status" aria-live="polite" data-testid="map-sr-note">
            Map of verified historical incidents. Use the incident list below as an
            accessible alternative. Marker colour is not the only indicator;
            location accuracy is also shown in the list.
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorSkeleton() {
  return (
    <div
      className="h-full w-full flex items-center justify-center bg-ocean-ice p-6"
      data-testid="historical-map-error"
      role="status"
      aria-label="Map initialisation error"
    >
      <p className="text-sm text-ocean-critical text-center max-w-md">
        Loading the historical incidents map failed on this browser.
      </p>
    </div>
  );
}

export default function HistoricalMap({
  features,
  basemapId,
  selectedId,
  isOffline = false,
  onSelect,
  onApi,
}: HistoricalMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const onApiRef = useRef(onApi);
  useEffect(() => { onApiRef.current = onApi; }, [onApi]);
  // Deterministic initial value: no browser checks during rendering.
  const [runtimeState, setRuntimeState] = useState<MapRuntimeState>("hydrating");
  const initRef = useRef<ReturnType<typeof createInitEffect> | null>(null);

  const base = useMemo(
    () => resolveBasemap(basemapId, isOffline),
    [basemapId, isOffline],
  );

  // ── Resolve WebGL support once, client-side, after hydration ──────────
  useEffect(() => {
    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      if (cancelled) return;
      const supported = detectWebGLSupport();
      setRuntimeState(supported ? "supported" : "unsupported");
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, []);

  // ── Expose the imperative API once the map is ready ───────────────────
  const setApi = useCallback(
    (api: HistoricalMapApi) => {
      setMapReady(true);
      onApiRef.current?.(api);
    },
    [],
  );

  // ── Map creation + style lifecycle ─────────────────────────────────────
  useEffect(() => {
    if (runtimeState !== "supported" || !containerRef.current) return;
    setMapReady(false);
    if (initRef.current) initRef.current.tearDown();
    initRef.current = createInitEffect({
      container: containerRef.current,
      base,
      externalTiles: Boolean(base.url),
      setApi,
      onError: () => setRuntimeState("initialization_error"),
    });
    return () => {
      initRef.current?.tearDown();
      initRef.current = null;
    };
  }, [runtimeState, base, setApi]);

  // ── Feature sourcing + interaction listeners (stable map, re-applied) ─
  useEffect(() => {
    const init = initRef.current;
    if (!mapReady || !init || init.state !== "ready") return;

    const map = init.map;
    if (map === null) return;

    const clusterLayer: CircleLayerSpecification = {
      id: "cluster-count",
      type: "circle",
      source: "incidents",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": "#0E7490",
        "circle-radius": [
          "step",
          ["get", "point_count"],
          17,
          12,
          21,
          40,
          26,
        ],
        "circle-opacity": 0.88,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#F4FAFC",
      },
    };
    const clusterLabelLayer: SymbolLayerSpecification = {
      id: "cluster-label",
      type: "symbol",
      source: "incidents",
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count"],
        "text-size": 11,
        "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
      },
      paint: { "text-color": "#FFFFFF" },
    };
    const incidentPointLayer: CircleLayerSpecification = {
      id: "incident-point",
      type: "circle",
      source: "incidents",
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-color": [
          "case",
          ["==", ["get", "coordinate_accuracy"], "exact"],
          "#0891B2",
          "#F59E0B",
        ],
        "circle-radius": 6.5,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#F4FAFC",
      },
    };
    const incidentLabelLayer: SymbolLayerSpecification = {
      id: "incident-label",
      type: "symbol",
      source: "incidents",
      filter: ["!", ["has", "point_count"]],
      layout: {
        "text-field": ["get", "name"],
        "text-size": 10,
        "text-offset": [0, 1.2],
        "text-anchor": "top",
        "text-max-width": 14,
        "text-font": ["Open Sans Regular", "Arial Unicode MS Regular"],
      },
      paint: {
        "text-color": "#0B2A3D",
        "text-halo-color": "#FFFFFF",
        "text-halo-width": 1.2,
      },
    };
    const selectedLayer: CircleLayerSpecification = {
      id: SELECTED_LAYER_ID,
      type: "circle",
      source: "selected-incident",
      paint: {
        "circle-color": "#EF5B5B",
        "circle-radius": 11,
        "circle-stroke-width": 2.5,
        "circle-stroke-color": "#FFFFFF",
      },
    };

    const externalTilesLocal = Boolean(base.url);
    const existingGeo = map.getSource("incidents");
    const ensureLayers = () => {
      if (existingGeo?.type === "geojson") {
        (existingGeo as GeoJSONSource).setData(
          features as unknown as Parameters<GeoJSONSource["setData"]>[0],
        );
      } else {
        map.addSource("incidents", {
          type: "geojson",
          data: features as unknown as Parameters<GeoJSONSource["setData"]>[0],
          cluster: true,
          clusterMaxZoom: 11,
          clusterRadius: 44,
        });
        map.addLayer(clusterLayer);
        if (externalTilesLocal) map.addLayer(clusterLabelLayer);
        map.addLayer(incidentPointLayer);
        if (externalTilesLocal) map.addLayer(incidentLabelLayer);
      }
    };

    if (map.getSource("incidents")?.type !== "geojson") {
      ensureLayers();
    } else {
      const source = map.getSource<GeoJSONSource>("incidents");
      if (source) {
        source.setData(
          features as unknown as Parameters<GeoJSONSource["setData"]>[0],
        );
      }
    }

    // Keep the selected point separate so clustering cannot hide it.
    const selectedData = {
      type: "FeatureCollection" as const,
      features: features.features.filter((feature) =>
        selectedId != null && (feature.id === selectedId || feature.properties?.incident_id === selectedId)
      ),
    };
    const selectedSource = map.getSource<GeoJSONSource>("selected-incident");
    if (selectedSource) {
      selectedSource.setData(selectedData as Parameters<GeoJSONSource["setData"]>[0]);
    } else {
      map.addSource("selected-incident", { type: "geojson", data: selectedData as Parameters<GeoJSONSource["setData"]>[0] });
      map.addLayer(selectedLayer);
    }

    const onClickCluster = (event: MapLayerMouseEvent) => {
      const hit = map.queryRenderedFeatures(event.point, {
        layers: ["cluster-count"],
      })[0];
      const clusterId = hit?.properties?.cluster_id as number | undefined;
      if (clusterId === undefined) return;
      const source = map.getSource<GeoJSONSource>("incidents");
      if (source) {
        source
          .getClusterExpansionZoom(clusterId)
          .then((zoom) => {
            map.easeTo({ center: event.lngLat, zoom });
          })
          .catch(() => {
            /* cluster may have been removed between click and zoom */
          });
      }
    };
    const onClickPoint = (event: MapLayerMouseEvent) => {
      const hit = map.queryRenderedFeatures(event.point, {
        layers: ["incident-point"],
      })[0];
      const incidentId = hit?.properties?.incident_id as string | undefined;
      if (incidentId) onSelect?.(incidentId);
    };
    const pointerCursor = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const defaultCursor = () => {
      map.getCanvas().style.cursor = "";
    };

    map.on("click", "cluster-count", onClickCluster);
    map.on("click", "incident-point", onClickPoint);
    map.on("mouseenter", "incident-point", pointerCursor);
    map.on("mouseleave", "incident-point", defaultCursor);

    return () => {
      map.off("click", "cluster-count", onClickCluster);
      map.off("click", "incident-point", onClickPoint);
      map.off("mouseenter", "incident-point", pointerCursor);
      map.off("mouseleave", "incident-point", defaultCursor);
    };
  }, [features, selectedId, onSelect, mapReady, base.url]);

  // ─── Render surface ────────────────────────────────────────────────────
  if (runtimeState === "hydrating") return <HydratingSkeleton />;
  if (runtimeState === "unsupported") return <UnavailableSkeleton />;
  if (runtimeState === "initialization_error") return <ErrorSkeleton />;

  return (
    <div
      ref={containerRef}
      className="h-full w-full relative"
      data-testid="historical-map"
      role="region"
      aria-label="Historical incidents map"
    >
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        data-testid="map-sr-note"
      >
        Map of verified historical incidents. Use the incident list below as an
        accessible alternative. Marker colour is not the only indicator;
        location accuracy is also shown in the list.
      </div>
      {basemapId === "satellite" && (
        <div className="absolute bottom-9 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
          <div className="bg-ocean-midnight/85 text-white text-[10px] px-3 py-1.5 rounded-md border border-ocean-teal/40 shadow-card">
            Satellite Context — static imagery, not live SAR
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Map init (module-level logic, never evaluated during render) ───────

interface InitHandle {
  get state(): "loading" | "ready" | "error";
  get map(): Map | null;
  get api(): HistoricalMapApi | null;
  tearDown(): void;
}

function createInitEffect(args: {
  container: HTMLDivElement;
  base: ReturnType<typeof resolveBasemap>;
  externalTiles: boolean;
  setApi: (api: HistoricalMapApi) => void;
  onError: () => void;
}): InitHandle {
  let state: "loading" | "ready" | "error" = "loading";
  let map: Map | null = null;
  let api: HistoricalMapApi | null = null;
  let cancelled = false;

  (async () => {
    let maplibreglModule: typeof import("maplibre-gl") | null = null;
    try {
      maplibreglModule = await import("maplibre-gl");
    } catch (error) {
      throw error;
    }
    if (cancelled || !maplibreglModule) return;

    const { container, base, externalTiles, setApi: setApiFn } = args;

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
    const style: StyleSpecification = {
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
    if (externalTiles) {
      style.glyphs = GLYPHS_URL;
    }

    const mapInst: Map = new maplibreglModule.Map({
      container,
      style,
      center: CLUSTER_CENTER,
      zoom: 2.4,
      maxZoom: 17,
      attributionControl: { compact: true },
    });

    mapInst.addControl(
      new maplibreglModule.NavigationControl({ showCompass: true }),
      "top-right",
    );

    mapInst.on("load", () => {
      if (cancelled) return;
      api = {
        flyTo: (lon, lat, zoom = 8) => {
          if (!cancelled) mapInst.flyTo({ center: [lon, lat], zoom, essential: true });
        },
        resetNorth: () => { if (!cancelled) mapInst.resetNorth(); },
      };
      map = mapInst;
      state = "ready";
      setApiFn(api);
    });

    map = mapInst;
  })().catch(() => {
    if (!cancelled) {
      state = "error";
      args.onError();
    }
  });

  const tearDown = () => {
    cancelled = true;
    if (map) {
      try {
        map.remove();
      } catch {
        /* already removed */
      }
      map = null;
      api = null;
      state = "error";
    }
  };

  return {
    get state() {
      return state;
    },
    get map() {
      return map;
    },
    get api() {
      return api;
    },
    tearDown,
  };
}

// ─── Re-export for backward compatibility ───────────────────────────────

export { BASEMAP_MAX_ZOOM };
