import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Next.js router/link shims for jsdom rendering
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
  };
});

import DashboardPage from "@/app/page";
import { listCases } from "@/lib/api";

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listCases).mockResolvedValue({
      success: true,
      data: [],
      total: 0,
      offset: 0,
      limit: 100,
    });
  });

  it("shows the honest empty state when no investigations exist", async () => {
    render(<DashboardPage />);
    expect(
      await screen.findByText("No Investigations Yet"),
    ).toBeInTheDocument();
    expect(screen.getByText("Start New Investigation")).toBeInTheDocument();
    // All three stat cards (total, completed, in progress) read zero
    expect(screen.getAllByText("0")).toHaveLength(3);
  });

  it("shows the error message and request ID when loading fails", async () => {
    const error = Object.assign(new Error("Backend unreachable"), {
      requestId: "req-abc123",
    });
    vi.mocked(listCases).mockRejectedValue(error);

    render(<DashboardPage />);
    expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
    expect(
      screen.getByText("Request ID: req-abc123"),
    ).toBeInTheDocument();
  });
});