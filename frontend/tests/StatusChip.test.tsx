import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusChip from "@/components/StatusChip";

describe("StatusChip", () => {
  it("renders a completed status with success styling", () => {
    render(<StatusChip status="completed" />);
    const chip = screen.getByText("completed");
    expect(chip).toHaveClass("chip-success");
  });

  it("renders a failed status with critical styling", () => {
    render(<StatusChip status="failed" />);
    const chip = screen.getByText("failed");
    expect(chip).toHaveClass("chip-critical");
  });

  it("renders a processing status with warning styling", () => {
    render(<StatusChip status="processing" />);
    const chip = screen.getByText("processing");
    expect(chip).toHaveClass("chip-warning");
  });

  it("falls back to default styling for unknown statuses", () => {
    render(<StatusChip status="mystery_status" />);
    const chip = screen.getByText("mystery status");
    expect(chip).toHaveClass("chip-default");
  });
});