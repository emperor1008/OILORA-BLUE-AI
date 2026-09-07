"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Trash2,
  AlertCircle,
  Layers,
  Database,
  X,
  Map as MapIcon,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import StatusChip from "@/components/StatusChip";
import MapLayerPanel from "@/components/map/MapLayerPanel";
import MapTimeline from "@/components/map/MapTimeline";
import EvidencePanel from "@/components/map/EvidencePanel";
import MapToolbar from "@/components/map/MapToolbar";
import DataFilesPanel from "@/components/map/DataFilesPanel";
import MaritimeMap, {
  MaritimeMapApi,
  VectorLayerView,
  BasemapId,
} from "@/components/map/MaritimeMap";
import {
  getCase,
  CaseDetail,
  FileInfo,
  uploadFile,
  listFiles,
  deleteCase,
  formatDate,
  stageLabel,
  errorRequestId,
  getMapSummary,
  getMapLayers,
  getMapFeatures,
  getMapViewport,
  getSarOverlay,
  getMapProvenance,
  saveMapViewport,
  MapSummary,
  MapLayerInfo,
  MapProvenance,
  MapLayerFeatureState,
  MapViewport,
  ViewportResponse,
  SarOverlay,
  SarProvenance,
} from "@/lib/api";
import type {
  GeoJSONFeatureCollection,
  GeoJSONBounds,
} from "@/lib/geojson";

const VIEWPORT_STORAGE_PREFIX = "oilora.map.hidden.v1.";

