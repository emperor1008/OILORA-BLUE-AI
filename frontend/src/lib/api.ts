/**
 * Oilora Blue AI — API Client
 *
 * Typed client for all backend API endpoints.
 * Uses relative URLs so Next.js rewrites proxy to the backend.
 */

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

export async function getHealth(): Promise<ApiResponse<{ version: string }>> {
  return request("/health");
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

export async function uploadFile(
  caseId: string,
  file: File,
  fileType: string,
): Promise<ApiResponse<FileInfo>> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("file_type", fileType);

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
