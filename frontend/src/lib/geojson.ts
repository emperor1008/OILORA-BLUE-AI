/**
 * Oilora Blue AI — Minimal GeoJSON types (RFC 7946 subset used by the map).
 *
 * Deliberately local: avoids a third-party @types dependency for the small
 * surface the workspace consumes. Coordinates are always [longitude, latitude]
 * in WGS 84 for browser-facing data.
 */

export type GeoJSONGeometryType =
  | "Point"
  | "MultiPoint"
  | "LineString"
  | "MultiLineString"
  | "Polygon"
  | "MultiPolygon"
  | "GeometryCollection";

export type GeoJSONPosition = number[];

export interface GeoJSONGeometry {
  type: GeoJSONGeometryType;
  coordinates?: unknown;
  geometries?: GeoJSONGeometry[];
}

export interface GeoJSONFeature {
  type: "Feature";
  id?: string | number;
  geometry: GeoJSONGeometry | null;
  properties: Record<string, unknown> | null;
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

export interface GeoJSONBounds {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface LonLatBounds {
  /** [west, south, east, north] */
  wsen: [number, number, number, number];
}
