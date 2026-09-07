import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

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
    listCases: vi.fn(),
    getSystemStatus: vi.fn(),
    getHealth: vi.fn(),
  };
});

import DashboardPage from "@/app/page";
import StatusPage from "@/app/status/page";
import { listCases, getSystemStatus, getHealth } from "@/lib/api";

// Words that must never appear in the normal user interface (developer-only
// language, per the production-cleanup phase).
const BANNED_PATTERNS = [
  /\bdemo\b/i,
  /\bdummy\b/i,
  /\bmock\b/i,
  /\bfixture\b/i,
  /\bplaceholder\b/i,
  /\bdevelopment\b/i,
  /\btest case\b/i,
  /API key required/i,
  /provider token missing/i,
  /\bfake\b/i,
  /sample spill/i,
  /simulated evidence/i,
];

function assertNoBannedText() {
  const text = document.body.textContent || "";
  for (const pattern of BANNED_PATTERNS) {
    expect(text).not.toMatch(pattern);
  }
}

describe("production UI copy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the dashboard without any developer/test language", async () => {
    vi.mocked(listCases).mockResolvedValue({
      success: true,
      data: [],
      total: 0,
      offset: 0,
      limit: 100,
    });
    render(<DashboardPage />);
    await screen.findByText("Begin a Maritime Analysis");
    assertNoBannedText();
  });

  it("renders the system status page without any developer/test language", async () => {
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
    vi.mocked(getHealth).mockResolvedValue({
      success: true,
      data: { version: "0.1.0" },
    });
    render(<StatusPage />);
    await screen.findByText("All Systems Operational");
    // The honest local-mode label (sidebar, header, status page) must not
    // contain the word "demo".
    expect(screen.getAllByText(/Local Mode/).length).toBeGreaterThan(0);
    assertNoBannedText();
  });
});