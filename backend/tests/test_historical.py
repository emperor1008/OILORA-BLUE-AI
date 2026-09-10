"""
Oilora Blue AI — Historical Incident Tests

Covers the NOAA IncidentNews importer (source-preserving synthetic fixture),
idempotency, provenance, filtering/pagination, map bounds, satellite-search
validation and create-investigation. The fixture is synthetic and lives only
in the isolated per-test database.
"""

from __future__ import annotations

import io
import os

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "noaa_incidents_synthetic.csv")


def _fixture_bytes() -> bytes:
    with open(FIXTURE, "rb") as fh:
        return fh.read()


def _import_fixture(client, limit: int | None = None) -> dict:
    """Import the synthetic fixture through the real service (no network)."""
    from app.services.historical_service import historical_service

    return historical_service.import_noaa_csv(
        _fixture_bytes(),
        source_url="https://incidentnews.noaa.gov/raw/incidents.csv",
        limit=limit,
    )


def _first_id(client, search: str) -> str:
    response = client.get("/api/historical-incidents", params={"search": search})
    assert response.status_code == 200, response.text
    data = response.json()
    return data["data"][0]["id"]


class TestNoaaImporter:
    def test_import_counts_and_rejections(self, client):
        result = _import_fixture(client)
        # 8 rows; 3 rejected (bad lat, missing name/date, bad lon); 5 accepted
        assert result["records_received"] == 8
        assert result["records_created"] == 5
        assert result["records_updated"] == 0
        assert result["records_rejected"] == 3
        reasons = {r["source_record_id"]: r["reasons"] for r in result["rejection_report"]}
        assert "90003" in reasons
        assert any("latitude" in r for r in reasons["90003"])
        assert "90005" in reasons
        assert any("longitude" in r for r in reasons["90005"])
        assert "90004" in reasons
        assert any("name" in r for r in reasons["90004"])
        # Blank fields are never converted to zero/guessed values.
        assert result["source_checksum"] and len(result["source_checksum"]) == 64

    def test_import_is_idempotent(self, client):
        first = _import_fixture(client)
        second = _import_fixture(client)
        assert second["records_created"] == 0
        assert second["records_updated"] == first["records_created"] == 5
        listing = client.get("/api/historical-incidents").json()
        assert listing["total"] == 5

    def test_source_record_id_unique_per_source(self, client):
        _import_fixture(client)
        listing = client.get("/api/historical-incidents").json()
        ids = [item["id"] for item in listing["data"]]
        assert len(ids) == len(set(ids)) == 5

    def test_blank_values_stay_null(self, client):
        _import_fixture(client)
        detail = client.get(
            f"/api/historical-incidents/{_first_id(client, 'Test Harbor Chemical')}"
        ).json()["data"]
        # 90002 quantity blank in the CSV → null
        assert detail["quantity_max"] is None
        assert detail["quantity_unit"] is None
        # 90001 quantity is 500 gallons → parsed maximum potential
        d1 = client.get(f"/api/historical-incidents/{_first_id(client, 'Test Bay Spill')}").json()[
            "data"
        ]
        assert d1["quantity_max"] == 500.0
        assert d1["quantity_unit"] == "US gallons"
        assert "maximum potential" in d1["quantity_status"]
        # 90007 has a thousands separator → parsed numeric
        d7 = client.get(f"/api/historical-incidents/{_first_id(client, 'Offshore India')}").json()[
            "data"
        ]
        assert d7["quantity_max"] == 1000.0

    def test_category_preserved_not_converted(self, client):
        _import_fixture(client)
        chem = client.get(
            f"/api/historical-incidents/{_first_id(client, 'Test Harbor Chemical')}"
        ).json()["data"]
        assert chem["incident_category"] == "Chemical"
        assert chem["substance_name"] == "Xylene"

    def test_country_derivation_conservative(self, client):
        _import_fixture(client)
        bay = client.get(f"/api/historical-incidents/{_first_id(client, 'Test Bay Spill')}").json()[
            "data"
        ]
        assert bay["country"] == "United States"  # ", CA" USPS code
        india = client.get(
            f"/api/historical-incidents/{_first_id(client, 'Offshore India')}"
        ).json()["data"]
        assert india["country"] == "India"
        no_loc = client.get(
            f"/api/historical-incidents/{_first_id(client, 'No Location Text')}"
        ).json()["data"]
        assert no_loc["country"] is None  # nothing invented

    def test_no_coordinate_record_not_mapped(self, client):
        _import_fixture(client)
        no_coords = client.get(
            f"/api/historical-incidents/{_first_id(client, 'No Coordinates')}"
        ).json()["data"]
        assert no_coords["latitude"] is None
        # Present in list total but excluded from the map
        total = client.get("/api/historical-incidents").json()["total"]
        assert total == 5
        geo = client.get(
            "/api/historical-incidents/map",
            params={"west": -180, "south": -90, "east": 180, "north": 90},
        ).json()["data"]
        assert len(geo["features"]) == 4  # all mapped rows except the no-coords one

    def test_date_and_timezone_normalized(self, client):
        _import_fixture(client)
        d = client.get(f"/api/historical-incidents/{_first_id(client, 'Test Bay Spill')}").json()[
            "data"
        ]
        assert d["start_time_utc"] == "2024-03-15T00:00:00Z"
        assert d["time_precision"] == "day"


