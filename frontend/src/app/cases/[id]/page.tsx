"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Upload,
  FileText,
  Trash2,
  CheckCircle,
  AlertCircle,
  Clock,
  Database,
  Shield,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import StatusChip from "@/components/StatusChip";
import {
  getCase,
  CaseDetail,
  uploadFile,
  listFiles,
  FileInfo,
  deleteCase,
  formatFileSize,
  formatDate,
  errorRequestId,
  stageLabel,
} from "@/lib/api";

export default function CaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorRequestIdValue, setErrorRequestIdValue] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const loadCase = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setErrorRequestIdValue(null);
      const response = await getCase(caseId);
      if (response.success && response.data) {
        setCaseData(response.data as CaseDetail);
        setFiles((response.data as CaseDetail).files || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load case");
      setErrorRequestIdValue(errorRequestId(err) || null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  const handleFileUpload = async (file: File, fileType: string) => {
    try {
      setUploading(true);
      setUploadStatus("Uploading and validating...");
      const result = await uploadFile(caseId, file, fileType);
      if (result.success) {
        setUploadStatus("File uploaded and validated successfully");
        // Reload files
        const filesResponse = await listFiles(caseId);
        setFiles(filesResponse.data || []);
        loadCase(); // Reload case to update dataset_ready
      }
    } catch (err) {
      const requestId = errorRequestId(err);
      setUploadStatus(
        `${err instanceof Error ? err.message : "Upload failed"}` +
          (requestId ? ` — Request ID: ${requestId}` : ""),
      );
    } finally {
      setUploading(false);
      setTimeout(() => setUploadStatus(null), 5000);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      // Determine file type from extension
      const ext = file.name.split(".").pop()?.toLowerCase();
      let fileType = "other";
      if (["tif", "tiff", "jp2"].includes(ext || "")) fileType = "sar";
      else if (["csv", "parquet", "tsv"].includes(ext || "")) fileType = "ais";
      else if (["nc", "netcdf", "nc4"].includes(ext || "")) fileType = "environmental";
      handleFileUpload(file, fileType);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this investigation? This action cannot be undone.")) return;
    try {
      await deleteCase(caseId);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete case");
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="p-6 lg:p-8 flex items-center justify-center min-h-[50vh]">
          <div className="text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-sm text-ocean-muted">Loading investigation...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !caseData) {
    return (
      <AppShell>
        <div className="p-6 lg:p-8 max-w-3xl mx-auto">
          <div className="card px-5 py-8 text-center">
            <AlertCircle className="w-12 h-12 text-ocean-critical mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-ocean-midnight mb-2">
              Investigation Not Found
            </h2>
            <p className="text-sm text-ocean-muted mb-4">{error || "This case does not exist."}</p>
            {errorRequestIdValue && (
              <p className="text-xs text-ocean-muted font-mono mb-4">
                Request ID: {errorRequestIdValue}
              </p>
            )}
            <Link href="/" className="btn-primary">
              Back to Dashboard
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const fileTypeLabels: Record<string, { label: string; accept: string; description: string }> = {
    sar: { label: "SAR Imagery", accept: ".tif,.tiff,.geotiff,.jp2", description: "Sentinel-1 GeoTIFF or COG" },
    ais: { label: "AIS Data", accept: ".csv,.parquet,.tsv", description: "Vessel tracking records" },
    environmental: { label: "Environmental", accept: ".nc,.netcdf,.nc4", description: "Wind and current NetCDF" },
    mask: { label: "Ground Truth", accept: ".tif,.tiff,.png,.jpg", description: "Labelled oil-spill mask" },
  };

  return (
    <AppShell>
      <div className="p-6 lg:p-8 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-start gap-4">
            <Link
              href="/"
              className="p-2 rounded-lg hover:bg-ocean-ice text-ocean-muted hover:text-ocean-slate transition-colors mt-0.5"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-ocean-midnight">
                {caseData.title}
              </h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-ocean-muted">
                <StatusChip status={caseData.status} />
                <span>{stageLabel(caseData.current_stage)}</span>
                {caseData.region && <span>{caseData.region}</span>}
              </div>
            </div>
          </div>
          <button
            onClick={handleDelete}
            className="p-2 rounded-lg hover:bg-red-50 text-ocean-muted hover:text-red-500 transition-colors"
            title="Delete investigation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* Description */}
        {caseData.description && (
          <p className="text-sm text-ocean-muted mb-6 ml-12">
            {caseData.description}
          </p>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main column */}
          <div className="lg:col-span-2 space-y-6">
            {/* File upload zone */}
            <div
              className={`card px-6 py-5 transition-colors ${
                dragOver ? "border-ocean-blue bg-ocean-ice/50" : ""
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <h2 className="text-sm font-semibold text-ocean-midnight uppercase tracking-wider mb-4">
                Data Files
              </h2>

              {/* Upload buttons */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                {Object.entries(fileTypeLabels).map(([type, info]) => (
                  <div key={type}>
                    <input
                      type="file"
                      accept={info.accept}
                      className="hidden"
                      id={`upload-${type}`}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleFileUpload(file, type);
                        e.target.value = "";
                      }}
                    />
                    <label
                      htmlFor={`upload-${type}`}
                      className="flex flex-col items-center gap-2 p-4 border-2 border-dashed border-ocean-border rounded-card cursor-pointer hover:border-ocean-blue hover:bg-ocean-ice/30 transition-colors text-center"
                    >
                      <Upload className="w-5 h-5 text-ocean-muted" />
                      <div>
                        <p className="text-xs font-medium text-ocean-slate">{info.label}</p>
                        <p className="text-[10px] text-ocean-muted mt-0.5">{info.description}</p>
                      </div>
                    </label>
                  </div>
                ))}
              </div>

              {/* Upload status */}
              {uploadStatus && (
                <div
                  className={`px-4 py-2 rounded-lg text-sm ${
                    uploadStatus.includes("success")
                      ? "bg-emerald-50 text-emerald-700"
                      : uploadStatus.includes("fail")
                        ? "bg-red-50 text-red-700"
                        : "bg-cyan-50 text-cyan-700"
                  }`}
                >
                  {uploading ? <div className="spinner inline-block mr-2" /> : null}
                  {uploadStatus}
                </div>
              )}

              {/* File list */}
              {files.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {files.map((f) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-3 px-4 py-3 bg-ocean-ice rounded-lg"
                    >
                      <FileText className="w-4 h-4 text-ocean-muted shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-ocean-slate truncate">
                          {f.original_filename}
                        </p>
                        <div className="flex items-center gap-3 text-xs text-ocean-muted mt-0.5">
                          <span className="chip chip-default">
                            {f.file_type}
                          </span>
                          <span>{formatFileSize(f.file_size)}</span>
                          <span
                            className={
                              f.validation_status === "validated"
                                ? "text-ocean-success"
                                : "text-ocean-critical"
                            }
                          >
                            {f.validation_status === "validated" ? (
                              <CheckCircle className="w-3 h-3 inline mr-0.5" />
                            ) : (
                              <AlertCircle className="w-3 h-3 inline mr-0.5" />
                            )}
                            {f.validation_status}
                          </span>
                        </div>
                      </div>
                      <div className="text-[10px] text-ocean-muted font-mono shrink-0">
                        {f.sha256_checksum.slice(0, 12)}…
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-ocean-muted text-center py-4">
                  No files uploaded yet. Drag a file here or use the buttons above.
                </p>
              )}
            </div>
          </div>

          {/* Sidebar info */}
          <div className="space-y-6">
            {/* Quick info */}
            <div className="card px-5 py-4 space-y-3">
              <h3 className="text-sm font-semibold text-ocean-midnight">
                Case Information
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-ocean-muted">Status</span>
                  <StatusChip status={caseData.status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-muted">Stage</span>
                  <span className="text-ocean-slate text-right">
                    {stageLabel(caseData.current_stage)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ocean-muted">Files</span>
                  <span className="text-ocean-slate">{files.length}</span>
                </div>
                {caseData.incident_time && (
                  <div className="flex justify-between">
                    <span className="text-ocean-muted">Incident</span>
                    <span className="text-ocean-slate text-xs">
                      {formatDate(caseData.incident_time)}
                    </span>
                  </div>
                )}
                {caseData.observation_time && (
                  <div className="flex justify-between">
                    <span className="text-ocean-muted">Observed</span>
                    <span className="text-ocean-slate text-xs">
                      {formatDate(caseData.observation_time)}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-ocean-muted">Created</span>
                  <span className="text-ocean-slate text-xs">
                    {formatDate(caseData.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Readiness indicators */}
            <div className="card px-5 py-4 space-y-3">
              <h3 className="text-sm font-semibold text-ocean-midnight">
                Readiness
              </h3>
              <div className="space-y-2">
                {[
                  { label: "Dataset", ready: caseData.dataset_ready, icon: Database },
                  { label: "System", ready: caseData.system_ready, icon: Shield },
                  { label: "Offline", ready: caseData.offline_ready, icon: Clock },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-2 text-sm">
                    <item.icon className="w-3.5 h-3.5 text-ocean-muted" />
                    <span className="text-ocean-muted">{item.label}</span>
                    <span
                      className={`ml-auto chip text-[10px] ${
                        item.ready ? "chip-success" : "chip-default"
                      }`}
                    >
                      {item.ready ? "Ready" : "Not Ready"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Bounding box */}
            {caseData.bbox_min_lat != null && (
              <div className="card px-5 py-4 space-y-3">
                <h3 className="text-sm font-semibold text-ocean-midnight">
                  Bounding Box
                </h3>
                <div className="font-mono text-xs text-ocean-muted space-y-1">
                  <div>Lat: {caseData.bbox_min_lat} → {caseData.bbox_max_lat}</div>
                  <div>Lon: {caseData.bbox_min_lon} → {caseData.bbox_max_lon}</div>
                </div>
              </div>
            )}

            {/* Analyst notes */}
            {caseData.analyst_notes && (
              <div className="card px-5 py-4 space-y-2">
                <h3 className="text-sm font-semibold text-ocean-midnight">
                  Analyst Notes
                </h3>
                <p className="text-sm text-ocean-muted">{caseData.analyst_notes}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
