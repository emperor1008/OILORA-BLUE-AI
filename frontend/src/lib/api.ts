/**
 * Oilora Blue AI — API Client
 *
 * Typed client for all backend API endpoints.
 * Uses relative URLs so Next.js rewrites proxy to the backend.
 */

import type { GeoJSONFeature, GeoJSONFeatureCollection } from "./geojson";

const API_BASE = "/api";

interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
  error_code?: string;
}

interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number;
  offset: number;
  limit: number;
}

export interface CaseSummary {
  id: string;
  title: string;
  description: string;
  region: string;
  status: string;
  current_stage: string;
  dataset_ready: boolean;
  system_ready: boolean;
  offline_ready: boolean;
  created_at: string;
  updated_at: string;
  file_count: number;
}

export interface CaseDetail extends CaseSummary {
  incident_time: string | null;
  observation_time: string | null;
  bbox_min_lat: number | null;
  bbox_min_lon: number | null;
  bbox_max_lat: number | null;
  bbox_max_lon: number | null;
  analyst_notes: string;
  completed_at: string | null;
  files: FileInfo[];
  jobs: JobInfo[];
}

export interface CaseCreate {
  title: string;
  description?: string;
  region?: string;
  incident_time?: string;
  observation_time?: string;
  bbox_min_lat?: number;
  bbox_min_lon?: number;
  bbox_max_lat?: number;
  bbox_max_lon?: number;
  analyst_notes?: string;
}

