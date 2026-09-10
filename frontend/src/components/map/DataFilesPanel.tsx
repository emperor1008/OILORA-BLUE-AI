"use client";

import { useRef, useState } from "react";
import {
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Database,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import {
  FileInfo,
  FileManifest,
  formatFileSize,
  getFileManifest,
  SarProvenance,
} from "@/lib/api";

export const FILE_TYPE_LABELS: Record<
  string,
  { label: string; accept: string; description: string }
> = {
  sar: { label: "SAR Imagery", accept: ".tif,.tiff,.geotiff,.jp2", description: "Sentinel-1 GeoTIFF or COG" },
  ais: { label: "AIS Data", accept: ".csv,.parquet,.tsv", description: "Vessel tracking records" },
  environmental: { label: "Environmental", accept: ".nc,.netcdf,.nc4", description: "Wind and current NetCDF" },
  mask: { label: "Ground Truth", accept: ".tif,.tiff,.png,.jpg", description: "Labelled oil-spill mask" },
  boundary: { label: "Boundary", accept: ".geojson,.json", description: "Known geographic boundary" },
};

interface DataFilesPanelProps {
  files: FileInfo[];
  uploading: boolean;
  uploadStatus: string | null;
  onUpload: (file: File, fileType: string, provenance?: SarProvenance) => void;
  idPrefix?: string;
}

const INPUT_CLASS =
  "w-full px-2.5 py-1.5 text-xs border border-ocean-border rounded-md focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue";

function ManifestRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  const text =
    value === null || value === undefined || value === ""
      ? "Not available"
      : String(value);
  return (
    <div className="flex justify-between gap-3">
      <span className="text-ocean-muted shrink-0">{label}</span>
      <span className="font-mono text-right break-all">{text}</span>
    </div>
  );
}