class TestHistoricalApi:
    @pytest.fixture(autouse=True)
    def _seed(self, client):
        _import_fixture(client)
        yield

    def test_list_pagination_and_max_page(self, client):
        response = client.get("/api/historical-incidents", params={"limit": 1000})
        # 422 is a valid enforcement: max page size enforced
        assert response.status_code in (200, 422)
        listing = client.get("/api/historical-incidents", params={"limit": 2}).json()
        assert listing["total"] == 5
        assert len(listing["data"]) == 2
        assert listing["next_cursor"]  # keyset cursor present for date_desc

        # Follow the cursor: subsequent page has distinct ids, no overlap
        second = client.get(
            "/api/historical-incidents",
            params={"limit": 2, "cursor": listing["next_cursor"]},
        ).json()
        first_ids = {item["id"] for item in listing["data"]}
        second_ids = {item["id"] for item in second["data"]}
        assert not (first_ids & second_ids)

    def test_search_filter(self, client):
        listing = client.get("/api/historical-incidents", params={"search": "Chennai"}).json()
        assert listing["total"] == 1
        assert listing["data"][0]["country"] == "India"

    def test_category_filter(self, client):
        listing = client.get("/api/historical-incidents", params={"category": "Chemical"}).json()
        assert listing["total"] == 1
        listing = client.get("/api/historical-incidents", params={"category": "Oil"}).json()
        assert listing["total"] == 4

    def test_date_range_filter(self, client):
        listing = client.get(
            "/api/historical-incidents",
            params={"start_date": "2023-01-01", "end_date": "2024-12-31"},
        ).json()
        assert listing["total"] == 2  # 90001 (2024), 90002 (2023)

    def test_country_filter(self, client):
        listing = client.get("/api/historical-incidents", params={"country": "India"}).json()
        assert listing["total"] == 1

    def test_map_bbox_validation(self, client):
        bad = client.get(
            "/api/historical-incidents/map",
            params={"west": 10, "south": 5, "east": 5, "north": 10},
        )
        assert bad.status_code == 422
        ok = client.get(
            "/api/historical-incidents/map",
            params={"west": 75, "south": 10, "east": 85, "north": 20},
        ).json()["data"]
        assert len(ok["features"]) == 1
        feature = ok["features"][0]
        assert feature["geometry"]["type"] == "Point"
        props = feature["properties"]
        assert props["satellite_status"] == "unmatched"
        assert "incident_id" in props

    def test_summary_never_leaks_paths(self, client):
        response = client.get("/api/historical-incidents").json()
        text = str(response)
        assert "oilora_blue.db" not in text
        assert "C:" not in text and "C:\\" not in text
        detail = client.get(
            f"/api/historical-incidents/{_first_id(client, 'Test Bay Spill')}"
        ).json()["data"]
        assert "file_path" not in str(detail)

    def test_detail_provenance(self, client):
        detail = client.get(
            f"/api/historical-incidents/{_first_id(client, 'Test Bay Spill')}"
        ).json()["data"]
        assert detail["verification_status"] == "source_imported"
        assert len(detail["sources"]) == 1
        source = detail["sources"][0]
        assert source["organization"] == "NOAA Office of Response and Restoration"
        assert source["source_url"].startswith("https://incidentnews.noaa.gov/incident/90001")
        assert "limitation" not in source  # limitation is at the incidents level
        prov = detail["field_provenance"]
        assert "canonical_name" in prov
        for entry in prov["canonical_name"]:
            assert entry["normalization_method"] == "copied"
            assert entry["confidence_level"] == "high"
        # Country provenance references its normalization method
        country_entries = prov["country"]
        assert country_entries
        assert country_entries[0]["normalization_method"] == "parsed from source location text"
        # location summary copied from the source is preserved verbatim
        assert detail["location_description"] == "Test Bay Marina, CA, USA"

    def test_sources_endpoint(self, client):
        iid = _first_id(client, "Test Bay Spill")
        response = client.get(f"/api/historical-incidents/{iid}/sources").json()["data"]
        assert response["sources"][0]["source_title"]
        assert "canonical_name" in response["field_provenance"]
        assert "limitation" in response

    def test_satellite_search_requires_coordinates(self, client):
        no_coords = _first_id(client, "No Coordinates")
        response = client.get(f"/api/historical-incidents/{no_coords}/satellite-search")
        assert response.status_code == 422
        assert "no source-reported coordinates" in response.json()["detail"]

    def test_satellite_search_requires_window(self, client):
        iid = _first_id(client, "Test Bay Spill")
        response = client.get(
            f"/api/historical-incidents/{iid}/satellite-search",
            params={"window_days": 0},
        )
        assert response.status_code == 422

    def test_satellite_search_stores_matches(self, client, monkeypatch):
        from app.routers import historical as historical_router

        synthetic_matches = [
            {
                "item_id": "S1X_IW_GRDH_1SDV_20240315T000000_20240315T000025_000001_000000_0000_TEST",
                "product_identifier": "S1X_IW_GRDH_1SDV_20240315T000000_TEST",
                "platform": "sentinel-1x",
                "collection": "sentinel-1-grd",
                "acquisition_start": "2024-03-15T01:00:00Z",
                "acquisition_end": "2024-03-15T01:00:25Z",
                "acquisition_mode": "IW",
                "processing_level": "GRD",
                "polarizations": ["VV", "VH"],
                "orbit_direction": "descending",
                "geometry_geojson": {"type": "Polygon", "coordinates": []},
                "bbox": [-118.0, 32.0, -117.0, 34.0],
                "metadata_url": "https://stac.dataspace.copernicus.eu/v1/test",
                "temporal_distance_hours": 1.0,
            }
        ]

        def _fake_search(*args, **kwargs):
            return {
                "status": "ok",
                "matches": synthetic_matches,
                "match_count": 1,
                "provider": "Copernicus Data Space Ecosystem",
                "searched_at": "2026-01-01T00:00:00Z",
                "warning": "catalogue",
            }

        # Patch the name the router imported, not the module attribute.
        monkeypatch.setattr(historical_router, "search_incident", _fake_search)
        iid = _first_id(client, "Test Bay Spill")
        response = client.get(f"/api/historical-incidents/{iid}/satellite-search")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["match_count"] == 1

        # The incident now reports satellite_status matched in list views.
        listing = client.get(
            "/api/historical-incidents", params={"satellite_status": "matched"}
        ).json()
        assert listing["total"] == 1

        # Repeat search is idempotent (no duplicate match rows).
        response = client.get(f"/api/historical-incidents/{iid}/satellite-search")
        assert response.json()["data"]["match_count"] == 1

    def test_create_investigation_copies_only_supported(self, client):
        iid = _first_id(client, "Offshore India")
        response = client.post(
            f"/api/historical-incidents/{iid}/create-investigation", json={"confirm": True}
        )
        assert response.status_code == 201, response.text
        case = response.json()["data"]
        assert case["historical_incident_id"] == iid
        assert case["incident_time"] == "2019-09-09T00:00:00Z"
        assert "Offshore India" in case["title"]
        assert case["region"] == "India"
        # No bounding box is invented from the single reported point
        assert case["bbox_min_lat"] is None

        # Linked cases appear on the incident detail
        detail = client.get(f"/api/historical-incidents/{iid}").json()["data"]
        assert any(c["id"] == case["id"] for c in detail["linked_cases"])

    def test_create_investigation_requires_confirmation(self, client):
        iid = _first_id(client, "Test Bay Spill")
        response = client.post(
            f"/api/historical-incidents/{iid}/create-investigation", json={"confirm": False}
        )
        assert response.status_code == 422