export interface FileInfo {
  id: string;
  case_id: string;
  file_type: string;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  mime_type: string | null;
  sha256_checksum: string;
  validation_status: string;
  validation_errors: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface JobInfo {
  id: string;
  case_id: string;
  stage: string;
  status: string;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface SystemStatus {
  backend_status: string;
  database_status: string;
  model_available: boolean;
  model_checksum: string | null;
  disk_space_gb: number;
  offline_ready: boolean;
  app_version: string;
  local_demo_mode: boolean;
}

// ─── Error handling ───────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public errorData?: unknown,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Extract the safest human-readable message from a backend error body. */
function extractErrorMessage(errorData: unknown): string | null {
  if (!errorData || typeof errorData !== "object") return null;
  const d = errorData as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  if (d.detail && typeof d.detail === "object") {
    const msg = (d.detail as Record<string, unknown>).message;
    if (typeof msg === "string") return msg;
  }
  if (typeof d.message === "string") return d.message;
  return null;
}

/**
 * Extract field-level validation errors from a FastAPI 422 body.
 * Returns [{ field, message }] entries suitable for inline form errors.
 */
export function fieldErrors(err: unknown): { field: string; message: string }[] {
  if (!(err instanceof ApiError) || !err.errorData) return [];
  const d = err.errorData as Record<string, unknown>;
  const detail = d.detail;
  if (!Array.isArray(detail)) return [];
  const out: { field: string; message: string }[] = [];
  for (const entry of detail) {
    if (!entry || typeof entry !== "object") continue;
    const e = entry as Record<string, unknown>;
    if (typeof e.msg !== "string") continue;
    const loc = Array.isArray(e.loc) ? e.loc.filter((x) => typeof x === "string") : [];
    const field = loc.length > 0 ? String(loc[loc.length - 1]) : "form";
    out.push({ field, message: e.msg });
  }
  return out;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  const requestId = response.headers.get("x-request-id") || undefined;

  if (!response.ok) {
    let errorData: unknown = null;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    const serverMessage = extractErrorMessage(errorData);
    throw new ApiError(
      response.status,
      serverMessage || `API Error: ${response.status} ${response.statusText}`,
      errorData,
      requestId,
    );
  }

  return response.json();
}

/** Return the request ID from an error, if the backend supplied one. */
export function errorRequestId(err: unknown): string | undefined {
  if (err instanceof ApiError) return err.requestId;
  if (err && typeof err === "object") {
    const rid = (err as { requestId?: unknown }).requestId;
    if (typeof rid === "string") return rid;
  }
  return undefined;
}

// ─── Health ───────────────────────────────────────────────────────────

export async function getHealth(
  signal?: AbortSignal,
): Promise<ApiResponse<{ version: string }>> {
  return request("/health", signal ? { signal } : {});
}

export async function getSystemStatus(): Promise<ApiResponse<SystemStatus>> {
  return request("/system/status");
}

// ─── Cases ────────────────────────────────────────────────────────────

export async function listCases(
  offset = 0,
  limit = 50,
): Promise<PaginatedResponse<CaseSummary>> {
  return request(`/cases?offset=${offset}&limit=${limit}`);
}

export async function getCase(caseId: string): Promise<ApiResponse<CaseDetail>> {
  return request(`/cases/${caseId}`);
}

export async function createCase(
  data: CaseCreate,
): Promise<ApiResponse<CaseDetail>> {
  return request("/cases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCase(
  caseId: string,
  data: Partial<CaseCreate>,
): Promise<ApiResponse<CaseDetail>> {
  return request(`/cases/${caseId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteCase(caseId: string): Promise<ApiResponse> {
  return request(`/cases/${caseId}`, { method: "DELETE" });
}

export async function getCaseStatus(
  caseId: string,
): Promise<
  ApiResponse<{
    case_id: string;
    status: string;
    current_stage: string;
    dataset_ready: boolean;
    system_ready: boolean;
  }>
> {
  return request(`/cases/${caseId}/status`);
}

// ─── Files ────────────────────────────────────────────────────────────

export async function listFiles(
  caseId: string,
): Promise<ApiResponse<FileInfo[]>> {
  return request(`/cases/${caseId}/files`);
}

export interface SarProvenance {
  product_identifier?: string;
  acquisition_time?: string;
  provenance_source?: string;
  polarization?: string;
}

export async function uploadFile(
  caseId: string,
  file: File,
  fileType: string,
  provenance?: SarProvenance,
): Promise<ApiResponse<FileInfo>> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("file_type", fileType);
  if (provenance && fileType === "sar") {
    for (const [key, value] of Object.entries(provenance)) {
      if (value) formData.append(key, value);
    }
  }

  const url = `${API_BASE}/cases/${caseId}/files`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  const requestId = response.headers.get("x-request-id") || undefined;

  if (!response.ok) {
    let errorData: unknown = null;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    const serverMessage = extractErrorMessage(errorData);
    throw new ApiError(
      response.status,
      serverMessage || `Upload failed: ${response.status}`,
      errorData,
      requestId,
    );
  }

  return response.json();
}

export async function getFile(
  caseId: string,
  fileId: string,
): Promise<ApiResponse<FileInfo>> {
  return request(`/cases/${caseId}/files/${fileId}`);
}

// ─── Map workspace types ──────────────────────────────────────────────

export type LayerState =
  | "ready"
  | "not_processed"
  | "missing_input"
  | "failed"
  | "coverage_mismatch"
  | "empty"
  | "unavailable"
  | "processing"
  | "awaiting_review";

export interface MapBounds {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface MapLegendItem {
  label: string;
  color: string;
  fill?: string;
  dash?: number[];
  width?: number;
  symbol?: string;
}

export interface MapLegend {
  title?: string;
  items: MapLegendItem[];
}

export interface MapLayerInfo {
  id: string;
  name: string;
  category: string;
  kind: "vector" | "raster";
  state: LayerState;
  reason: string;
  selectable: boolean;
  timeline: boolean;
  exportable: boolean;
  opacity_default: number;
  min_zoom: number;
  crs: string;
  timestamps: { start?: string; end?: string } | null;
  legend: MapLegend;
}

export interface MapSummary {
  case_id: string;
  case_title: string;
  region: string;
  status: string;
  current_stage: string;
  bounds: MapBounds | null;
  time_range: { start: string; end: string } | null;
  available_layer_ids: string[];
  pending_layer_ids: string[];
  unavailable_layer_ids: string[];
  missing_data: string[];
  has_geospatial_data: boolean;
  map_ready: boolean;
  data_integrity: "ok" | "warning" | "no_data";
  registered_files: Record<string, number>;
}

export interface MapLayerFeatureState {
  layer: string;
  state: LayerState;
  reason: string;
  features: GeoJSONFeatureCollection | null;
  timestamps: { start?: string; end?: string } | null;
  crs: string;
  generated_at: string;
}

export interface SarOverlay {
  available: boolean;
  state: LayerState;
  reason?: string;
  /** Granular honest state: uploaded | format_checked | geospatial_validated |
   * sentinel1_verified | preview_ready | processing_blocked | invalid. */
  validation_status?: string;
  file_id?: string | null;
  source_filename?: string;
  url?: string | null;
  bounds?: [number, number, number, number];
  crs?: string;
  width?: number;
  height?: number;
  band?: number;
  input_sha256?: string;
  preview_sha256?: string;
  generated_at?: string;
  config?: Record<string, unknown>;
  acquisition_time?: string | null;
  polarisation?: string | null;
  product_identifier?: string | null;
  provenance_source?: string | null;
}

export interface ProvenanceSource {
  file_id: string;
  file_type: string;
  original_filename: string;
  file_size: number;
  mime_type: string | null;
  sha256_checksum: string;
  validation_status: string;
  registered_at: string;
  crs: string | null;
  bounds: MapBounds | null;
}

export interface DerivedArtifact {
  artifact: string;
  file_id?: string;
  source_filename?: string;
  input_sha256?: string;
  sha256_checksum?: string;
  generated_at?: string;
  bounds_wsen?: number[];
  width?: number;
  height?: number;
  config?: Record<string, unknown>;
}

export interface MapProvenance {
  case_id: string;
  sources: ProvenanceSource[];
  derived_artifacts: DerivedArtifact[];
  note: string;
}

export interface MapViewport {
  center_lon: number;
  center_lat: number;
  zoom: number;
  bearing: number;
  pitch: number;
}

export interface ViewportResponse {
  case_id: string;
  viewport: MapViewport | null;
  default_viewport: MapViewport | null;
  bounds: MapBounds | null;
}

// ─── Map API ───────────────────────────────────────────────────────────

export async function getMapSummary(caseId: string): Promise<ApiResponse<MapSummary>> {
  return request(`/cases/${caseId}/map/summary`);
}

export async function getMapLayers(
  caseId: string,
): Promise<ApiResponse<{ case_id: string; layers: MapLayerInfo[] }>> {
  return request(`/cases/${caseId}/map/layers`);
}

export async function getMapFeatures(
  caseId: string,
  layerIds?: string[],
): Promise<
  ApiResponse<{ case_id: string; layers: Record<string, MapLayerFeatureState> }>
> {
  const query =
    layerIds && layerIds.length > 0 ? `?layer=${layerIds.join(",")}` : "";
  return request(`/cases/${caseId}/map/features${query}`);
}

export async function getMapProvenance(
  caseId: string,
): Promise<ApiResponse<MapProvenance>> {
  return request(`/cases/${caseId}/map/provenance`);
}

export async function getMapViewport(
  caseId: string,
): Promise<ApiResponse<ViewportResponse>> {
  return request(`/cases/${caseId}/map/viewport`);
}

export async function saveMapViewport(
  caseId: string,
  viewport: {
    center_lon: number;
    center_lat: number;
    zoom: number;
    bearing?: number;
    pitch?: number;
  },
): Promise<ApiResponse> {
  return request(`/cases/${caseId}/map/viewport`, {
    method: "PATCH",
    body: JSON.stringify(viewport),
  });
}

export async function getSarOverlay(
  caseId: string,
): Promise<ApiResponse<SarOverlay>> {
  return request(`/cases/${caseId}/map/sar-overlay`);
}

// ─── Data source registry (Gate 1) ────────────────────────────────────

export type SourceStatus =
  | "connected"
  | "authentication_required"
  | "source_unavailable"
  | "not_configured"
  | "local_file_workflow"
  | "not_verified";

export interface SourceInfo {
  source_id: string;
  source_name: string;
  organization: string;
  data_category: string;
  documentation_url: string;
  access_method: string;
  authentication_required: boolean;
  /** Masked credential status — values never leave the backend. */
  authentication_configured: boolean;
  authentication_note: string;
  licence: string;
  spatial_coverage: string;
  temporal_coverage: string;
  refresh_frequency: string;
  expected_format: string;
  configured_status: SourceStatus;
  latest_error_category: string;
  last_successful_access: string | null;
  last_failed_access: string | null;
  last_probe_at: string | null;
}

export interface FileManifest {
  manifest_id: string;
  case_id: string;
  file_id: string;
  source_id: string | null;
  source_type: string | null;
  provider: string | null;
  product_identifier: string | null;
  acquisition_start: string | null;
  acquisition_end: string | null;
  registered_at: string;
  original_filename: string;
  stored_filename: string;
  byte_size: number;
  sha256_checksum: string;
  media_format: string | null;
  crs: string | null;
  spatial_bounds: Record<string, number> | null;
  temporal_bounds: Record<string, string> | null;
  bands: Record<string, unknown>[] | null;
  validation_status: string;
  validation_messages: string[];
  processing_version: string;
  software_version: string | null;
  created_by: string;
  created_at: string;
}

export async function listSources(): Promise<ApiResponse<SourceInfo[]>> {
  return request("/sources");
}

export async function getSource(sourceId: string): Promise<ApiResponse<SourceInfo>> {
  return request(`/sources/${sourceId}`);
}

export async function testSource(sourceId: string): Promise<ApiResponse<SourceInfo>> {
  return request(`/sources/${sourceId}/test`, { method: "POST" });
}

export async function getFileManifest(
  caseId: string,
  fileId: string,
): Promise<ApiResponse<FileManifest>> {
  return request(`/cases/${caseId}/files/${fileId}/manifest`);
}

// ─── Historical incident explorer ─────────────────────────────────────

export interface HistoricalIncidentSummary {
  id: string;
  canonical_name: string;
  incident_category: string | null;
  verification_status: string;
  start_time_utc: string | null;
  time_precision: string;
  country: string | null;
  location_description: string | null;
  latitude: number | null;
  longitude: number | null;
  coordinate_accuracy: string | null;
  location_method: string | null;
  source_id: string;
  substance_name: string | null;
  satellite_status: string;
  satellite_match_count: number;
}

export interface HistoricalSource {
  id: string;
  incident_id: string;
  organization: string;
  source_title: string | null;
  source_url: string | null;
  publication_date: string | null;
  accessed_at: string;
  source_type: string | null;
  licence_or_usage_note: string | null;
  source_quality: string | null;
}

export interface HistoricalFieldProvenanceEntry {
  field_name: string;
  source_value: string | null;
  normalization_method: string | null;
  confidence_level: string | null;
  curator_note: string | null;
  organization: string;
  source_url: string | null;
  source_title: string | null;
}

export interface HistoricalSatelliteMatch {
  id: string;
  item_id: string;
  product_identifier: string | null;
  platform: string | null;
  collection: string;
  acquisition_start: string | null;
  acquisition_end: string | null;
  acquisition_mode: string | null;
  processing_level: string | null;
  polarizations: string[];
  orbit_direction: string | null;
  metadata_url: string | null;
  asset_access_status: string;
  temporal_distance_hours: number | null;
}

export interface HistoricalIncidentDetail extends HistoricalIncidentSummary {
  end_time_utc: string | null;
  maritime_region: string | null;
  nearest_port: string | null;
  affected_area_geometry_geojson: unknown;
  substance_category: string | null;
  quantity_min: number | null;
  quantity_max: number | null;
  quantity_unit: string | null;
  quantity_status: string | null;
  reported_cause: string | null;
  summary: string | null;
  response_status: string | null;
  original_payload: Record<string, unknown>;
  sources: HistoricalSource[];
  field_provenance: Record<string, HistoricalFieldProvenanceEntry[]>;
  vessels: Record<string, unknown>[];
  impacts: Record<string, unknown>[];
  responses: Record<string, unknown>[];
  satellite_matches: HistoricalSatelliteMatch[];
  satellite_summary: {
    available: boolean;
    reason: string | null;
    match_count: number;
    nearest: Record<string, unknown> | null;
  } | null;
  linked_cases: { id: string; title: string; created_at: string }[];
}

export interface HistoricalOptions {
  categories: string[];
  countries: string[];
  sources: { id: string; name: string }[];
  year_min: string | null;
  year_max: string | null;
}

export interface HistoricalListData extends ApiResponse<HistoricalIncidentSummary[]> {
  total: number;
  limit: number;
  offset: number;
  next_cursor: string | null;
}

export interface HistoricalMapResponse {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

export interface IncidentFilters {
  search?: string;
  country?: string;
  category?: string;
  source?: string;
  start_date?: string;
  end_date?: string;
  satellite_status?: string;
  sort?: string;
}

export interface SatelliteSearchResult {
  status: string;
  message: string;
  matches: {
    item_id: string;
    product_identifier: string;
    platform: string;
    acquisition_start: string | null;
    acquisition_end: string | null;
    acquisition_mode: string;
    processing_level: string;
    polarizations: string[];
    orbit_direction: string | null;
    temporal_distance_hours: number | null;
    metadata_url: string | null;
    asset_access_status: string;
  }[];
  match_count: number;
  provider: string;
  search_bbox?: number[];
  window_days: number;
  searched_at: string;
  access_note: string;
  documentation_url: string;
  warning?: string;
  satellite_summary?: {
    available: boolean;
    reason: string | null;
    match_count: number;
    nearest: Record<string, unknown> | null;
  };
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function listHistoricalIncidents(
  filters: IncidentFilters & {
    limit?: number;
    offset?: number;
    cursor?: string | null;
  } = {},
): Promise<HistoricalListData> {
  return request(
    `/historical-incidents${toQuery({
      search: filters.search,
      country: filters.country,
      category: filters.category,
      source: filters.source,
      start_date: filters.start_date,
      end_date: filters.end_date,
      satellite_status: filters.satellite_status,
      sort: filters.sort,
      limit: filters.limit,
      offset: filters.offset,
      cursor: filters.cursor ?? undefined,
    })}`,
  );
}

export async function getHistoricalIncident(
  incidentId: string,
): Promise<ApiResponse<HistoricalIncidentDetail>> {
  return request(`/historical-incidents/${incidentId}`);
}

export async function getHistoricalOptions(): Promise<ApiResponse<HistoricalOptions>> {
  return request("/historical-incidents/options");
}

export async function getHistoricalMapIncidents(bounds: {
  west: number;
  south: number;
  east: number;
  north: number;
}): Promise<ApiResponse<HistoricalMapResponse>> {
  return request(
    `/historical-incidents/map?west=${bounds.west}&south=${bounds.south}&east=${bounds.east}&north=${bounds.north}`,
  );
}

export async function satelliteSearchIncident(
  incidentId: string,
  params: {
    window_days?: number;
    polarization?: string;
    limit?: number;
  } = {},
): Promise<ApiResponse<SatelliteSearchResult>> {
  return request(
    `/historical-incidents/${incidentId}/satellite-search${toQuery({
      window_days: params.window_days,
      polarization: params.polarization,
      limit: params.limit,
    })}`,
  );
}

export async function createInvestigationFromIncident(
  incidentId: string,
  analystNotes = "",
): Promise<ApiResponse<CaseDetail>> {
  return request(`/historical-incidents/${incidentId}/create-investigation`, {
    method: "POST",
    body: JSON.stringify({ confirm: true, analyst_notes: analystNotes }),
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    registration: "Data Registration",
    validation: "Validation",
    sar_preprocessing: "SAR Preprocessing",
    oil_slick_detection: "Oil-Slick Detection",
    human_review: "Human Review",
    backward_drift: "Backward Drift",
    forward_drift: "Forward Drift",
    ais_analysis: "AIS Analysis",
    candidate_ranking: "Candidate Ranking",
    evidence_manifest: "Evidence Manifest",
    report_generation: "Report Generation",
  };
  return labels[stage] || stage;
}

export function statusColor(status: string): string {
  const colors: Record<string, string> = {
    created: "chip-default",
    data_registered: "chip-info",
    validating: "chip-warning",
    processing: "chip-warning",
    awaiting_review: "chip-info",
    completed: "chip-success",
    failed: "chip-critical",
    cancelled: "chip-default",
  };
  return colors[status] || "chip-default";
}

export function layerStateMeta(state: LayerState): {
  label: string;
  chip: string;
  dot: string;
} {
  const meta: Record<
    LayerState,
    { label: string; chip: string; dot: string }
  > = {
    ready: {
      label: "Ready",
      chip: "chip-success",
      dot: "bg-ocean-success",
    },
    processing: {
      label: "Processing",
      chip: "chip-warning",
      dot: "bg-ocean-warning",
    },
    awaiting_review: {
      label: "Awaiting Review",
      chip: "chip-info",
      dot: "bg-ocean-teal",
    },
    not_processed: {
      label: "Not Processed",
      chip: "chip-default",
      dot: "bg-ocean-muted",
    },
    missing_input: {
      label: "Missing Input",
      chip: "chip-default",
      dot: "bg-ocean-muted",
    },
    failed: {
      label: "Failed",
      chip: "chip-critical",
      dot: "bg-ocean-critical",
    },
    coverage_mismatch: {
      label: "Coverage Mismatch",
      chip: "chip-warning",
      dot: "bg-ocean-warning",
    },
    empty: {
      label: "Empty Result",
      chip: "chip-default",
      dot: "bg-ocean-muted",
    },
    unavailable: {
      label: "Unavailable",
      chip: "chip-default",
      dot: "bg-ocean-muted",
    },
  };
  return meta[state] || meta.unavailable;
}

export function formatCoord(value: number, digits = 5): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Not available";
  }
  return value.toFixed(digits);
}

export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return "Not available";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

export function notAvailable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not available";
  return String(value);
}

