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
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...mod,
    getHealth: vi.fn(),
    getSystemStatus: vi.fn(),
  };
});

import Header from "@/components/Header";
import StatusPage from "@/app/status/page";
import { getHealth, getSystemStatus } from "@/lib/api";

function mockHealthySystem() {
  vi.mocked(getSystemStatus).mockResolvedValue({
    success: true,
    data: {
      backend_status: "healthy",
      database_status: "connected",
      model_available: true,
      model_checksum: null,
      disk_space_gb: 100,
      offline_ready: true,
      app_version: "0.1.0",
      local_demo_mode: true,
    },
  });
}

describe("Header backend indicator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Checking before the first health response arrives", () => {
    vi.mocked(getHealth).mockReturnValue(new Promise(() => {}));
    render(<Header />);
    expect(screen.getByText("Checking…")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });

  it("shows Operational only after a successful health request", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      success: true,
      data: { version: "0.1.0" },
    });
    render(<Header />);
    expect(screen.getByText("Checking…")).toBeInTheDocument();
    expect(await screen.findByText("Operational")).toBeInTheDocument();
    // Never a color-only indicator: visible text + title exist.
    expect(screen.getByTitle("Backend operational")).toBeInTheDocument();
  });

  it("shows Unavailable when the health request fails", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("backend down"));
    render(<Header />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByTitle("Backend unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Operational")).not.toBeInTheDocument();
  });
});

describe("Status page readiness rows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("separates internet connectivity from the API service and backend", async () => {
    mockHealthySystem();
    vi.mocked(getHealth).mockResolvedValue({
      success: true,
      data: { version: "0.1.0" },
    });
    render(<StatusPage />);
    expect(await screen.findByText("All Systems Operational")).toBeInTheDocument();
    expect(screen.getByText("Internet connection")).toBeInTheDocument();
    expect(screen.getByText("API service")).toBeInTheDocument();
    expect(screen.getByText("Detection Model")).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    // Header indicator + API-service row both report Operational.
    expect(screen.getAllByText("Operational").length).toBeGreaterThan(0);
  });

  it("reacts to browser online/offline events independently of the backend", async () => {
    mockHealthySystem();
    vi.mocked(getHealth).mockResolvedValue({
      success: true,
      data: { version: "0.1.0" },
    });
    render(<StatusPage />);
    await screen.findByText("All Systems Operational");

    fireEvent(window, new Event("offline"));
    expect(await screen.findByText("Offline")).toBeInTheDocument();
    expect(screen.getByText("Internet connection")).toBeInTheDocument();
    // API service is unaffected by the browser being offline in this test:
    // both are reported separately.
    expect(screen.getByText("API service")).toBeInTheDocument();

    fireEvent(window, new Event("online"));
    expect(await screen.findByText("Online")).toBeInTheDocument();
  });

  it("shows Unknown (not a green check) when backend data is unavailable", async () => {
    vi.mocked(getSystemStatus).mockRejectedValue(new Error("unreachable"));
    vi.mocked(getHealth).mockResolvedValue({
      success: true,
      data: { version: "0.1.0" },
    });
    render(<StatusPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
    });
    // Backend, database, model and disk cannot be verified: the summary is
    // honest rather than claiming everything is operational.
    expect(screen.getByText("Status Partially Unknown")).toBeInTheDocument();
  });

  it("marks the API service unavailable when the health probe fails", async () => {
    mockHealthySystem();
    vi.mocked(getHealth).mockRejectedValue(new Error("backend down"));
    render(<StatusPage />);
    // The header indicator and the API-service row both report Unavailable.
    await waitFor(() => {
      expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Some Systems Unavailable")).toBeInTheDocument();
  });
});