"""
Oilora Blue AI — Data Source Registry

Central registry of the official external data sources the platform can use,
with *honest* status derivation:

- ``connected``            — the last real probe of the provider succeeded
- ``authentication_required`` — the source needs credentials and none are
                            configured (or the last probe was rejected)
- ``source_unavailable``   — the last real probe failed (network/timeout/HTTP)
- ``not_configured``       — no access method has been configured
- ``local_file_workflow``  — data is expected as user-registered local files
- ``not_verified``         — never probed successfully and no failure recorded

No source is ever reported ``connected`` without a real probe having succeeded.
Definitions live in code; per-source state (probe results and timestamps)
persists in the ``data_sources`` table. Credential VALUES are never returned —
the API exposes only ``authentication_configured: bool``.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from .. import config
from ..database import get_db

logger = logging.getLogger("oilora_blue.sources")

# ─── Probe / status vocabulary ────────────────────────────────────────
STATUS_CONNECTED = "connected"
STATUS_AUTH_REQUIRED = "authentication_required"
STATUS_UNAVAILABLE = "source_unavailable"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_LOCAL_FILE = "local_file_workflow"
STATUS_NOT_VERIFIED = "not_verified"

ERROR_NONE = "none"
ERROR_TIMEOUT = "timeout"
ERROR_NETWORK = "network"
ERROR_HTTP = "http"
ERROR_AUTHENTICATION = "authentication"

# Probe guardrails: short timeouts so the API never hangs on a provider, and a
# cooldown so /test cannot hammer a provider.
_PROBE_TIMEOUT_SECONDS = 8.0
_FORCED_PROBE_COOLDOWN_SECONDS = 5.0

# Static definitions (code). State columns are managed separately in the DB.
_SOURCE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "source_id": "sentinel1_cdse",
        "source_name": "Sentinel-1 SAR (Copernicus Data Space)",
        "organization": "European Space Agency / Copernicus",
        "data_category": "satellite_radar",
        "documentation_url": "https://documentation.dataspace.copernicus.eu/",
        "access_method": "STAC API + authenticated product download",
        "authentication_required": True,
        "authentication_note": (
            "Catalogue discovery is anonymous via the STAC API; downloading a "
            "product requires Copernicus Data Space credentials configured on "
            "the backend (CDSE_CLIENT_ID / CDSE_CLIENT_SECRET)."
        ),
        "licence": "Copernicus Sentinel Data — free, subject to ESA/Copernicus terms",
        "spatial_coverage": "Global (Sentinel-1)",
        "temporal_coverage": "2014-10-03 → present",
        "refresh_frequency": "Continuous (each new acquisition)",
        "expected_format": "SAFE product / GRD GeoTIFF",
        "probe": {
            "kind": "get",
            "url": "https://stac.dataspace.copernicus.eu/v1/",
            "credential_gate": "cdse",
        },
    },
    {
        "source_id": "satellite_context_nasa_gibs",
        "source_name": "Satellite Context (NASA GIBS)",
        "organization": "NASA Global Imagery Browse Services",
        "data_category": "optical_context",
        "documentation_url": "https://wiki.earthdata.nasa.gov/display/GIBS",
        "access_method": "Keyless WMTS (public imagery)",
        "authentication_required": False,
        "authentication_note": (
            "Public keyless service. Geographic context only — never presented "
            "as Sentinel-1 analytical input. Default layer is the static 2004 "
            "Blue Marble composite."
        ),
        "licence": "NASA — free to use; attribution required",
        "spatial_coverage": "Global",
        "temporal_coverage": "Static 2004 composite (default layer)",
        "refresh_frequency": "Static",
        "expected_format": "WMTS tiles (XYZ raster)",
        "probe": {
            "kind": "get",
            "url": "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml",
            "credential_gate": None,
        },
    },
    {
        "source_id": "ocean_currents_copernicus_marine",
        "source_name": "Ocean Currents (Copernicus Marine)",
        "organization": "Copernicus Marine Service (CMEMS)",
        "data_category": "ocean_physics",
        "documentation_url": "https://data.marine.copernicus.eu/",
        "access_method": "Copernicus Marine Toolbox / authenticated download",
        "authentication_required": True,
        "authentication_note": (
            "Requires a Copernicus Marine account configured on the backend "
            "(COPERNICUS_MARINE_USERNAME / COPERNICUS_MARINE_PASSWORD)."
        ),
        "licence": "CMEMS licence terms — free for research use",
        "spatial_coverage": "Global (0.083° grid)",
        "temporal_coverage": "1993 → present (analysis/forecast)",
        "refresh_frequency": "Daily",
        "expected_format": "NetCDF (uo / vo variables)",
        "probe": {
            "kind": "post",
            "url": "https://identity.marine.copernicus.eu/auth/realms/CDS/protocol/openid-connect/token",
            "credential_gate": "copernicus_marine",
            "form": {"grant_type": "password"},
        },
    },
    {
        "source_id": "wind_netcdf_grib",
        "source_name": "Wind Fields (provider-independent adapter)",
        "organization": "Provider-independent (ERA5, GFS, ECMWF, ...)",
        "data_category": "atmospheric",
        "documentation_url": "",
        "access_method": "Local-file workflow — register NetCDF/GRIB with documented u10/v10",
        "authentication_required": False,
        "authentication_note": (
            "No built-in credential. Users register authentic wind files; the "
            "adapter validates variable names, units and coverage."
        ),
        "licence": "Depends on the registered dataset",
        "spatial_coverage": "Depends on the registered dataset",
        "temporal_coverage": "Depends on the registered dataset",
        "refresh_frequency": "User-managed",
        "expected_format": "NetCDF / GRIB with u10, v10",
        "probe": None,
    },
    {
        "source_id": "ais_local_csv_parquet",
        "source_name": "AIS Records (local files)",
        "organization": "User-authorized AIS provider",
        "data_category": "vessel_ais",
        "documentation_url": "",
        "access_method": "Local-file workflow — register authorized AIS CSV/Parquet",
        "authentication_required": False,
        "authentication_note": (
            "No built-in credential. Users register authorized AIS exports; "
            "redistribution-restricted data must never be committed to Git."
        ),
        "licence": "Depends on the registered dataset",
        "spatial_coverage": "Depends on the registered dataset",
        "temporal_coverage": "Depends on the registered dataset",
        "refresh_frequency": "User-managed",
        "expected_format": "CSV / Parquet (timestamp, lat, lon, MMSI)",
        "probe": None,
    },
    {
        "source_id": "ais_gfw",
        "source_name": "Global Fishing Watch (authorized)",
        "organization": "Global Fishing Watch",
        "data_category": "vessel_ais",
        "documentation_url": "https://globalfishingwatch.org/",
        "access_method": "Authorized API access with backend token",
        "authentication_required": True,
        "authentication_note": (
            "Requires a legitimate GFW token configured on the backend "
            "(GFW_API_TOKEN). GFW does not provide complete worldwide shipping "
            "coverage — coverage caveats are displayed with any result."
        ),
        "licence": "GFW terms — authorized access only; no scraping",
        "spatial_coverage": "GFW coverage (not complete worldwide)",
        "temporal_coverage": "GFW coverage window",
        "refresh_frequency": "User-managed",
        "expected_format": "JSON / GeoJSON (GFW API)",
        "probe": {
            "kind": "get",
            "url": "https://globalfishingwatch.org/api/v2/meta/endpoints",
            "credential_gate": "gfw",
            "headers": {"Authorization": "Bearer {token}"},
        },
    },
]


class SourceRegistry:
    """Provider registry with honest status derivation and safe probes."""

    def __init__(self) -> None:
        self._probe_cache: dict[str, dict[str, Any]] = {}

    # ── Persistence ───────────────────────────────────────────────────

    def seed(self) -> None:
        """Insert or refresh definition rows; preserve state columns."""
        now = datetime.now(UTC).isoformat()
        with get_db() as conn:
            for definition in _SOURCE_DEFINITIONS:
                conn.execute(
                    """INSERT INTO data_sources (
                        source_id, source_name, organization, data_category,
                        documentation_url, access_method, authentication_required,
                        authentication_note, licence, spatial_coverage,
                        temporal_coverage, refresh_frequency, expected_format,
                        configured_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        source_name = excluded.source_name,
                        organization = excluded.organization,
                        data_category = excluded.data_category,
                        documentation_url = excluded.documentation_url,
                        access_method = excluded.access_method,
                        authentication_required = excluded.authentication_required,
                        authentication_note = excluded.authentication_note,
                        licence = excluded.licence,
                        spatial_coverage = excluded.spatial_coverage,
                        temporal_coverage = excluded.temporal_coverage,
                        refresh_frequency = excluded.refresh_frequency,
                        expected_format = excluded.expected_format,
                        updated_at = excluded.updated_at""",
                    (
                        definition["source_id"],
                        definition["source_name"],
                        definition["organization"],
                        definition["data_category"],
                        definition["documentation_url"],
                        definition["access_method"],
                        1 if definition.get("authentication_required") else 0,
                        definition["authentication_note"],
                        definition["licence"],
                        definition["spatial_coverage"],
                        definition["temporal_coverage"],
                        definition["refresh_frequency"],
                        definition["expected_format"],
                        STATUS_NOT_CONFIGURED,
                        now,
                        now,
                    ),
                )

    def _row(self, source_id: str) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM data_sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    # ── Credential presence (masked, never values) ────────────────────

    @staticmethod
    def _credentials_present(gate: str | None) -> bool:
        s = config.settings
        if gate == "cdse":
            return bool(s.CDSE_CLIENT_ID and s.CDSE_CLIENT_SECRET)
        if gate == "copernicus_marine":
            return bool(s.COPERNICUS_MARINE_USERNAME and s.COPERNICUS_MARINE_PASSWORD)
        if gate == "gfw":
            return bool(s.GFW_API_TOKEN)
        return False

    @staticmethod
    def _definition(source_id: str) -> dict[str, Any] | None:
        for definition in _SOURCE_DEFINITIONS:
            if definition["source_id"] == source_id:
                return definition
        return None

    # ── Honest status derivation (no network on read) ─────────────────

    def _derive_status(self, row: dict[str, Any]) -> dict[str, Any]:
        """Derive the honest configured status from stored state + config.

        Never performs network I/O — reads only persisted probe results and
        credential presence so page loads cannot hang on external providers.
        """
        source_id = row["source_id"]
        definition = self._definition(source_id)
        probe = (definition or {}).get("probe")

        # Local-file workflow sources have no provider to probe.
        if probe is None:
            return {
                "configured_status": STATUS_LOCAL_FILE,
                "latest_error_category": ERROR_NONE,
            }

        creds_needed = bool((definition or {}).get("authentication_required"))
        creds = self._credentials_present(probe.get("credential_gate"))
        if creds_needed and not creds:
            return {
                "configured_status": STATUS_AUTH_REQUIRED,
                "latest_error_category": ERROR_AUTHENTICATION,
            }

        last_success = row.get("last_successful_access")
        last_failure = row.get("last_failed_access")
        if last_success and (not last_failure or last_success >= last_failure):
            return {
                "configured_status": STATUS_CONNECTED,
                "latest_error_category": ERROR_NONE,
            }
        if last_failure and (not last_success or last_failure > last_success):
            return {
                "configured_status": STATUS_UNAVAILABLE,
                "latest_error_category": row.get("latest_error_category") or ERROR_HTTP,
            }
        return {
            "configured_status": STATUS_NOT_VERIFIED,
            "latest_error_category": ERROR_NONE,
        }

    # ── Public safe records ───────────────────────────────────────────

    def list_sources(self) -> list[dict[str, Any]]:
        """All registry sources as safe public records (no credential values)."""
        records = []
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM data_sources ORDER BY source_id").fetchall()
        for row in rows:
            d = dict(row)
            records.append(self._public_record(d))
        return records

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        row = self._row(source_id)
        if row is None:
            return None
        return self._public_record(row)

    def _public_record(self, row: dict[str, Any]) -> dict[str, Any]:
        definition = self._definition(row["source_id"]) or {}
        probe = definition.get("probe")
        derived = self._derive_status(row)
        # Mask credential status to a boolean — values never leave the backend.
        gate = probe.get("credential_gate") if probe else None
        return {
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "organization": row["organization"],
            "data_category": row["data_category"],
            "documentation_url": row["documentation_url"],
            "access_method": row["access_method"],
            "authentication_required": bool(row["authentication_required"]),
            "authentication_configured": self._credentials_present(gate),
            "authentication_note": row["authentication_note"],
            "licence": row["licence"],
            "spatial_coverage": row["spatial_coverage"],
            "temporal_coverage": row["temporal_coverage"],
            "refresh_frequency": row["refresh_frequency"],
            "expected_format": row["expected_format"],
            "configured_status": derived["configured_status"],
            "latest_error_category": derived["latest_error_category"],
            "last_successful_access": row["last_successful_access"],
            "last_failed_access": row["last_failed_access"],
            "last_probe_at": row["last_probe_at"],
        }

    # ── Real probes ───────────────────────────────────────────────────

    def probe_source(self, source_id: str, force: bool = False) -> dict[str, Any] | None:
        """Run a real, time-limited probe against the provider (or report why not).

        ``force=True`` bypasses the short cooldown (used by POST /test). Results
        are persisted so GET responses reflect real state. Errors are categorized
        (timeout / network / http / authentication) and technical detail is
        logged server-side only.
        """
        row = self._row(source_id)
        if row is None:
            return None
        definition = self._definition(source_id) or {}
        probe = definition.get("probe")
        now = datetime.now(UTC).isoformat()

        if probe is None:
            # Local-file workflow: nothing to probe, nothing to persist.
            public = self._public_record(row)
            return public

        creds_needed = bool(definition.get("authentication_required"))
        gate = probe.get("credential_gate")
        creds = self._credentials_present(gate)

        if creds_needed and not creds:
            self._persist_probe(source_id, STATUS_AUTH_REQUIRED, None, ERROR_AUTHENTICATION, now)
            return self.get_source(source_id)

        # Cooldown for forced probes (avoid hammering providers).
        if force:
            last_probe = row.get("last_probe_at")
            if last_probe:
                try:
                    last_ts = datetime.fromisoformat(last_probe).timestamp()
                    if time.time() - last_ts < _FORCED_PROBE_COOLDOWN_SECONDS:
                        return self.get_source(source_id)
                except ValueError:
                    pass

        try:
            success, error_category = self._run_probe(probe, gate)
        except Exception as exc:  # noqa: BLE001 - categorize any probe failure
            logger.warning("Source probe failed unexpectedly: source=%s error=%s", source_id, exc)
            success, error_category = False, ERROR_NETWORK

        if success:
            self._persist_probe(source_id, STATUS_CONNECTED, now, ERROR_NONE, now)
        else:
            self._persist_probe(source_id, STATUS_UNAVAILABLE, None, error_category, now)

        return self.get_source(source_id)

    def _run_probe(self, probe: dict[str, Any], gate: str | None) -> tuple[bool, str]:
        """Execute the probe request. Returns (success, error_category)."""
        import httpx

        headers = dict(probe.get("headers") or {})
        if gate == "gfw" and config.settings.GFW_API_TOKEN:
            headers["Authorization"] = f"Bearer {config.settings.GFW_API_TOKEN}"

        data = None
        form = probe.get("form")
        if probe.get("kind") == "post" and gate == "copernicus_marine":
            data = {
                "username": config.settings.COPERNICUS_MARINE_USERNAME,
                "password": config.settings.COPERNICUS_MARINE_PASSWORD,
                **(form or {}),
            }

        try:
            with httpx.Client(timeout=_PROBE_TIMEOUT_SECONDS, follow_redirects=True) as client:
                if probe.get("kind") == "post":
                    response = client.post(probe["url"], data=data, headers=headers)
                else:
                    response = client.get(probe["url"], headers=headers)
        except httpx.TimeoutException:
            return False, ERROR_TIMEOUT
        except httpx.NetworkError:
            return False, ERROR_NETWORK
        except httpx.HTTPError:
            return False, ERROR_NETWORK

        if response.status_code in (200, 204):
            return True, ERROR_NONE
        if response.status_code in (401, 403):
            logger.warning(
                "Source probe rejected: source=%s status=%s", probe.get("url"), response.status_code
            )
            return False, ERROR_AUTHENTICATION
        logger.warning("Source probe returned HTTP %s: %s", response.status_code, probe.get("url"))
        return False, ERROR_HTTP

    def _persist_probe(
        self,
        source_id: str,
        status: str,
        success_at: str | None,
        error_category: str,
        probe_at: str,
    ) -> None:
        with get_db() as conn:
            if success_at:
                conn.execute(
                    """UPDATE data_sources SET configured_status = ?,
                       last_successful_access = ?, last_failed_access = NULL,
                       latest_error_category = ?, last_probe_at = ?, updated_at = ?
                       WHERE source_id = ?""",
                    (status, success_at, error_category, probe_at, probe_at, source_id),
                )
            else:
                conn.execute(
                    """UPDATE data_sources SET configured_status = ?,
                       last_failed_access = ?, latest_error_category = ?,
                       last_probe_at = ?, updated_at = ? WHERE source_id = ?""",
                    (status, probe_at, error_category, probe_at, probe_at, source_id),
                )


source_registry = SourceRegistry()


def seed_source_registry() -> None:
    """Seed the registry (called from init_database)."""
    source_registry.seed()
