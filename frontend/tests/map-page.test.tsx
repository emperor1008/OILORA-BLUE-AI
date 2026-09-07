import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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
  usePathname: () => "/",
  useParams: () => ({ id: "case-map-1" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    getCase: vi.fn(),
    uploadFile: vi.fn(),
    listFiles: vi.fn(),
    deleteCase: vi.fn(),
    getMapSummary: vi.fn(),
    getMapLayers: vi.fn(),
    getMapFeatures: vi.fn(),
    getMapViewport: vi.fn(),
    getSarOverlay: vi.fn(),
    getMapProvenance: vi.fn(),
    saveMapViewport: vi.fn(),
  };
});

import CaseDetailPage from "@/app/cases/[id]/page";
import {
  getCase,
  getMapSummary,
  getMapLayers,
  getMapFeatures,
  getMapViewport,
  getSarOverlay,
  getMapProvenance,
} from "@/lib/api";
import {
  caseDetail,
  mapSummary,
  summaryWithoutGeometry,
  layersWithArea,
  featureStateReady,
  emptyViewport,
  emptySarOverlay,
  emptyProvenance,
} from "./map-test-data";

function mockMapEndpoints(overrides: {
  summary?: ReturnType<typeof mapSummary>;
  layers?: ReturnType<typeof layersWithArea>;
  features?: boolean;
} = {}) {
  vi.mocked(getMapSummary).mockResolvedValue({
    success: true,
    data: overrides.summary ?? mapSummary(),
  });
  vi.mocked(getMapLayers).mockResolvedValue({
    success: true,
    data: { case_id: "case-map-1", layers: overrides.layers ?? layersWithArea() },
  });
  if (overrides.features === false) {
    vi.mocked(getMapFeatures).mockResolvedValue({
      success: true,
      data: { case_id: "case-map-1", layers: {} },
    });
  } else {
    vi.mocked(getMapFeatures).mockResolvedValue({
      success: true,
      data: {
        case_id: "case-map-1",
        layers: { investigation_area: featureStateReady("investigation_area") },
      },
    });
  }
  vi.mocked(getMapViewport).mockResolvedValue({
    success: true,
    data: emptyViewport(),
  });
  vi.mocked(getSarOverlay).mockResolvedValue({
    success: true,
    data: emptySarOverlay(),
  });
  vi.mocked(getMapProvenance).mockResolvedValue({
    success: true,
    data: emptyProvenance(),
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getCase).mockResolvedValue({
    success: true,
    data: caseDetail(),
  });
  mockMapEndpoints();
});

describe("Investigation Workspace (map)", () => {
  it("renders an honest empty state when no geospatial case data exists", async () => {
    mockMapEndpoints({ summary: summaryWithoutGeometry(), features: false });
    render(<CaseDetailPage />);
    const emptyStates = await screen.findAllByText(
      "No geospatial case data registered",
    );
    expect(emptyStates.length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Register a genuine SAR, boundary or AIS file/),
    ).toBeInTheDocument();
  });

  it("displays map errors with their request ID and keeps the workspace usable", async () => {
    const error = Object.assign(new Error("Backend unreachable"), {
      requestId: "req-map-error-1",
    });
    vi.mocked(getMapSummary).mockRejectedValue(error);
    render(<CaseDetailPage />);
    expect(
      await screen.findByText("Map data could not be loaded"),
    ).toBeInTheDocument();
    const errorMessages = screen.getAllByText("Backend unreachable");
    expect(errorMessages.length).toBeGreaterThan(0);
    expect(
      screen.getByText("Request ID: req-map-error-1"),
    ).toBeInTheDocument();
  });

  it("shows the timeline disabled without time-indexed data", async () => {
    render(<CaseDetailPage />);
    expect(await screen.findByText("No time-indexed data")).toBeInTheDocument();
    const play = screen.getByRole("button", { name: /play timeline/i });
    expect(play).toBeDisabled();
  });

  it("opens the layer panel drawer on smaller viewports", async () => {
    render(<CaseDetailPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    // Backdrop with close action only renders while the drawer is open
    const backdrop = screen.getByRole("button", { name: "Close layer panel" });
    expect(backdrop).toBeInTheDocument();
  });

  it("selects a real layer and surfaces its evidence with Not available fields", async () => {
    render(<CaseDetailPage />);
    // The layer drawer is inert while closed; open it first (closed drawers
    // must not be keyboard-reachable or exposed to assistive technology).
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    const inspect = await screen.findByRole("button", {
      name: "Inspect Investigation Area",
    });
    fireEvent.click(inspect);
    expect(
      await screen.findByText("Case bounding box (SQLite)"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
    });
  });

  it("keeps unavailable layers clearly disabled with reasons", async () => {
    render(<CaseDetailPage />);
    // Open the (inert-while-closed) layer drawer to inspect its contents.
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    const reasons = await screen.findAllByText(
      "Detection has not been executed.",
    );
    expect(reasons.length).toBeGreaterThan(0);
    const disabledToggle = screen.getByRole("button", {
      name: "Layer unavailable AI-Predicted Oil Boundary",
    });
    expect(disabledToggle).toBeDisabled();
  });
});

