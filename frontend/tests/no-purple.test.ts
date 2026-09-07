import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Guard: the Oilora Blue AI maritime palette must never include purple, violet,
 * magenta or pink tokens (SIH judges explicitly exclude them).
 */
const FORBIDDEN = [
  /\bpurple\b/i,
  /\bviolet\b/i,
  /\bmagenta\b/i,
  /\bfuchsia\b/i,
  /#7c3aed/i,
  /#8b5cf6/i,
  /#a855f7/i,
  /#9333ea/i,
  /#6d28d9/i,
  /#7e22ce/i,
  /#c026d3/i,
  /#d946ef/i,
  /#a21caf/i,
  /#ec4899/i,
  /#db2777/i,
  /#f472b6/i,
  /#be185d/i,
];

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      sourceFiles(full, out);
    } else if (/\.(ts|tsx|js|jsx|css)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe("Maritime palette guard", () => {
  it("introduces no purple, violet, magenta or pink tokens", () => {
    const files = [
      ...sourceFiles(join(process.cwd(), "src")),
      join(process.cwd(), "tailwind.config.js"),
    ];
    expect(files.length).toBeGreaterThan(0);
    const violations: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, "utf-8");
      for (const pattern of FORBIDDEN) {
        if (pattern.test(content)) {
          violations.push(`${file} matched ${pattern}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
