import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { resolveBasemap, BASEMAP_MAX_ZOOM } from "@/components/map/MaritimeMap";
import MapToolbar from "@/components/map/MapToolbar";
import MapLayerPanel from "@/components/map/MapLayerPanel";
import { layerInfo } from "./map-test-data";

describe("resolveBasemap (basemap provider configuration)", () => {
  it("resolves Ocean / Street to the legal CARTO/OSM source with attribution", () => {
    const cfg = resolveBasemap("ocean", false);
    expect(cfg.url).toContain("basemaps.cartocdn.com");
    expect(cfg.attribution).toContain("OpenStreetMap");
    expect(cfg.attribution).toContain("CARTO");
    expect(cfg.maxZoom).toBe(BASEMAP_MAX_ZOOM.ocean);
  });

  it("resolves Satellite Context to the keyless NASA GIBS source with attribution", () => {
    const cfg = resolveBasemap("satellite", false);
    expect(cfg.url).toContain("gibs.earthdata.nasa.gov");
    expect(cfg.url).toContain("BlueMarble_NextGeneration");
    // No API key may be embedded in the tile URL.
    expect(cfg.url).not.toMatch(/[?&](key|token|apikey|access_token)=/i);
    expect(cfg.attribution).toContain("NASA");
    expect(cfg.maxZoom).toBe(8);
  });

  it("makes no external tile request in Minimal / Offline mode", () => {
    for (const offline of [true, false]) {
      const cfg = resolveBasemap("minimal", offline);
      expect(cfg.url).toBeNull();
      expect(cfg.attribution).toBe("");
    }
    // Offline overrides even an online basemap selection.
    expect(resolveBasemap("ocean", true).url).toBeNull();
    expect(resolveBasemap("satellite", true).url).toBeNull();
  });

  it("never exceeds the GIBS maximum useful zoom for satellite context", () => {
    // GIBS BlueMarble_NextGeneration serves zoom 0-8 (GoogleMapsCompatible_Level8).
    expect(BASEMAP_MAX_ZOOM.satellite).toBe(8);
    expect(BASEMAP_MAX_ZOOM.ocean).toBeGreaterThan(BASEMAP_MAX_ZOOM.satellite);
  });
});

describe("MapToolbar satellite context", () => {
  const baseProps = {
    basemapId: "ocean" as const,
    onBasemapChange: vi.fn(),
    satelliteAvailable: true,
    canExport: false,
  };

  it("keeps Satellite Context selectable when the legal provider is configured", () => {
    render(<MapToolbar {...baseProps} />);
    const button = screen.getByRole("button", { name: /Satellite Context/i });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(baseProps.onBasemapChange).toHaveBeenCalledWith("satellite");
  });

  it("explains in the tooltip that satellite context is not the Sentinel-1 SAR input", () => {
    render(<MapToolbar {...baseProps} />);
    const button = screen.getByRole("button", { name: /Satellite Context/i });
    expect(button.getAttribute("title")).toContain(
      "This layer is not the Sentinel-1 SAR image used for oil-spill analysis.",
    );
    expect(button.getAttribute("title")).toContain("Optical satellite context");
  });

  it("does not label the satellite layer as live imagery", () => {
    render(<MapToolbar {...baseProps} />);
    const text = document.body.textContent || "";
    expect(text).not.toMatch(/Live Satellite/i);
  });
});

describe("MapLayerPanel SAR source empty state", () => {
  it("shows the honest SAR-not-registered state with a register action", () => {
    const onRegisterSar = vi.fn();
    const sar = layerInfo(
      "sar_raster",
      "Sentinel-1 SAR Source",
      "Satellite",
      "raster",
      "missing_input",
      "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
    );
    render(
      <MapLayerPanel
        layers={[sar]}
        visibility={{}}
        onToggle={() => {}}
        opacities={{}}
        onOpacity={() => {}}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
        onRegisterSar={onRegisterSar}
      />,
    );
    expect(
      screen.getByText("Sentinel-1 SAR source not registered"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Register an authentic georeferenced Sentinel-1 raster to create an analytical overlay.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Register SAR File" }));
    expect(onRegisterSar).toHaveBeenCalledTimes(1);
  });

  it("does not render a fake SAR layer when the source is missing", () => {
    const sar = layerInfo(
      "sar_raster",
      "Sentinel-1 SAR Source",
      "Satellite",
      "raster",
      "missing_input",
      "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
    );
    render(
      <MapLayerPanel
        layers={[sar]}
        visibility={{}}
        onToggle={() => {}}
        opacities={{}}
        onOpacity={() => {}}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
      />,
    );
    // Layer row is disabled (no visibility toggle) and explains the gap.
    expect(
      screen.getByLabelText("Layer unavailable Sentinel-1 SAR Source"),
    ).toBeDisabled();
    expect(
      screen.getByText("SAR imagery (Sentinel-1 GeoTIFF) has not been registered."),
    ).toBeInTheDocument();
  });
});