describe("Investigation Workspace (drawer accessibility)", () => {
  function renderWorkspace() {
    const view = render(<CaseDetailPage />);
    return view.container as HTMLElement;
  }

  function drawers(container: HTMLElement) {
    const asides = Array.from(container.querySelectorAll("aside"));
    const right =
      asides.find((el) =>
        el.querySelector('[aria-label="Close evidence drawer"]'),
      ) ?? null;
    const left =
      asides.find((el) => el.querySelector('[aria-label="Close panel"]')) ??
      null;
    return { left, right };
  }

  it("closed drawers are inert and aria-hidden (not keyboard-reachable)", async () => {
    const container = renderWorkspace();
    await screen.findByText("No time-indexed data");
    const { left, right } = drawers(container);
    expect(left).not.toBeNull();
    expect(right).not.toBeNull();
    if (left) {
      expect(left.hasAttribute("inert")).toBe(true);
      expect(left.getAttribute("aria-hidden")).toBe("true");
      // The inert attribute is what removes descendants from the tab order;
      // verify at least one focusable element exists inside the closed drawer.
      const focusables = Array.from(
        left.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea',
        ),
      );
      expect(focusables.length).toBeGreaterThan(0);
    }
    if (right) {
      expect(right.hasAttribute("inert")).toBe(true);
      expect(right.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("removes inert from the open drawer so it becomes focusable", async () => {
    const container = renderWorkspace();
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    await screen.findByRole("button", { name: "Close layer panel" });
    const { left } = drawers(container);
    if (left) {
      expect(left.hasAttribute("inert")).toBe(false);
      expect(left.getAttribute("aria-hidden")).toBe("false");
    }
  });

  it("Escape closes the open drawer and restores focus to the trigger", async () => {
    const container = renderWorkspace();
    const trigger = await screen.findByRole("button", { name: "Open layer panel" });
    // Browsers focus buttons on mousedown; jsdom does not, so focus explicitly
    // so the drawer remembers the correct trigger for restoration.
    trigger.focus();
    fireEvent.click(trigger);
    await screen.findByRole("button", { name: "Close layer panel" });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close panel" }),
    );

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => {
      const { left } = drawers(container);
      expect(left?.hasAttribute("inert")).toBe(true);
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("the evidence panel X button closes the right drawer", async () => {
    const container = renderWorkspace();
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Inspect Investigation Area" }),
    );
    const { right } = drawers(container);
    expect(right?.hasAttribute("inert")).toBe(false);

    fireEvent.click(
      await screen.findByRole("button", { name: "Close evidence drawer" }),
    );
    await waitFor(() => {
      expect(right?.hasAttribute("inert")).toBe(true);
    });
  });

  it("the backdrop closes the drawer", async () => {
    const container = renderWorkspace();
    fireEvent.click(
      await screen.findByRole("button", { name: "Open layer panel" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Close layer panel" }),
    );
    const { left } = drawers(container);
    await waitFor(() => {
      expect(left?.hasAttribute("inert")).toBe(true);
    });
  });
});
