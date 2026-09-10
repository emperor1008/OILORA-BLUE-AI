import { describe, it, expect } from "vitest";
import { normalizeCorners, validateBoundingBox } from "@/lib/bbox";

describe("normalizeCorners (map-click / drawn-rectangle input)", () => {
  it("orders two clicked latitudes into min/max", () => {
    expect(normalizeCorners(17.5, 14.2)).toEqual([14.2, 17.5]);
    expect(normalizeCorners(14.2, 17.5)).toEqual([14.2, 17.5]);
  });

  it("orders two clicked longitudes into min/max", () => {
    expect(normalizeCorners(-70, -68.1)).toEqual([-70, -68.1]);
    expect(normalizeCorners(-68.1, -70)).toEqual([-70, -68.1]);
  });

  it("accepts equal corners (caller rejects zero-area separately)", () => {
    expect(normalizeCorners(15, 15)).toEqual([15, 15]);
  });
});

describe("validateBoundingBox (client mirror of backend validation)", () => {
  it("accepts a valid bounding box", () => {
    expect(
      validateBoundingBox({
        bbox_min_lat: 14.0,
        bbox_min_lon: 68.0,
        bbox_max_lat: 16.0,
        bbox_max_lon: 69.0,
      }),
    ).toEqual([]);
  });

  it("rejects reversed latitudes", () => {
    const errors = validateBoundingBox({
      bbox_min_lat: 16.0,
      bbox_min_lon: 68.0,
      bbox_max_lat: 14.0,
      bbox_max_lon: 69.0,
    });
    expect(errors.some((e) => e.field === "bbox_min_lat")).toBe(true);
  });

  it("rejects reversed longitudes", () => {
    const errors = validateBoundingBox({
      bbox_min_lat: 14.0,
      bbox_min_lon: 69.0,
      bbox_max_lat: 16.0,
      bbox_max_lon: 68.0,
    });
    expect(errors.some((e) => e.field === "bbox_min_lon")).toBe(true);
  });

  it("rejects zero-area (equal) boxes", () => {
    const errors = validateBoundingBox({
      bbox_min_lat: 14.0,
      bbox_min_lon: 68.0,
      bbox_max_lat: 14.0,
      bbox_max_lon: 68.0,
    });
    expect(errors.some((e) => e.field === "bbox_min_lat")).toBe(true);
    expect(errors.some((e) => e.field === "bbox_min_lon")).toBe(true);
  });

  it("rejects out-of-range latitudes and longitudes", () => {
    const errors = validateBoundingBox({
      bbox_min_lat: -91,
      bbox_min_lon: -181,
      bbox_max_lat: 91,
      bbox_max_lon: 181,
    });
    const fields = errors.map((e) => e.field);
    expect(fields).toContain("bbox_min_lat");
    expect(fields).toContain("bbox_min_lon");
    expect(fields).toContain("bbox_max_lat");
    expect(fields).toContain("bbox_max_lon");
  });

  it("rejects NaN and Infinity corners", () => {
    expect(
      validateBoundingBox({
        bbox_min_lat: Number.NaN,
        bbox_min_lon: 68,
        bbox_max_lat: 16,
        bbox_max_lon: Number.POSITIVE_INFINITY,
      }).length,
    ).toBeGreaterThan(0);
  });

  it("returns no errors when no box is supplied", () => {
    expect(validateBoundingBox({})).toEqual([]);
  });

  it("requires all four corners together", () => {
    const errors = validateBoundingBox({ bbox_min_lat: 14 });
    expect(errors.some((e) => e.field === "bbox")).toBe(true);
  });
});