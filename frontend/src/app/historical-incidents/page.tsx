"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  Filter,
  Loader2,
  MapPin,
  Satellite,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import AppShell from "@/components/AppShell";
import HistoricalMap, {
  type HistoricalMapApi,
} from "@/components/incidents/HistoricalMap";
import type { BasemapId } from "@/components/map/MaritimeMap";
import {
  errorRequestId,
  formatUtc,
  getHistoricalIncident,
  getHistoricalOptions,
  getHistoricalMapIncidents,
  listHistoricalIncidents,
  type HistoricalFieldProvenanceEntry,
  type HistoricalIncidentDetail,
  type HistoricalIncidentSummary,
  type HistoricalMapResponse,
  type HistoricalOptions,
  notAvailable,
} from "@/lib/api";

const BASEMAPS: { id: BasemapId; label: string }[] = [
  { id: "ocean", label: "Ocean" },
  { id: "satellite", label: "Satellite Context" },
  { id: "minimal", label: "Minimal" },
];

function emptyFeatureCollection(): HistoricalMapResponse {
  return { type: "FeatureCollection", features: [] };
}

/**
 * useSearchParams must live below a Suspense boundary so Next.js can
 * statically prerender the shell and stream the search-param-dependent UI.
 */
export default function HistoricalIncidentsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-ocean-ice">
          <div className="card px-6 py-8 text-center">
            <div className="spinner mx-auto mb-3" />
            <p className="text-sm text-ocean-muted">Loading historical incidents...</p>
          </div>
        </div>
      }
    >
      <HistoricalIncidentsExplorer />
    </Suspense>
  );
}