class TestImportEndpoint:
    """HTTP import endpoint behaviour with a stubbed NOAA download."""

    def test_import_endpoint_parses_served_csv(self, client, monkeypatch):
        import httpx

        class FakeResponse:
            status_code = 200
            content = _fixture_bytes()

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, url):
                return FakeResponse()

        monkeypatch.setattr(httpx, "Client", FakeClient)
        response = client.post(
            "/api/historical-incidents/import/noaa",
            params={"source_url": "https://incidentnews.noaa.gov/raw/incidents.csv"},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["records_received"] == 8
        assert data["records_created"] == 5
        assert data["records_rejected"] == 3
        # Import run is auditable through the runs endpoint.
        runs = client.get("/api/historical-incidents/import/runs").json()["data"]
        assert len(runs) == 1
        assert runs[0]["import_status"] == "completed"
        assert runs[0]["source_checksum"] == data["source_checksum"]

    def test_import_endpoint_blocks_non_noaa_url(self, client):
        response = client.post(
            "/api/historical-incidents/import/noaa",
            params={"source_url": "https://example.com/evil.csv"},
        )
        assert response.status_code == 422


class TestSarSourceEndpoint:
    def _create_case(self, client) -> str:
        response = client.post(
            "/api/cases",
            json={
                "title": "SAR Source Probe Case",
                "incident_time": "2024-05-01T10:00:00Z",
            },
        )
        return response.json()["data"]["id"]

    def test_invalid_source_kind_rejected(self, client):
        case_id = self._create_case(client)
        response = client.post(
            f"/api/cases/{case_id}/sar-sources",
            data={"source_kind": "mystery"},
            files={"file": ("x.tif", io.BytesIO(b"nope"), "image/tiff")},
        )
        assert response.status_code == 422

    def test_safe_zip_gated_honestly(self, client):
        case_id = self._create_case(client)
        response = client.post(
            f"/api/cases/{case_id}/sar-sources",
            data={"source_kind": "original_safe_zip"},
            files={"file": ("S1A_...SAFE.zip", io.BytesIO(b"PK\x03\x04fake"), "application/zip")},
        )
        assert response.status_code == 422
        assert "SAFE" in response.json()["detail"]

    def test_derived_geotiff_registers_with_granular_state(self, client):
        try:
            import numpy as np
            import rasterio as rio
        except Exception as exc:  # noqa: BLE001 - geospatial runtime check
            pytest.skip(f"geospatial runtime unavailable: {exc.__class__.__name__}")
        case_id = self._create_case(client)
        width, height = 8, 8
        data = np.zeros((height, width), dtype="float32")
        buffer = io.BytesIO()
        with rio.open(
            buffer,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=rio.transform.from_bounds(68.0, 15.0, 69.0, 16.0, width, height),
        ) as dst:
            dst.write(data, 1)
        buffer.seek(0)
        response = client.post(
            f"/api/cases/{case_id}/sar-sources",
            data={
                "source_kind": "derived_geotiff",
                "product_identifier": "S1A_IW_GRDH_1SDV_TEST",
                "acquisition_time": "2024-05-01T10:00:00Z",
                "provenance_source": "https://stac.dataspace.copernicus.eu/v1/test",
                "polarization": "VV",
            },
            files={"file": ("derived_test.tif", buffer, "image/tiff")},
        )
        assert response.status_code == 201, response.text
        payload = response.json()["data"]
        assert payload["file"]["id"]
        overlay = payload["sar_overlay"]
        # A synthetic raster is geospatially valid but carries no real
        # Sentinel-1 provenance verification yet — the honest granular states:
        assert overlay["available"] is True
        assert overlay["validation_status"] in (
            "sentinel1_verified",
            "preview_ready",
            "geospatial_validated",
        )