export default function CaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

  // ── Case + files (existing behaviour preserved) ──────────────────────
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorRequestIdValue, setErrorRequestIdValue] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  // ── Map workspace state ──────────────────────────────────────────────
  const [summary, setSummary] = useState<MapSummary | null>(null);
  const [layersMeta, setLayersMeta] = useState<MapLayerInfo[]>([]);
  const [layerFeatures, setLayerFeatures] = useState<
    Record<string, MapLayerFeatureState>
  >({});
  const [sar, setSar] = useState<SarOverlay | null>(null);
  const [provenance, setProvenance] = useState<MapProvenance | null>(null);
  const [viewportResp, setViewportResp] = useState<ViewportResponse | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapRequestId, setMapRequestId] = useState<string | null>(null);

  const [visibility, setVisibility] = useState<Record<string, boolean>>({});
  const [opacities, setOpacities] = useState<Record<string, number>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<"layers" | "data">("layers");
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const [basemapId, setBasemapId] = useState<BasemapId>("ocean");
  const [basemapNotice, setBasemapNotice] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);

  // Breakpoint state so closed drawers (absolute overlays below lg/xl) can be
  // made inert, while the always-visible desktop side panels stay interactive.
  const [isDesktop, setIsDesktop] = useState(false); // >= lg (1024px)
  const [isXl, setIsXl] = useState(false); // >= xl (1280px)

  const mapApiRef = useRef<MaritimeMapApi | null>(null);
  const leftDrawerRef = useRef<HTMLElement | null>(null);
  const rightDrawerRef = useRef<HTMLElement | null>(null);
  const leftTriggerRef = useRef<HTMLElement | null>(null);
  const rightTriggerRef = useRef<HTMLElement | null>(null);

  // ── Drawer open/close (with focus memory + restoration) ─────────────
  const openLeft = useCallback((tab: "layers" | "data") => {
    leftTriggerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setLeftTab(tab);
    setLeftOpen(true);
  }, []);

  const closeLeft = useCallback(() => {
    setLeftOpen(false);
    requestAnimationFrame(() => leftTriggerRef.current?.focus?.());
  }, []);

  const openRight = useCallback(() => {
    rightTriggerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setRightOpen(true);
  }, []);

  const closeRight = useCallback(() => {
    setRightOpen(false);
    requestAnimationFrame(() => rightTriggerRef.current?.focus?.());
  }, []);

  // ── Breakpoint tracking ────────────────────────────────────────────
  useEffect(() => {
    const mqLg = window.matchMedia("(min-width: 1024px)");
    const mqXl = window.matchMedia("(min-width: 1280px)");
    const update = () => {
      setIsDesktop(mqLg.matches);
      setIsXl(mqXl.matches);
    };
    update();
    mqLg.addEventListener("change", update);
    mqXl.addEventListener("change", update);
    return () => {
      mqLg.removeEventListener("change", update);
      mqXl.removeEventListener("change", update);
    };
  }, []);

  // ── Escape closes any open drawer and restores focus ───────────────
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (leftOpen) closeLeft();
      else if (rightOpen) closeRight();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [leftOpen, rightOpen, closeLeft, closeRight]);

  // ── Focus management: move focus into an opened drawer, trap it while
  //    open on small screens (modal behaviour). ───────────────────────
  const leftIsModal = leftOpen && !isDesktop;
  const rightIsModal = rightOpen && !isXl;

  useEffect(() => {
    if (!leftIsModal) return;
    const drawer = leftDrawerRef.current;
    const closeBtn = drawer?.querySelector<HTMLElement>(
      'button[aria-label="Close panel"]',
    );
    (closeBtn ?? drawer?.querySelector("button"))?.focus();
  }, [leftIsModal]);

  useEffect(() => {
    if (!rightIsModal) return;
    const drawer = rightDrawerRef.current;
    const closeBtn = drawer?.querySelector<HTMLElement>(
      'button[aria-label="Close evidence drawer"]',
    );
    (closeBtn ?? drawer?.querySelector("button"))?.focus();
  }, [rightIsModal]);

  useEffect(() => {
    const drawer = rightIsModal
      ? rightDrawerRef.current
      : leftIsModal
        ? leftDrawerRef.current
        : null;
    if (!drawer) return;
    const focusables = Array.from(
      drawer.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => !el.hasAttribute("disabled"));
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const onTab = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    drawer.addEventListener("keydown", onTab);
    return () => drawer.removeEventListener("keydown", onTab);
  }, [leftIsModal, rightIsModal]);

  // ── Prevent background scrolling while a modal drawer is open ──────
  useEffect(() => {
    if (!leftIsModal && !rightIsModal) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [leftIsModal, rightIsModal]);

  // ── Case loading ─────────────────────────────────────────────────────
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

  useEffect(() => {
    if (typeof navigator !== "undefined") {
      setIsOffline(!navigator.onLine);
      const onLine = () => setIsOffline(false);
      const offLine = () => setIsOffline(true);
      window.addEventListener("online", onLine);
      window.addEventListener("offline", offLine);
      return () => {
        window.removeEventListener("online", onLine);
        window.removeEventListener("offline", offLine);
      };
    }
    return undefined;
  }, []);

  // ── Map data loading (only after the case exists) ────────────────────
  useEffect(() => {
    let cancelled = false;
    if (!caseData) return undefined;

    const loadMapData = async () => {
      setMapLoading(true);
      setMapError(null);
      setMapRequestId(null);
      try {
        const [summaryRes, layersRes, viewportRes, sarRes, provenanceRes] =
          await Promise.all([
            getMapSummary(caseId),
            getMapLayers(caseId),
            getMapViewport(caseId),
            getSarOverlay(caseId),
            getMapProvenance(caseId),
          ]);
        if (cancelled) return;

        const nextSummary = summaryRes.data as MapSummary;
        const nextLayers = (layersRes.data as { layers: MapLayerInfo[] }).layers;
        setSummary(nextSummary);
        setLayersMeta(nextLayers);
        setViewportResp(viewportRes.data as ViewportResponse);
        setSar(sarRes.data as SarOverlay);
        setProvenance(provenanceRes.data as MapProvenance);

        // Defaults: ready layers visible, raster defaults from backend.
        const defaultVisible: Record<string, boolean> = {};
        const defaultOpacity: Record<string, number> = {};
        for (const layer of nextLayers) {
          defaultVisible[layer.id] = layer.state === "ready";
          defaultOpacity[layer.id] = layer.opacity_default ?? 1;
        }
        try {
          const raw = window.localStorage.getItem(
            `${VIEWPORT_STORAGE_PREFIX}${caseId}`,
          );
          if (raw) {
            const hidden = JSON.parse(raw) as string[];
            for (const id of hidden) defaultVisible[id] = false;
          }
        } catch {
          // safe preference only; ignore storage failures
        }
        setVisibility(defaultVisible);
        setOpacities(defaultOpacity);

        // Fetch real features for ready vector layers.
        const readyVectorIds = nextLayers
          .filter((layer) => layer.kind === "vector" && layer.state === "ready")
          .map((layer) => layer.id);
        if (readyVectorIds.length > 0) {
          const featuresRes = await getMapFeatures(caseId, readyVectorIds);
          if (!cancelled) {
            setLayerFeatures(
              (featuresRes.data as { layers: Record<string, MapLayerFeatureState> })
                .layers,
            );
          }
        } else {
          setLayerFeatures({});
        }
      } catch (err) {
        if (!cancelled) {
          setMapError(
            err instanceof Error ? err.message : "Failed to load map data",
          );
          setMapRequestId(errorRequestId(err) || null);
        }
      } finally {
        if (!cancelled) setMapLoading(false);
      }
    };

    loadMapData();
    return () => {
      cancelled = true;
    };
  }, [caseId, caseData]);

  // ── Upload flow (unchanged semantics) ────────────────────────────────
  const handleFileUpload = useCallback(
    async (file: File, fileType: string, provenance?: SarProvenance) => {
      try {
        setUploading(true);
        setUploadStatus("Uploading and validating...");
        const result = await uploadFile(caseId, file, fileType, provenance);
        if (result.success) {
          setUploadStatus("File uploaded and validated successfully");
          const filesResponse = await listFiles(caseId);
          setFiles(filesResponse.data || []);
          await loadCase(); // refresh map data after registration
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
    },
    [caseId, loadCase],
  );

  const handleDelete = useCallback(async () => {
    if (
      !confirm(
        "Are you sure you want to delete this investigation? This action cannot be undone.",
      )
    ) {
      return;
    }
    try {
      await deleteCase(caseId);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete case");
    }
  }, [caseId, router]);

  // ── Derived map inputs ───────────────────────────────────────────────
  const selectedLayer = useMemo(() => {
    if (!selectedId) return null;
    return layersMeta.find((layer) => layer.id === selectedId) || null;
  }, [selectedId, layersMeta]);

  const bounds: GeoJSONBounds | null = useMemo(() => {
    if (!summary?.bounds) return null;
    const b = summary.bounds;
    if (
      !Number.isFinite(b.min_lat) ||
      !Number.isFinite(b.min_lon) ||
      !Number.isFinite(b.max_lat) ||
      !Number.isFinite(b.max_lon)
    ) {
      return null;
    }
    return b;
  }, [summary]);

  const visibleVectorLayers: VectorLayerView[] = useMemo(() => {
    const out: VectorLayerView[] = [];
    for (const layer of layersMeta) {
      if (layer.kind !== "vector") continue;
      if (visibility[layer.id] === false) continue;
      const features = layerFeatures[layer.id]?.features;
      if (!features) continue;
      out.push({ id: layer.id, name: layer.name, features });
    }
    return out;
  }, [layersMeta, visibility, layerFeatures]);

  const showSar = Boolean(
    sar?.available && visibility["sar_raster"] !== false,
  );
  const sarOpacity = opacities["sar_raster"] ?? 1;

  // Satellite Context uses the keyless NASA GIBS source configured inside
  // MaritimeMap (overridable via NEXT_PUBLIC_SATELLITE_TILES), so it is
  // selectable by default. Sentinel-1 SAR remains a separate registered input.
  const satelliteAvailable = true;
  const hasExportable = visibleVectorLayers.length > 0;

  // ── Actions ──────────────────────────────────────────────────────────
  const toggleLayer = useCallback((id: string) => {
    setVisibility((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  // Persist only safe display preferences (visibility), never data.
  useEffect(() => {
    if (!caseData || layersMeta.length === 0) return;
    const hidden = layersMeta
      .filter((layer) => visibility[layer.id] === false)
      .map((layer) => layer.id);
    try {
      window.localStorage.setItem(
        `${VIEWPORT_STORAGE_PREFIX}${caseId}`,
        JSON.stringify(hidden),
      );
    } catch {
      // safe preference only
    }
  }, [caseData, layersMeta, visibility, caseId]);

  const setLayerOpacity = useCallback((id: string, value: number) => {
    setOpacities((prev) => ({ ...prev, [id]: value }));
  }, []);

  const selectLayer = useCallback((id: string) => {
    rightTriggerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setSelectedId(id);
    setRightOpen(true);
  }, []);

  const saveViewportPref = useCallback(
    (viewport: MapViewport) => {
      saveMapViewport(caseId, viewport).catch(() => {
        // safe preference; failure must not disturb analysis
      });
    },
    [caseId],
  );

  // Honest basemap failure notice (e.g. satellite service unreachable).
  // Deduplicated per basemap selection so it never loops into repeated toasts.
  const handleBasemapError = useCallback(
    (id: BasemapId) => {
      const label = id === "satellite" ? "Satellite Context" : "Ocean / Street";
      setBasemapNotice(
        `${label} tiles could not be loaded from the provider. Analysis layers remain available — switch to Minimal / Offline to continue offline.`,
      );
    },
    [],
  );

  const changeBasemap = useCallback((id: BasemapId) => {
    setBasemapId(id);
    setBasemapNotice(null);
  }, []);

  const downloadGeojson = useCallback(
    (layerId: string) => {
      const state = layerFeatures[layerId];
      const collection = state?.features;
      if (!collection) return;
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      const blob = new Blob([JSON.stringify(collection, null, 2)], {
        type: "application/geo+json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${caseId}-${layerId}-${stamp}.geojson`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },
    [caseId, layerFeatures],
  );

  const exportVisible = useCallback(() => {
    const collections: GeoJSONFeatureCollection = {
      type: "FeatureCollection",
      features: [],
    };
    for (const layer of visibleVectorLayers) {
      for (const feature of layer.features.features) {
        collections.features.push(feature);
      }
    }
    if (collections.features.length === 0) return;
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const blob = new Blob([JSON.stringify(collections, null, 2)], {
      type: "application/geo+json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${caseId}-visible-layers-${stamp}.geojson`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }, [caseId, visibleVectorLayers]);

  // ── Loading / error states (messages preserved for existing tests) ───
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
            <p className="text-sm text-ocean-muted mb-4">
              {error || "This case does not exist."}
            </p>
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

  const timelineDisabledReason =
    "Timeline playback becomes available when time-indexed scientific data (drift, AIS, environmental steps) has been processed for this case.";

  return (
    <AppShell>
      <div className="flex flex-col h-[calc(100dvh-56px)] overflow-hidden bg-ocean-ice">
        {/* ── Case context bar ─────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-3 lg:px-4 h-12 bg-white border-b border-ocean-border shrink-0">
          <Link
            href="/"
            className="p-2 -ml-1 rounded-lg hover:bg-ocean-ice text-ocean-muted hover:text-ocean-slate transition-colors shrink-0"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-sm font-bold text-ocean-midnight truncate">
                {caseData.title}
              </h1>
              <StatusChip status={caseData.status} />
              <span className="hidden sm:inline text-[11px] text-ocean-muted shrink-0">
                {stageLabel(caseData.current_stage)}
              </span>
            </div>
            <p className="text-[10px] font-mono text-ocean-muted truncate">
              {caseData.id} · updated {formatDate(caseData.updated_at)}
            </p>
          </div>
          <span className="hidden md:inline chip chip-default text-[10px] shrink-0">
            <MapIcon className="w-3 h-3" /> Maritime Intelligence Workspace
          </span>
          <button
            type="button"
            onClick={() => openLeft("data")}
            className="btn-secondary text-xs shrink-0 hidden sm:inline-flex"
          >
            <Database className="w-3.5 h-3.5" />
            Register Data
          </button>
          <button
            onClick={handleDelete}
            className="p-2 rounded-lg hover:bg-red-50 text-ocean-muted hover:text-red-500 transition-colors shrink-0"
            title="Delete investigation"
            aria-label="Delete investigation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* ── Workspace body ───────────────────────────────────────── */}
        <div className="relative flex flex-1 min-h-0">
          {/* Left rail backdrop (tablet/mobile) */}
          {leftOpen && (
            <button
              type="button"
              aria-label="Close layer panel"
              className="absolute inset-0 z-30 bg-ocean-midnight/30 lg:hidden"
              onClick={closeLeft}
            />
          )}
          {/* Right panel backdrop */}
          {rightOpen && (
            <button
              type="button"
              aria-label="Close evidence panel"
              className="absolute inset-0 z-30 bg-ocean-midnight/30 xl:hidden"
              onClick={closeRight}
            />
          )}

          {/* ── Left rail: layers / data ─────────────────────────── */}
          <aside
            ref={leftDrawerRef}
            aria-hidden={!leftIsModal && !isDesktop}
            inert={!leftIsModal && !isDesktop}
            className={[
              "flex flex-col bg-white border-r border-ocean-border",
              "w-72 max-w-[88vw] z-40",
              "absolute lg:static top-0 bottom-0 left-0",
              "transform transition-transform duration-200 ease-in-out",
              leftOpen ? "translate-x-0" : "-translate-x-full",
              "lg:translate-x-0 lg:transition-none",
            ].join(" ")}
          >
            {/* Workspace branding (desktop) */}
            <div className="hidden lg:block px-4 pt-3 pb-2 border-b border-ocean-border shrink-0">
              <p className="text-[9px] font-bold uppercase tracking-widest text-ocean-blue">
                Oilora Blue AI
              </p>
              <h2 className="text-sm font-bold text-ocean-midnight leading-tight">
                Maritime Intelligence Workspace
              </h2>
              <p className="text-[10px] text-ocean-muted mt-0.5 leading-snug">
                Satellite evidence, environmental analysis, and incident
                documentation
              </p>
            </div>
            <div className="flex items-center border-b border-ocean-border shrink-0 px-2 py-1.5">
              {(
                [
                  { id: "layers", label: "Layers", icon: Layers },
                  { id: "data", label: "Data Files", icon: Database },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setLeftTab(tab.id)}
                  aria-pressed={leftTab === tab.id}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-xs font-medium transition-colors ${
                    leftTab === tab.id
                      ? "bg-ocean-ice text-ocean-slate"
                      : "text-ocean-muted hover:text-ocean-slate"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              ))}
              <button
                type="button"
                onClick={closeLeft}
                className="lg:hidden p-2 rounded-md text-ocean-muted hover:bg-ocean-ice"
                aria-label="Close panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 min-h-0">
              {leftTab === "layers" ? (
                <MapLayerPanel
                  layers={layersMeta}
                  visibility={visibility}
                  onToggle={toggleLayer}
                  opacities={opacities}
                  onOpacity={setLayerOpacity}
                  selectedId={selectedId}
                  onSelectLayer={selectLayer}
                  loading={mapLoading && layersMeta.length === 0}
                  error={mapError}
                  onRegisterSar={() => openLeft("data")}
                />
              ) : (
                <DataFilesPanel
                  files={files}
                  uploading={uploading}
                  uploadStatus={uploadStatus}
                  onUpload={handleFileUpload}
                  idPrefix="case-data"
                />
              )}
            </div>
          </aside>

          {/* ── Centre: map + timeline ────────────────────────────── */}
          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            <div className="relative flex-1 min-h-0 bg-ocean-deep">
              <MaritimeMap
                bounds={bounds}
                vectorLayers={visibleVectorLayers}
                sarOverlay={sar}
                showSar={showSar}
                sarOpacity={sarOpacity}
                basemapId={basemapId}
                initialViewport={viewportResp?.viewport ?? viewportResp?.default_viewport ?? null}
                selectedId={selectedId}
                onSelect={selectLayer}
                onViewportChange={saveViewportPref}
                onExportGeojson={downloadGeojson}
                onApi={(api) => {
                  mapApiRef.current = api;
                }}
                onBasemapError={handleBasemapError}
                isOffline={isOffline}
              />

              {/* Scientific-layer label chips (top-left) */}
              <div className="absolute top-3 left-3 z-10 flex flex-col items-start gap-1.5 max-w-[55%] pointer-events-none">
                {showSar && sar?.available && (
                  <span className="chip bg-ocean-midnight/85 text-ocean-aqua border border-ocean-teal/40 text-[10px] backdrop-blur-sm">
                    Scientific Sentinel-1 SAR
                  </span>
                )}
                {visibleVectorLayers.map((layer) => (
                  <span
                    key={layer.id}
                    className="chip bg-white/90 border border-ocean-border text-ocean-slate text-[10px] backdrop-blur-sm"
                  >
                    {layer.name}
                  </span>
                ))}
                {!showSar &&
                  !sar?.available &&
                  visibleVectorLayers.length === 0 &&
                  !summary?.has_geospatial_data && (
                    <span className="chip bg-white/90 border border-ocean-border text-ocean-muted text-[10px] backdrop-blur-sm">
                      Context basemap only
                    </span>
                  )}
              </div>

              {/* Empty-geography notice */}
              {!summary?.has_geospatial_data && !mapLoading && !mapError && (
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 w-[92%] max-w-md pointer-events-none">
                  <div className="bg-white/95 border border-ocean-border rounded-lg shadow-card px-4 py-2.5 text-center">
                    <p className="text-xs font-medium text-ocean-slate">
                      No geospatial case data registered
                    </p>
                    <p className="text-[11px] text-ocean-muted mt-0.5 leading-snug">
                      Register a genuine SAR, boundary or AIS file (or set case
                      bounds) to see real data here. Nothing is simulated.
                    </p>
                  </div>
                </div>
              )}

              {/* Map data error */}
              {mapError && (
                <div className="absolute top-12 left-1/2 -translate-x-1/2 z-10 w-[92%] max-w-md">
                  <div className="bg-red-50 border border-red-200 rounded-lg shadow-card px-4 py-2.5">
                    <p className="text-xs font-medium text-red-700">
                      Map data could not be loaded
                    </p>
                    <p className="text-[11px] text-red-500 mt-0.5">{mapError}</p>
                    {mapRequestId && (
                      <p className="text-[10px] text-red-400 mt-1 font-mono">
                        Request ID: {mapRequestId}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Basemap failure notice (non-blocking; map stays usable) */}
              {basemapNotice && !mapError && (
                <div className="absolute top-12 left-1/2 -translate-x-1/2 z-10 w-[92%] max-w-md">
                  <div className="bg-amber-50 border border-amber-200 rounded-lg shadow-card px-4 py-2.5">
                    <p className="text-xs font-medium text-amber-800">
                      {basemapNotice}
                    </p>
                    <button
                      type="button"
                      onClick={() => changeBasemap("minimal")}
                      className="mt-1 text-[11px] font-medium text-ocean-blue underline underline-offset-2"
                    >
                      Switch to Minimal / Offline
                    </button>
                  </div>
                </div>
              )}

              <MapToolbar
                basemapId={basemapId}
                onBasemapChange={changeBasemap}
                satelliteAvailable={satelliteAvailable}
                onOpenLayers={() => openLeft("layers")}
                onOpenEvidence={openRight}
                onOpenData={() => openLeft("data")}
                onFitToCase={() => mapApiRef.current?.fitToCase()}
                onResetNorth={() => mapApiRef.current?.resetNorth()}
                onExportVisible={exportVisible}
                canExport={hasExportable}
              />
            </div>

            {/* ── Shared scientific timeline ──────────────────────── */}
            <MapTimeline
              range={summary?.time_range ?? null}
              disabledReason={
                summary && !summary.time_range
                  ? "No time-indexed data for this case. Register a dataset with an observation time."
                  : timelineDisabledReason
              }
            />
          </div>

          {/* ── Right: evidence panel ─────────────────────────────── */}
          <aside
            ref={rightDrawerRef}
            aria-hidden={!rightIsModal && !isXl}
            inert={!rightIsModal && !isXl}
            className={[
              "flex flex-col bg-white border-l border-ocean-border",
              "w-[21rem] max-w-[92vw] z-40",
              "absolute xl:static top-0 bottom-0 right-0",
              "transform transition-transform duration-200 ease-in-out",
              rightOpen ? "translate-x-0" : "translate-x-full",
              "xl:translate-x-0 xl:transition-none",
            ].join(" ")}
          >
            <EvidencePanel
              summary={summary}
              selectedLayer={selectedLayer}
              layerFeatures={layerFeatures}
              provenance={provenance}
              onClose={() => setSelectedId(null)}
              onCloseDrawer={closeRight}
              onExportGeojson={downloadGeojson}
            />
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
