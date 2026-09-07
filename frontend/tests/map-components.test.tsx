import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import MapLayerPanel from "@/components/map/MapLayerPanel";
import MapTimeline from "@/components/map/MapTimeline";
import EvidencePanel from "@/components/map/EvidencePanel";
import MaritimeMap from "@/components/map/MaritimeMap";
import {
  layersWithArea,
  layerInfo,
  mapSummary,
  featureStateReady,
  emptyProvenance,
  emptySarOverlay,
  summaryWithoutGeometry,
} from "./map-test-data";

describe("MapLayerPanel", () => {
  it("groups layers by category and shows honest unavailable reasons", () => {
    render(
      <MapLayerPanel
        layers={layersWithArea()}
        visibility={{ investigation_area: true }}
        onToggle={() => {}}
        opacities={{ sar_raster: 1 }}
        onOpacity={() => {}}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
      />,
    );
    // Category headings
    expect(screen.getByText("Context")).toBeInTheDocument();
    expect(screen.getByText("Detection")).toBeInTheDocument();
    expect(screen.getByText("Vessels")).toBeInTheDocument();
    // Ready layer count is honest (1 of 4 ready)
    expect(screen.getByText("1 ready")).toBeInTheDocument();
    // Unavailable layers carry their real reason
    expect(
      screen.getByText("Detection has not been executed."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("SAR imagery (Sentinel-1 GeoTIFF) has not been registered."),
    ).toBeInTheDocument();
  });

  it("disables toggles for unavailable layers and enables them for ready layers", () => {
    render(
      <MapLayerPanel
        layers={layersWithArea()}
        visibility={{ investigation_area: true }}
        onToggle={() => {}}
        opacities={{ sar_raster: 1 }}
        onOpacity={() => {}}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
      />,
    );
    const readyToggle = screen.getByRole("button", {
      name: "Show or hide Investigation Area",
    });
    expect(readyToggle).toBeEnabled();
    const detectionToggle = screen.getByRole("button", {
      name: "Layer unavailable AI-Predicted Oil Boundary",
    });
    expect(detectionToggle).toBeDisabled();
  });

  it("fires visibility toggles for real layers", () => {
    const onToggle = vi.fn();
    render(
      <MapLayerPanel
        layers={[layerInfo("investigation_area", "Investigation Area", "Context", "vector", "ready")]}
        visibility={{ investigation_area: true }}
        onToggle={onToggle}
        opacities={{}}
        onOpacity={() => {}}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Show or hide Investigation Area" }),
    );
    expect(onToggle).toHaveBeenCalledWith("investigation_area");
  });

  it("updates opacity for a ready raster layer", () => {
    const onOpacity = vi.fn();
    const sar = layerInfo(
      "sar_raster",
      "Sentinel-1 SAR Source",
      "Satellite",
      "raster",
      "ready",
    );
    render(
      <MapLayerPanel
        layers={[sar]}
        visibility={{ sar_raster: true }}
        onToggle={() => {}}
        opacities={{ sar_raster: 1 }}
        onOpacity={onOpacity}
        selectedId={null}
        onSelectLayer={() => {}}
        loading={false}
        error={null}
      />,
    );
    const slider = screen.getByRole("slider", {
      name: "Sentinel-1 SAR Source opacity",
    });
    fireEvent.change(slider, { target: { value: "0.5" } });
    expect(onOpacity).toHaveBeenCalledWith("sar_raster", 0.5);
  });
});

describe("MapTimeline", () => {
  it("disables playback honestly when no time-indexed data exists", () => {
    render(
      <MapTimeline
        range={null}
        disabledReason="No time-indexed data for this case."
      />,
    );
    expect(screen.getByText("No time-indexed data")).toBeInTheDocument();
    const play = screen.getByRole("button", { name: /play timeline/i });
    expect(play).toBeDisabled();
  });
});

describe("EvidencePanel", () => {
  it("shows Not available for genuinely absent optional fields", () => {
    const selected = layerInfo(
      "investigation_area",
      "Investigation Area",
      "Context",
      "vector",
      "ready",
    );
    render(
      <EvidencePanel
        summary={mapSummary()}
        selectedLayer={selected}
        layerFeatures={{ investigation_area: featureStateReady("investigation_area") }}
        provenance={emptyProvenance()}
        onExportGeojson={() => {}}
      />,
    );
    expect(screen.getByText("Case bounding box (SQLite)")).toBeInTheDocument();
    // Observation time and timestamps are null -> Not available
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
  });

  it("shows the honest empty-geography overview", () => {
    render(
      <EvidencePanel
        summary={summaryWithoutGeometry()}
        selectedLayer={null}
        layerFeatures={{}}
        provenance={emptyProvenance()}
      />,
    );
    expect(
      screen.getByText("No geospatial case data registered"),
    ).toBeInTheDocument();
    expect(screen.getByText("Why Layers Are Unavailable")).toBeInTheDocument();
  });
});

describe("MaritimeMap (WebGL fallback)", () => {
  it("shows the accessible fallback instead of a fake map when WebGL is missing", () => {
    render(
      <MaritimeMap
        bounds={null}
        vectorLayers={[]}
        sarOverlay={null}
        showSar={false}
        sarOpacity={1}
        basemapId="ocean"
        initialViewport={null}
        selectedId={null}
      />,
    );
    expect(
      screen.getByText("Interactive map unavailable in this browser"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No geospatial evidence registered/),
    ).toBeInTheDocument();
  });

  it("lists real features and offers GeoJSON export in the fallback", () => {
    const onExport = vi.fn();
    render(
      <MaritimeMap
        bounds={null}
        vectorLayers={[
          {
            id: "investigation_area",
            name: "Investigation Area",
            features: featureStateReady("investigation_area").features as NonNullable<
              ReturnType<typeof featureStateReady>["features"]
            >,
          },
        ]}
        sarOverlay={emptySarOverlay()}
        showSar={false}
        sarOpacity={1}
        basemapId="ocean"
        initialViewport={null}
        selectedId={null}
        onExportGeojson={onExport}
      />,
    );
    const exportButton = screen.getByRole("button", {
      name: "Export GeoJSON",
    });
    fireEvent.click(exportButton);
    expect(onExport).toHaveBeenCalledWith("investigation_area");
  });
});