function HistoricalIncidentsExplorer() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [incidents, setIncidents] = useState<HistoricalIncidentSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [country, setCountry] = useState("");
  const [category, setCategory] = useState("");
  const [options, setOptions] = useState<HistoricalOptions | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const [basemapId, setBasemapId] = useState<BasemapId>("ocean");
  const [mapFeatures, setMapFeatures] = useState<HistoricalMapResponse>(
    emptyFeatureCollection(),
  );
  const [mapBounds, setMapBounds] = useState<{
    west: number;
    south: number;
    east: number;
    north: number;
  } | null>(null);

  const selectedId = searchParams.get("incident");
  const [detail, setDetail] = useState<HistoricalIncidentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [mapApi, setMapApi] = useState<HistoricalMapApi | null>(null);
  const handleMapApi = useCallback((api: HistoricalMapApi) => setMapApi(api), []);

  // Load filter options once.
  useEffect(() => {
    let active = true;
    getHistoricalOptions()
      .then((res) => {
        if (active && res.success && res.data) setOptions(res.data);
      })
      .catch(() => {
        // Options are non-critical; the page still works without them.
      });
    return () => {
      active = false;
    };
  }, []);

  // Debounced search + filters fetch the incident list.
  const loadList = useCallback(
    async (searchTerm: string, countryTerm: string, categoryTerm: string) => {
      setLoading(true);
      setError(null);
      setRequestId(null);
      try {
        const res = await listHistoricalIncidents({
          search: searchTerm || undefined,
          country: countryTerm || undefined,
          category: categoryTerm || undefined,
          limit,
          offset: 0,
        });
        if (res.success && Array.isArray(res.data)) {
          setIncidents(res.data);
          setTotal(res.total ?? res.data.length);
          setOffset(0);
        } else {
          setIncidents([]);
          setTotal(0);
        }
      } catch (err) {
        setIncidents([]);
        setError(err instanceof Error ? err.message : "Failed to load incidents");
        setRequestId(errorRequestId(err) || null);
      } finally {
        setLoading(false);
      }
    },
    [limit],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      loadList(search, country, category);
    }, 250);
    return () => clearTimeout(timer);
  }, [search, country, category, loadList]);

  // Load more (server-side pagination).
  const loadMore = async () => {
    if (loading || incidents === null) return;
    setLoading(true);
    try {
      const res = await listHistoricalIncidents({
        search: search || undefined,
        country: country || undefined,
        category: category || undefined,
        limit,
        offset: offset + limit,
      });
      const items = res.data ?? [];
      if (res.success && items.length > 0) {
        setIncidents((prev) => [...(prev ?? []), ...items]);
        setTotal(res.total ?? 0);
        setOffset((prev) => prev + limit);
      }
    } catch {
      // Keep the already-loaded list; the load-more button can be retried.
    } finally {
      setLoading(false);
    }
  };

  // Load map features for the current filter set (worldwide when no bounds).
  useEffect(() => {
    let active = true;
    getHistoricalMapIncidents(
      mapBounds ?? { west: -180, south: -90, east: 180, north: 90 },
    )
      .then((res) => {
        if (active && res.success && res.data) setMapFeatures(res.data);
      })
      .catch(() => {
        if (active) setMapFeatures(emptyFeatureCollection());
      });
    return () => {
      active = false;
    };
  }, [mapBounds]);

  // Load detail for the selected incident (URL-driven, survives refresh).
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    getHistoricalIncident(selectedId)
      .then((res) => {
        if (!active) return;
        if (res.success && res.data) {
          setDetail(res.data);
        } else {
          setDetail(null);
          setDetailError("Incident not found.");
        }
      })
      .catch((err) => {
        if (!active) return;
        setDetail(null);
        setDetailError(
          err instanceof Error ? err.message : "Failed to load incident details",
        );
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const selectIncident = useCallback(
    (incidentId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("incident", incidentId);
      router.replace(`/historical-incidents?${params.toString()}`, {
        scroll: false,
      });
    },
    [router, searchParams],
  );

  const clearSelection = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("incident");
    router.replace(`/historical-incidents?${params.toString()}`, { scroll: false });
  }, [router, searchParams]);

  // Move the map to the selected incident's exact stored coordinates.
  useEffect(() => {
    if (detail?.latitude != null && detail.longitude != null) {
      mapApi?.flyTo(detail.longitude, detail.latitude, 8);
    }
  }, [mapApi, detail?.latitude, detail?.longitude]);

  const resetFilters = () => {
    setSearch("");
    setCountry("");
    setCategory("");
  };

  const hasFilters = Boolean(search || country || category);

  return (
    <AppShell>
      <div className="flex flex-col h-[calc(100vh-4rem)]">
        {/* Page header */}
        <div className="px-6 py-4 border-b border-ocean-border bg-white shrink-0">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-xl font-bold text-ocean-midnight">
                Historical Incidents
              </h1>
              <p className="text-xs text-ocean-muted mt-0.5">
                Source-registered maritime incidents from documented archives.
                Incidents with coordinates are shown on the map; all incidents
                remain browsable in the list.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="flex items-center rounded-lg border border-ocean-border overflow-hidden"
                role="group"
                aria-label="Basemap selector"
              >
                {BASEMAPS.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => setBasemapId(b.id)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      basemapId === b.id
                        ? "bg-ocean-blue text-white"
                        : "bg-white text-ocean-slate hover:bg-ocean-ice"
                    }`}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Map + list */}
        <div className="flex-1 flex flex-col lg:flex-row min-h-0">
          {/* Map */}
          <div className="flex-1 min-h-[320px] lg:min-h-0 relative">
            <HistoricalMap
              features={mapFeatures}
              basemapId={basemapId}
              selectedId={selectedId}
              onSelect={selectIncident}
              onApi={handleMapApi}
            />
            {incidents && incidents.length > 0 && (
              <button
                onClick={() =>
                  setMapBounds({
                    west: -180,
                    south: -90,
                    east: 180,
                    north: 90,
                  })
                }
                className="absolute top-3 left-3 z-10 btn-secondary text-[11px] px-2.5 py-1.5"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                Fit world
              </button>
            )}
          </div>

          {/* Incident list sidebar */}
          <aside className="lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-ocean-border bg-ocean-ice/40 flex flex-col min-h-0">
            <div className="p-4 space-y-3 shrink-0">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ocean-muted" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search incidents..."
                  aria-label="Search historical incidents"
                  className="w-full pl-9 pr-8 py-2 text-sm border border-ocean-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ocean-blue/30 focus:border-ocean-blue bg-white"
                />
                {search && (
                  <button
                    onClick={() => setSearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-ocean-muted hover:text-ocean-slate"
                    aria-label="Clear search"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <button
                onClick={() => setFiltersOpen((v) => !v)}
                className="btn-secondary text-xs w-full inline-flex items-center justify-center gap-2"
                aria-expanded={filtersOpen}
              >
                <Filter className="w-3.5 h-3.5" />
                Filters
                {hasFilters && (
                  <span className="w-2 h-2 rounded-full bg-ocean-teal inline-block" />
                )}
              </button>
              {filtersOpen && (
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="text-[10px] font-medium text-ocean-muted block mb-1">
                      Country
                    </span>
                    <select
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      className="w-full px-2 py-1.5 text-xs border border-ocean-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-ocean-blue/30"
                    >
                      <option value="">All countries</option>
                      {options?.countries.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-[10px] font-medium text-ocean-muted block mb-1">
                      Category
                    </span>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="w-full px-2 py-1.5 text-xs border border-ocean-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-ocean-blue/30"
                    >
                      <option value="">All categories</option>
                      {options?.categories.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </label>
                  {hasFilters && (
                    <button
                      onClick={resetFilters}
                      className="col-span-2 text-[11px] text-ocean-blue hover:underline text-left"
                    >
                      Clear all filters
                    </button>
                  )}
                </div>
              )}
              <p className="text-[11px] text-ocean-muted" role="status" aria-live="polite">
                {loading
                  ? "Loading incidents..."
                  : `${total} source-registered incident${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
              {error && (
                <div className="card px-4 py-3 text-sm text-ocean-critical" role="alert">
                  <p>{error}</p>
                  {requestId && (
                    <p className="text-xs text-ocean-muted font-mono mt-1">
                      Request ID: {requestId}
                    </p>
                  )}
                </div>
              )}
              {!error && incidents && incidents.length === 0 && (
                <div className="card px-4 py-8 text-center" role="status">
                  <MapPin className="w-8 h-8 text-ocean-muted mx-auto mb-2" />
                  <p className="text-sm text-ocean-muted">
                    No historical incidents match the current filters.
                  </p>
                  <p className="text-xs text-ocean-muted mt-1">
                    {hasFilters
                      ? "Clear filters to browse all registered incidents."
                      : "No incidents are imported on this backend yet. The importer only ingests authentic, documented archives."}
                  </p>
                </div>
              )}
              {incidents?.map((incident) => (
                <button
                  key={incident.id}
                  onClick={() => selectIncident(incident.id)}
                  className={`w-full text-left card px-4 py-3 hover:border-ocean-teal transition-colors ${
                    selectedId === incident.id
                      ? "border-ocean-teal ring-1 ring-ocean-teal/40"
                      : ""
                  }`}
                  aria-pressed={selectedId === incident.id}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-ocean-midnight leading-snug">
                      {incident.canonical_name}
                    </h3>
                    {incident.coordinate_accuracy === "approximate" && (
                      <span className="chip chip-warning text-[9px] shrink-0 mt-0.5">
                        Approx. location
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[11px] text-ocean-muted">
                    {incident.start_time_utc && (
                      <span>{formatUtc(incident.start_time_utc)}</span>
                    )}
                    {incident.country && <span>{incident.country}</span>}
                    {incident.incident_category && (
                      <span className="text-ocean-teal">{incident.incident_category}</span>
                    )}
                  </div>
                  {incident.latitude == null && (
                    <p className="text-[10px] text-ocean-warning mt-1">
                      No coordinates in source record — listed here but not placed
                      on the map.
                    </p>
                  )}
                </button>
              ))}
              {incidents && total > incidents.length && (
                <button
                  onClick={loadMore}
                  disabled={loading}
                  className="w-full btn-secondary text-xs py-2"
                >
                  {loading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" />
                  ) : (
                    `Load more (${total - incidents.length} remaining)`
                  )}
                </button>
              )}
            </div>
          </aside>
        </div>

        {/* Incident detail drawer */}
        {selectedId && (
          <div
            className="fixed inset-0 bg-black/30 z-20 lg:hidden"
            onClick={clearSelection}
            aria-hidden="true"
          />
        )}
        {selectedId && (
          <section
            className={`fixed z-30 bg-white shadow-2xl transition-transform duration-200 ${
              "inset-x-0 bottom-0 max-h-[70vh] rounded-t-xl lg:inset-x-auto lg:left-auto lg:right-0 lg:top-16 lg:bottom-0 lg:max-h-none lg:w-[26rem] lg:rounded-none"
            }`}
            aria-label="Incident details"
          >
            <IncidentDetailPanel
              detail={detail}
              loading={detailLoading}
              error={detailError}
              onClose={clearSelection}
              onSelect={() => setMapBounds(null)}
            />
          </section>
        )}
      </div>
    </AppShell>
  );
}

function IncidentDetailPanel({
  detail,
  loading,
  error,
  onClose,
  onSelect,
}: {
  detail: HistoricalIncidentDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSelect: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-ocean-border shrink-0">
        <h2 className="text-sm font-bold text-ocean-midnight">Incident Details</h2>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-ocean-ice text-ocean-muted hover:text-ocean-slate"
          aria-label="Close details"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {loading && (
          <div className="py-10 text-center" role="status">
            <Loader2 className="w-6 h-6 animate-spin text-ocean-blue mx-auto mb-3" />
            <p className="text-sm text-ocean-muted">Loading details...</p>
          </div>
        )}
        {error && (
          <div className="card px-4 py-3 text-sm text-ocean-critical" role="alert">
            {error}
          </div>
        )}
        {!loading && !error && detail && (
          <div className="space-y-5">
            <div>
              <h3 className="text-base font-bold text-ocean-midnight leading-snug">
                {detail.canonical_name}
              </h3>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {detail.incident_category && (
                  <span className="chip chip-info text-[10px]">{detail.incident_category}</span>
                )}
                <span className="chip chip-default text-[10px]">
                  {detail.verification_status}
                </span>
              </div>
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
              <DetailItem label="Start time (UTC)" value={formatUtc(detail.start_time_utc)} />
              <DetailItem label="End time (UTC)" value={formatUtc(detail.end_time_utc)} />
              <DetailItem label="Country" value={notAvailable(detail.country)} />
              <DetailItem
                label="Location"
                value={
                  detail.location_description ||
                  (detail.latitude != null && detail.longitude != null
                    ? `${detail.latitude.toFixed(3)}, ${detail.longitude.toFixed(3)}`
                    : "Not available")
                }
              />
              <DetailItem
                label="Coordinates"
                value={
                  detail.latitude != null && detail.longitude != null
                    ? `${detail.latitude.toFixed(4)}°, ${detail.longitude.toFixed(4)}°`
                    : "Not in source record"
                }
              />
              <DetailItem
                label="Coordinate accuracy"
                value={notAvailable(detail.coordinate_accuracy)}
              />
              <DetailItem label="Substance" value={notAvailable(detail.substance_name)} />
              <DetailItem label="Quantity" value={quantityLabel(detail)} />
            </dl>

            {detail.summary && (
              <p className="text-xs text-ocean-slate leading-relaxed">{detail.summary}</p>
            )}

            {detail.satellite_status && (
              <div className="card px-4 py-3 bg-ocean-ice/50">
                <div className="flex items-center gap-2 text-xs font-medium text-ocean-slate">
                  <Satellite className="w-4 h-4 text-ocean-blue" />
                  Satellite coverage
                </div>
                <p className="text-[11px] text-ocean-muted mt-1 leading-snug">
                  {detail.satellite_status === "available"
                    ? `${detail.satellite_match_count} catalogue match(es) near this incident. Availability depends on sensor, date, cloud conditions and coverage.`
                    : "No verified Sentinel-1 catalogue match is recorded for this incident."}
                </p>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold text-ocean-midnight uppercase tracking-wider mb-2">
                Sources &amp; provenance
              </h4>
              {detail.sources && detail.sources.length > 0 ? (
                <ul className="space-y-2">
                  {detail.sources.map((source) => (
                    <li key={source.id} className="text-[11px] text-ocean-slate">
                      <span className="font-medium">{source.organization}</span>
                      {source.source_title && <span> — {source.source_title}</span>}
                      {source.source_url && (
                        <a
                          href={source.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-1 text-ocean-blue hover:underline inline-flex items-center gap-0.5"
                        >
                          Original source
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-ocean-muted">
                  No source record registered for this incident.
                </p>
              )}
            </div>

            <div>
              <h4 className="text-xs font-semibold text-ocean-midnight uppercase tracking-wider mb-2">
                Field-level provenance
              </h4>
              <FieldProvenanceTable
                provenance={detail.field_provenance ?? {}}
              />
            </div>

            <button onClick={onSelect} className="btn-secondary text-xs w-full">
              <ArrowLeft className="w-3.5 h-3.5 rotate-180" />
              Center map on this incident
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] text-ocean-muted uppercase tracking-wide mb-0.5">
        {label}
      </dt>
      <dd className="text-ocean-slate leading-snug">{value}</dd>
    </div>
  );
}

function quantityLabel(
  detail: HistoricalIncidentDetail,
): string {
  if (detail.quantity_min == null && detail.quantity_max == null) {
    return "Not available";
  }
  const parts: string[] = [];
  if (detail.quantity_min != null) parts.push(String(detail.quantity_min));
  if (detail.quantity_max != null) parts.push(String(detail.quantity_max));
  const unit = detail.quantity_unit ? ` ${detail.quantity_unit}` : "";
  const status =
    detail.quantity_status && detail.quantity_status !== "not_reported"
      ? ` (${detail.quantity_status})`
      : "";
  return `${parts.join(" – ")}${unit}${status}`;
}

function FieldProvenanceTable({
  provenance,
}: {
  provenance: Record<string, HistoricalFieldProvenanceEntry[]>;
}) {
  const entries = Object.entries(provenance);
  if (entries.length === 0) {
    return (
      <p className="text-[11px] text-ocean-muted">
        No field-level provenance recorded.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {entries.slice(0, 12).map(([field, sources]) => (
        <li key={field} className="text-[11px]">
          <span className="font-mono text-ocean-slate">{field}:</span>{" "}
          <span className="text-ocean-muted">
            {sources.map((s) => s.source_value ?? "—").filter(Boolean).join(", ") ||
              "recorded"}
            {sources[0]?.organization ? ` · ${sources[0].organization}` : ""}
          </span>
        </li>
      ))}
      {entries.length > 12 && (
        <li className="text-[10px] text-ocean-muted">
          +{entries.length - 12} more fields with provenance
        </li>
      )}
    </ul>
  );
}
