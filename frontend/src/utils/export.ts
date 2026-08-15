/**
 * Query result export helpers (CSV / JSON client-side download).
 *
 * Pure formatting functions plus a small DOM download helper, mirroring
 * `backend/app/services/exporter.py` so UI-side and server-side exports
 * produce byte-compatible files.
 */

import type { QueryResult } from "../types/query";

/** UTF-8 BOM so Excel auto-detects the encoding (CJK-safe). */
const CSV_BOM = "﻿";

/** OWASP CSV injection guidance: quote-prefix string cells starting with these. */
const FORMULA_PREFIXES = ["=", "+", "-", "@", "\t", "\r"] as const;

/**
 * Render one cell per RFC 4180: null becomes "", string values that look like
 * spreadsheet formulas get a `'` guard prefix, and cells containing commas,
 * quotes or newlines are quoted with doubled quotes.
 *
 * Numbers keep their native text so `-5` stays a usable number in Excel.
 */
function escapeCsvCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  let text = String(value);
  if (typeof value === "string" && FORMULA_PREFIXES.some((p) => text.startsWith(p))) {
    text = `'${text}`;
  }
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

/** Serialize a QueryResult to CSV (BOM + header + rows, CRLF line endings). */
export function toCsv(result: QueryResult): string {
  const headers = result.columns.map((col) => col.name);
  const lines = [headers.map(escapeCsvCell).join(",")];
  for (const row of result.rows) {
    lines.push(headers.map((header) => escapeCsvCell(row[header])).join(","));
  }
  return CSV_BOM + lines.join("\r\n") + "\r\n";
}

/** Serialize QueryResult rows to pretty-printed JSON. */
export function toJson(result: QueryResult): string {
  return JSON.stringify(result.rows, null, 2);
}

/** Reduce a connection name to a filename-safe token (fallback: "export"). */
export function sanitizeFilename(databaseName: string): string {
  const token = databaseName.replace(/[^A-Za-z0-9_-]/g, "");
  return token || "export";
}

/** Build `<name>_<UTC timestamp>.<ext>`, e.g. `interview-db_20260814T160153.csv`. */
export function buildExportFilename(
  databaseName: string,
  format: "csv" | "json"
): string {
  const timestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .slice(0, 15); // 2026-08-14T16:01:53Z -> 20260814T160153
  return `${sanitizeFilename(databaseName)}_${timestamp}.${format}`;
}

/** Trigger a browser download of `content` as `filename`. */
export function downloadBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