export default function DataFilesPanel({
  files,
  uploading,
  uploadStatus,
  onUpload,
  idPrefix = "df",
}: DataFilesPanelProps) {
  const [dragOver, setDragOver] = useState(false);
  const [sarMetaOpen, setSarMetaOpen] = useState(false);
  const [sarProvenance, setSarProvenance] = useState<SarProvenance>({});
  const [openManifest, setOpenManifest] = useState<string | null>(null);
  const [manifests, setManifests] = useState<Record<string, FileManifest>>({});
  const [manifestErrors, setManifestErrors] = useState<Record<string, string>>({});
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const toggleManifest = async (fileId: string, caseId: string) => {
    if (openManifest === fileId) {
      setOpenManifest(null);
      return;
    }
    setOpenManifest(fileId);
    if (!manifests[fileId]) {
      try {
        const response = await getFileManifest(caseId, fileId);
        if (response.success && response.data) {
          setManifests((prev) => ({ ...prev, [fileId]: response.data! }));
        }
      } catch (err) {
        setManifestErrors((prev) => ({
          ...prev,
          [fileId]: err instanceof Error ? err.message : "Manifest unavailable",
        }));
      }
    }
  };

  const setSarField = (key: keyof SarProvenance, value: string) => {
    setSarProvenance((prev) => ({ ...prev, [key]: value || undefined }));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    let fileType = "other";
    if (["tif", "tiff", "jp2"].includes(ext || "")) fileType = "sar";
    else if (["csv", "parquet", "tsv"].includes(ext || "")) fileType = "ais";
    else if (["nc", "netcdf", "nc4"].includes(ext || "")) fileType = "environmental";
    else if (["png", "jpg", "jpeg"].includes(ext || "")) fileType = "mask";
    else if (["geojson", "json"].includes(ext || "")) fileType = "boundary";
    onUpload(file, fileType, fileType === "sar" ? sarProvenance : undefined);
  };

  const uploadButtons = Object.entries(FILE_TYPE_LABELS);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-2 border-b border-ocean-border shrink-0">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-ocean-blue" />
          <h2 className="text-sm font-semibold text-ocean-midnight">Data Files</h2>
        </div>
        <p className="text-[11px] text-ocean-muted mt-1 leading-snug">
          Register genuine datasets. Every file is validated and stored with a
          SHA-256 checksum before it can drive scientific processing.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 min-h-0 space-y-4">
        {/* Upload zone */}
        <div
          className={`px-4 py-3 rounded-lg border-2 border-dashed border-ocean-border transition-colors ${
            dragOver ? "border-ocean-blue bg-ocean-ice/50" : ""
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <p className="text-[11px] text-ocean-muted mb-3 text-center">
            Drag a file here or choose a category:
          </p>
          <div className="grid grid-cols-2 gap-2">
            {uploadButtons.map(([type, info]) => (
              <div key={type}>
                <input
                  type="file"
                  accept={info.accept}
                  className="hidden"
                  id={`${idPrefix}-upload-${type}`}
                  ref={(node) => {
                    inputRefs.current[`${idPrefix}-${type}`] = node;
                  }}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      onUpload(
                        file,
                        type,
                        type === "sar" ? sarProvenance : undefined,
                      );
                    }
                    e.target.value = "";
                  }}
                />
                <label
                  htmlFor={`${idPrefix}-upload-${type}`}
                  className="flex flex-col items-center gap-1 p-3 border-2 border-dashed border-ocean-border rounded-card cursor-pointer hover:border-ocean-blue hover:bg-ocean-ice/30 transition-colors text-center h-full justify-center"
                >
                  <Upload className="w-4 h-4 text-ocean-muted" />
                  <p className="text-[11px] font-medium text-ocean-slate leading-tight">
                    {info.label}
                  </p>
                  <p className="text-[9px] text-ocean-muted leading-tight">
                    {info.description}
                  </p>
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Sentinel-1 provenance (optional but required for verified status) */}
        <div className="rounded-lg border border-ocean-border bg-ocean-ice/40">
          <button
            type="button"
            onClick={() => setSarMetaOpen((open) => !open)}
            aria-expanded={sarMetaOpen}
            className="w-full flex items-center gap-1.5 px-3 py-2 text-left"
          >
            {sarMetaOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-ocean-muted shrink-0" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-ocean-muted shrink-0" />
            )}
            <span className="text-[11px] font-semibold text-ocean-slate">
              Sentinel-1 provenance (SAR)
            </span>
          </button>
          {sarMetaOpen && (
            <div className="px-3 pb-3 space-y-2">
              <p className="text-[10px] text-ocean-muted leading-snug">
                For a derived Sentinel-1 GeoTIFF, record the product identifier
                and source. Without both, the file is registered but is never
                reported as verified Sentinel-1 input.
              </p>
              <label className="block">
                <span className="block text-[10px] font-medium text-ocean-muted mb-1">
                  Product identifier
                </span>
                <input
                  type="text"
                  value={sarProvenance.product_identifier || ""}
                  onChange={(e) => setSarField("product_identifier", e.target.value)}
                  placeholder="S1A_IW_GRDH_1SDV_..."
                  className={INPUT_CLASS}
                />
              </label>
              <label className="block">
                <span className="block text-[10px] font-medium text-ocean-muted mb-1">
                  Acquisition time (ISO 8601, timezone required)
                </span>
                <input
                  type="text"
                  value={sarProvenance.acquisition_time || ""}
                  onChange={(e) => setSarField("acquisition_time", e.target.value)}
                  placeholder="2026-06-24T08:53:00Z"
                  className={INPUT_CLASS}
                />
              </label>
              <label className="block">
                <span className="block text-[10px] font-medium text-ocean-muted mb-1">
                  Provenance source (publisher / URL / DOI)
                </span>
                <input
                  type="text"
                  value={sarProvenance.provenance_source || ""}
                  onChange={(e) => setSarField("provenance_source", e.target.value)}
                  placeholder="Copernicus Data Space Ecosystem"
                  className={INPUT_CLASS}
                />
              </label>
              <label className="block">
                <span className="block text-[10px] font-medium text-ocean-muted mb-1">
                  Polarization
                </span>
                <input
                  type="text"
                  value={sarProvenance.polarization || ""}
                  onChange={(e) => setSarField("polarization", e.target.value)}
                  placeholder="VV or VH"
                  className={INPUT_CLASS}
                />
              </label>
            </div>
          )}
        </div>

        {/* Upload status */}
        {uploadStatus && (
          <div
            className={`px-3 py-2 rounded-lg text-xs ${
              uploadStatus.includes("success")
                ? "bg-emerald-50 text-emerald-700"
                : uploadStatus.includes("fail")
                  ? "bg-red-50 text-red-700"
                  : "bg-cyan-50 text-cyan-700"
            }`}
          >
            {uploading ? <span className="spinner inline-block mr-2 w-3 h-3" /> : null}
            {uploadStatus}
          </div>
        )}

        {/* File list */}
        <div>
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ocean-muted mb-2">
            Registered Files ({files.length})
          </h3>
          {files.length > 0 ? (
            <ul className="space-y-2">
              {files.map((file) => {
                const manifest = manifests[file.id];
                const manifestError = manifestErrors[file.id];
                const isOpen = openManifest === file.id;
                return (
                  <li
                    key={file.id}
                    className="px-3 py-2.5 bg-ocean-ice rounded-lg"
                  >
                    <div className="flex items-start gap-2.5">
                      <FileText className="w-4 h-4 text-ocean-muted shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-ocean-slate truncate">
                          {file.original_filename}
                        </p>
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ocean-muted mt-1">
                          <span className="chip chip-default text-[10px]">
                            {file.file_type}
                          </span>
                          <span>{formatFileSize(file.file_size)}</span>
                          {file.validation_status === "validated" ? (
                            <span className="text-ocean-success flex items-center gap-1">
                              <CheckCircle className="w-3 h-3" />
                              validated
                            </span>
                          ) : (
                            <span className="text-ocean-critical flex items-center gap-1">
                              <AlertCircle className="w-3 h-3" />
                              {file.validation_status}
                            </span>
                          )}
                        </div>
                        <p className="text-[9px] font-mono text-ocean-muted mt-1 break-all">
                          {file.sha256_checksum}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleManifest(file.id, file.case_id)}
                      aria-expanded={isOpen}
                      className="mt-2 w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[11px] font-medium text-ocean-blue hover:bg-ocean-ice/70 border border-ocean-border transition-colors"
                    >
                      {isOpen ? (
                        <ChevronDown className="w-3.5 h-3.5 shrink-0" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 shrink-0" />
                      )}
                      <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                      Provenance manifest
                    </button>
                    {isOpen && (
                      <div className="mt-2 px-2.5 py-2 bg-white/60 rounded-md border border-ocean-border text-[10px] text-ocean-slate space-y-1.5">
                        {manifest ? (
                          <>
                            <ManifestRow
                              label="Validation status"
                              value={manifest.validation_status.replace(/_/g, " ")}
                            />
                            <ManifestRow label="Media format" value={manifest.media_format} />
                            <ManifestRow label="Provider" value={manifest.provider} />
                            <ManifestRow
                              label="Product identifier"
                              value={manifest.product_identifier}
                            />
                            <ManifestRow
                              label="Acquisition start"
                              value={manifest.acquisition_start}
                            />
                            <ManifestRow label="CRS" value={manifest.crs} />
                            <ManifestRow
                              label="Spatial bounds"
                              value={
                                manifest.spatial_bounds
                                  ? `left ${Number(manifest.spatial_bounds.left).toFixed(4)} · right ${Number(manifest.spatial_bounds.right).toFixed(4)} · bottom ${Number(manifest.spatial_bounds.bottom).toFixed(4)} · top ${Number(manifest.spatial_bounds.top).toFixed(4)}`
                                  : null
                              }
                            />
                            <ManifestRow
                              label="Registered"
                              value={manifest.registered_at}
                            />
                            <ManifestRow
                              label="Software version"
                              value={manifest.software_version}
                            />
                            {manifest.validation_messages.length > 0 && (
                              <div>
                                <p className="font-semibold text-ocean-muted uppercase tracking-wide mt-1">
                                  Validation notes
                                </p>
                                <ul className="list-disc pl-4 mt-0.5 space-y-0.5">
                                  {manifest.validation_messages.map((message, i) => (
                                    <li key={i}>{message}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </>
                        ) : manifestError ? (
                          <p className="text-ocean-critical">{manifestError}</p>
                        ) : (
                          <p className="text-ocean-muted">Loading manifest…</p>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="text-center py-6">
              <p className="text-xs text-ocean-muted">
                No files uploaded yet. Drag a file here or use the buttons above.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
