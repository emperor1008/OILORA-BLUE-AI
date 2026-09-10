/**
 * Oilora Blue AI — Bounding-box helpers
 *
 * Pure client-side mirror of the backend bounding-box policy
 * (backend/app/validation.py): all four corners must be supplied together,
 * finite, within WGS 84 ranges, and describe a non-degenerate area
 * (min < max on both axes). Keeping this in a dependency-free module makes it
 * unit-testable in isolation and reusable by any map-drawing flow.
 */

export interface BboxCorners {
  bbox_min_lat?: number;
  bbox_min_lon?: number;
  bbox_max_lat?: number;
  bbox_max_lon?: number;
}

export interface BboxFieldError {
  field: string;
  message: string;
}

/** Normalise a drawn/clicked pair into canonical min/max corners. */
export function normalizeCorners(a: number, b: number): [number, number] {
  return [Math.min(a, b), Math.max(a, b)];
}

/**
 * Validate a (possibly partial) bounding box. Returns [] when the box is
 * entirely absent or valid; otherwise a list of field-level errors shaped
 * like the backend's 422 detail for inline rendering.
 */
export function validateBoundingBox(values: BboxCorners): BboxFieldError[] {
  const present = (["bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon"] as const).filter(
    (key) => values[key] != null,
  );
  if (present.length === 0) return [];
  if (present.length !== 4) {
    return [
      {
        field: "bbox",
        message: "All four bounding-box coordinates must be provided together.",
      },
    ];
  }

  const minLat = values.bbox_min_lat as number;
  const minLon = values.bbox_min_lon as number;
  const maxLat = values.bbox_max_lat as number;
  const maxLon = values.bbox_max_lon as number;

  const errors: BboxFieldError[] = [];
  for (const [field, value, min, max] of [
    ["bbox_min_lat", minLat, -90, 90],
    ["bbox_max_lat", maxLat, -90, 90],
    ["bbox_min_lon", minLon, -180, 180],
    ["bbox_max_lon", maxLon, -180, 180],
  ] as [string, number, number, number][]) {
    if (!Number.isFinite(value)) {
      errors.push({ field, message: `${field} must be a finite number.` });
    } else if (value < min || value > max) {
      errors.push({ field, message: `${field} must be between ${min} and ${max}.` });
    }
  }
  if (minLat >= maxLat) {
    errors.push({
      field: "bbox_min_lat",
      message: "Minimum latitude must be less than maximum latitude.",
    });
  }
  if (minLon >= maxLon) {
    errors.push({
      field: "bbox_min_lon",
      message: "Minimum longitude must be less than maximum longitude.",
    });
  }
  return errors;
}