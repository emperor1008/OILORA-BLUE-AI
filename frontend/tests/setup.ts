import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount rendered trees between tests (no vitest globals configured).
afterEach(() => {
  cleanup();
});

// jsdom has no real WebGL implementation. Force canvas contexts to null so the
// MaritimeMap component deterministically renders its accessible, honest
// fallback in unit tests instead of attempting MapLibre initialisation.
const canvasProto = HTMLCanvasElement.prototype as unknown as {
  getContext?: (...args: unknown[]) => unknown;
};
canvasProto.getContext = function getContext(): unknown {
  return null;
};

// jsdom has no matchMedia. Default to mobile-ish viewports (matches: false) so
// drawer behaviour is exercised in modal mode; individual tests can override
// the returned matches value before rendering.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
