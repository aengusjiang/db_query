/** Unit tests for query result export helpers. */

import { describe, it, expect } from "vitest";

import type { QueryResult } from "../types/query";
import {
  buildExportFilename,
  sanitizeFilename,
  toCsv,
  toJson,
} from "./export";

function makeResult(overrides: Partial<QueryResult> = {}): QueryResult {
  return {
    columns: [
      { name: "id", dataType: "integer" },
      { name: "name", dataType: "character varying" },
    ],
    rows: [
      { id: 1, name: "Alice" },
      { id: 2, name: "Bob" },
    ],
    rowCount: 2,
    executionTimeMs: 12,
    sql: "SELECT id, name FROM users",
    ...overrides,
  };
}

describe("toCsv", () => {
  it("prepends the UTF-8 BOM so Excel opens CJK text without mojibake", () => {
    const csv = toCsv(makeResult());
    expect(csv.charCodeAt(0)).toBe(0xfeff);
  });

  it("writes the header row followed by one row per record", () => {
    const csv = toCsv(makeResult());
    const lines = csv.slice(1).split("\r\n");
    expect(lines[0]).toBe("id,name");
    expect(lines[1]).toBe("1,Alice");
    expect(lines[2]).toBe("2,Bob");
  });

  it("escapes commas, quotes and newlines per RFC 4180", () => {
    const csv = toCsv(
      makeResult({
        columns: [{ name: "note", dataType: "text" }],
        rows: [{ note: 'has "quotes", commas\nand newline' }],
        rowCount: 1,
      })
    );
    expect(csv.slice(1)).toContain('"has ""quotes"", commas');
    expect(csv.slice(1)).toContain('and newline"');
  });

  it("quote-guards formula-looking strings but leaves numbers untouched", () => {
    const csv = toCsv(
      makeResult({
        columns: [
          { name: "formula", dataType: "text" },
          { name: "delta", dataType: "integer" },
        ],
        rows: [{ formula: "=SUM(A1:A9)", delta: -5 }],
        rowCount: 1,
      })
    );
    expect(csv).toContain("'=SUM(A1:A9)");
    expect(csv).toContain(",-5");
    expect(csv).not.toContain("'-5");
  });

  it("renders null and undefined cells as empty strings", () => {
    const csv = toCsv(
      makeResult({
        rows: [{ id: 1, name: null }],
        rowCount: 1,
      })
    );
    expect(csv.slice(1)).toContain("1,");
  });

  it("keeps CJK cell values verbatim", () => {
    const csv = toCsv(
      makeResult({
        rows: [{ id: 1, name: "张伟" }],
        rowCount: 1,
      })
    );
    expect(csv).toContain("1,张伟");
  });

  it("escapes header names containing commas and formula prefixes", () => {
    const csv = toCsv(
      makeResult({
        columns: [
          { name: "total,USD", dataType: "integer" },
          { name: "=SUM(x)", dataType: "text" },
        ],
        rows: [{ "total,USD": 1, "=SUM(x)": "a" }],
        rowCount: 1,
      })
    );
    expect(csv.slice(1).split("\r\n")[0]).toBe("\"total,USD\",'=SUM(x)");
  });

  it("emits a final CRLF terminator, matching the backend csv.writer", () => {
    const csv = toCsv(makeResult());
    expect(csv.endsWith("\r\n")).toBe(true);
    expect(toCsv(makeResult({ rows: [], rowCount: 0 })).slice(1)).toBe(
      "id,name\r\n"
    );
  });
});

describe("toJson", () => {
  it("serializes rows as a pretty-printed array", () => {
    const json = toJson(makeResult());
    expect(JSON.parse(json)).toEqual([
      { id: 1, name: "Alice" },
      { id: 2, name: "Bob" },
    ]);
    expect(json).toContain("\n");
  });

  it("keeps CJK characters unescaped", () => {
    const json = toJson(
      makeResult({ rows: [{ id: 1, name: "张伟" }], rowCount: 1 })
    );
    expect(json).toContain("张伟");
  });

  it("returns [] for an empty result set", () => {
    expect(toJson(makeResult({ rows: [], rowCount: 0 }))).toBe("[]");
  });
});

describe("sanitizeFilename", () => {
  it("keeps safe characters", () => {
    expect(sanitizeFilename("interview-db")).toBe("interview-db");
    expect(sanitizeFilename("test_db")).toBe("test_db");
  });

  it("strips path separators and spaces", () => {
    expect(sanitizeFilename("my db/../evil")).toBe("mydbevil");
  });

  it("falls back to 'export' when nothing safe remains", () => {
    expect(sanitizeFilename("///")).toBe("export");
    expect(sanitizeFilename("数据")).toBe("export");
  });
});

describe("buildExportFilename", () => {
  it("produces <name>_<timestamp>.<ext> with a compact UTC stamp", () => {
    expect(buildExportFilename("sample-hr", "json")).toMatch(
      /^sample-hr_\d{8}T\d{6}\.json$/
    );
    expect(buildExportFilename("my db", "csv")).toMatch(
      /^mydb_\d{8}T\d{6}\.csv$/
    );
  });
});
