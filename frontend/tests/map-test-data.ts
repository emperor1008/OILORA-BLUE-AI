import type {
  CaseDetail,
  MapLayerInfo,
  MapLayerFeatureState,
  MapProvenance,
  MapSummary,
  SarOverlay,
  ViewportResponse,
} from "@/lib/api";

export function caseDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  return {
    id: "case-map-1",
    title: "Maritime Map Test",
    description: "Workspace behaviour tests",
    region: "Arabian Sea",
    status: "created",
    current_stage: "registration",
    dataset_ready: false,
    system_ready: true,
    offline_ready: false,
    created_at: "2026-01-01T00:00:00+00:00",
    updated_at: "2026-01-01T00:00:00+00:00",
    incident_time: null,
    observation_time: null,
    bbox_min_lat: 15,
    bbox_min_lon: 68,
    bbox_max_lat: 16,
    bbox_max_lon: 69,
    analyst_notes: "",
    completed_at: null,
    file_count: 0,
    files: [],
    jobs: [],
    ...overrides,
  };
}

export function layerInfo(
  id: string,
  name: string,
  category: string,
  kind: "vector" | "raster",
  state: MapLayerInfo["state"],
  reason = "",
  extra: Partial<MapLayerInfo> = {},
): MapLayerInfo {
  return {
    id,
    name,
    category,
    kind,
    state,
    reason,
    selectable: state === "ready" && kind === "vector",
    timeline: false,
    exportable: state === "ready",
    opacity_default: 1,
    min_zoom: 0,
    crs: "EPSG:4326",
    timestamps: null,
    legend: { title: `${name} legend`, items: [{ label: name, color: "#0E7490" }] },
    ...extra,
  };
}

export function mapSummary(
  overrides: Partial<MapSummary> = {},
): MapSummary {
  const base = {
    case_id: "case-map-1",
    case_title: "Maritime Map Test",
    region: "Arabian Sea",
    status: "created",
    current_stage: "registration",
    bounds: {
      min_lat: 15,
      min_lon: 68,
      max_lat: 16,
      max_lon: 69,
    },
    time_range: null,
    has_geospatial_data: true,
    map_ready: true,
    data_integrity: "no_data" as const,
    registered_files: {},
    available_layer_ids: ["investigation_area"],
    pending_layer_ids: [],
    unavailable_layer_ids: ["detection_predicted"],
    missing_data: ["Detection has not been executed."],
  };
  return { ...base, ...overrides };
}

export function summaryWithoutGeometry(): MapSummary {
  return mapSummary({
    bounds: null,
    has_geospatial_data: false,
    map_ready: false,
    available_layer_ids: [],
    unavailable_layer_ids: [
      "investigation_area",
      "sar_raster",
      "detection_predicted",
    ],
    missing_data: [
      "No geographic bounds registered for this case.",
      "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
    ],
  });
}

const BOUNDARY_FEATURES = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "case-map-1-area",
      properties: { layer: "investigation_area", source: "case_bounding_box" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [68, 15],
            [69, 15],
            [69, 16],
            [68, 16],
            [68, 15],
          ],
        ],
      },
    },
  ],
} as const;

export function featureStateReady(
  layer: string,
): MapLayerFeatureState {
  return {
    layer,
    state: "ready",
    reason: "",
    features: JSON.parse(JSON.stringify(BOUNDARY_FEATURES)),
    timestamps: null,
    crs: "EPSG:4326",
    generated_at: "2026-01-01T00:00:00+00:00",
  };
}

export function emptySarOverlay(): SarOverlay {
  return {
    available: false,
    state: "missing_input",
    reason: "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
    file_id: null,
    url: null,
  };
}

export function emptyViewport(): ViewportResponse {
  return {
    case_id: "case-map-1",
    viewport: null,
    default_viewport: {
      center_lon: 68.5,
      center_lat: 15.5,
      zoom: 9,
      bearing: 0,
      pitch: 0,
    },
    bounds: { min_lat: 15, min_lon: 68, max_lat: 16, max_lon: 69 },
  };
}

export function emptyProvenance(): MapProvenance {
  return {
    case_id: "case-map-1",
    sources: [],
    derived_artifacts: [],
    note: "Every derived artifact records its input checksum and generation configuration.",
  };
}

export function layersWithArea(): MapLayerInfo[] {
  return [
    layerInfo(
      "investigation_area",
      "Investigation Area",
      "Context",
      "vector",
      "ready",
    ),
    layerInfo(
      "sar_raster",
      "Sentinel-1 SAR Source",
      "Satellite",
      "raster",
      "missing_input",
      "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
    ),
    layerInfo(
      "detection_predicted",
      "AI-Predicted Oil Boundary",
      "Detection",
      "vector",
      "not_processed",
      "Detection has not been executed.",
    ),
    layerInfo(
      "ais_tracks",
      "AIS Vessel Tracks",
      "Vessels",
      "vector",
      "missing_input",
      "AIS vessel dataset has not been registered for this case.",
    ),
  ];
}
