import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/link", () => ({
  default: ({
    children,
    ...props
  }: {
    children: React.ReactNode;
    [key: string]: unknown;
  }) => <a {...props}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/sources",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    listSources: vi.fn(),
    testSource: vi.fn(),
  };
});

import SourcesPage from "@/app/sources/page";
import { listSources, testSource, SourceInfo } from "@/lib/api";

function makeSource(overrides: Partial<SourceInfo>): SourceInfo {
  return {
    source_id: "sentinel1_cdse",
    source_name: "Sentinel-1 SAR (Copernicus Data Space)",
    organization: "European Space Agency / Copernicus",
    data_category: "satellite_radar",
    documentation_url: "https://documentation.dataspace.copernicus.eu/",
    access_method: "STAC API + authenticated product download",
    authentication_required: true,
    authentication_configured: false,
    authentication_note: "Credentials configured on the backend only.",
    licence: "Copernicus Sentinel Data",
    spatial_coverage: "Global",
    temporal_coverage: "2014 → present",
    refresh_frequency: "Continuous",
    expected_format: "SAFE / GRD GeoTIFF",
    configured_status: "not_verified",
    latest_error_category: "none",
    last_successful_access: null,
    last_failed_access: null,
    last_probe_at: null,
    ...overrides,
  };
}

describe("SourcesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listSources).mockResolvedValue({
      success: true,
      data: [
        makeSource({ source_id: "sentinel1_cdse", configured_status: "authentication_required" }),
        makeSource({
          source_id: "satellite_context_nasa_gibs",
          source_name: "Satellite Context (NASA GIBS)",
          authentication_required: false,
          configured_status: "not_verified",
        }),
        makeSource({
          source_id: "wind_netcdf_grib",
          source_name: "Wind Fields (provider-independent adapter)",
          authentication_required: false,
          configured_status: "local_file_workflow",
        }),
      ],
    });
  });

  it("renders honest statuses without fabricating connectivity", async () => {
    render(<SourcesPage />);
    expect(
      await screen.findByText("Sentinel-1 SAR (Copernicus Data Space)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Authentication required").length).toBeGreaterThan(0);
    expect(screen.getByText("Satellite Context (NASA GIBS)")).toBeInTheDocument();
    expect(screen.getByText("Not verified")).toBeInTheDocument();
    expect(screen.getByText("Local-file workflow")).toBeInTheDocument();
    // No source is ever shown as Connected in this unprobed state.
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
    expect(screen.getAllByText("Test connection")).toHaveLength(3);
  });

  it("shows Connected only after a successful test-connection response", async () => {
    vi.mocked(testSource).mockResolvedValue({
      success: true,
      message: "Source status: connected",
      data: makeSource({
        source_id: "satellite_context_nasa_gibs",
        configured_status: "connected",
        last_successful_access: "2026-09-07T12:00:00.000Z",
      }),
    });

    render(<SourcesPage />);
    await screen.findByText("Satellite Context (NASA GIBS)");
    const buttons = screen.getAllByText("Test connection");
    // Click the GIBS card's button (second in the list).
    buttons[1].click();

    await waitFor(() => {
      expect(screen.getAllByText("Connected")).not.toHaveLength(0);
    });
    expect(testSource).toHaveBeenCalledWith("satellite_context_nasa_gibs");
  });

  it("never renders credential values, only the masked boolean", async () => {
    vi.mocked(listSources).mockResolvedValue({
      success: true,
      data: [
        makeSource({
          source_id: "ocean_currents_copernicus_marine",
          authentication_configured: true,
          configured_status: "authentication_required",
        }),
      ],
    });
    render(<SourcesPage />);
    expect(
      await screen.findByText("Credentials configured on the backend"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/marine-pass|username/i)).not.toBeInTheDocument();
  });
});