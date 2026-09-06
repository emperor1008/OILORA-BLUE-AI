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
  useParams: () => ({ id: "case-test-1" }),
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
  };
});

import CaseDetailPage from "@/app/cases/[id]/page";
import { getCase } from "@/lib/api";

describe("CaseDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading state while the case is being fetched", () => {
    // Never-resolving promise keeps the page in its initial loading state
    vi.mocked(getCase).mockReturnValue(new Promise(() => {}));

    render(<CaseDetailPage />);
    expect(screen.getByText("Loading investigation...")).toBeInTheDocument();
  });

  it("shows the not-found error state with the request ID when loading fails", async () => {
    const error = Object.assign(new Error("Case retrieval failed"), {
      requestId: "req-xyz789",
    });
    vi.mocked(getCase).mockRejectedValue(error);

    render(<CaseDetailPage />);
    expect(
      await screen.findByText("Investigation Not Found"),
    ).toBeInTheDocument();
    expect(screen.getByText("Case retrieval failed")).toBeInTheDocument();
    expect(
      screen.getByText("Request ID: req-xyz789"),
    ).toBeInTheDocument();
    expect(screen.getByText("Back to Dashboard")).toBeInTheDocument();
  });
});