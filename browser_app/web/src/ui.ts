// Small DOM helpers shared by the AI tool and the Basic tool.
import { downloadCsv } from "./csv";
import type { Table } from "./duck";

export function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

export const fmtCell = (v: unknown) => typeof v === "number"
  ? (Number.isInteger(v) ? v.toLocaleString() : Number(v.toPrecision(4)).toLocaleString())
  : escapeHtml(String(v ?? ""));

/** A result block: title, notes, a table of the first `limit` rows and a CSV button with all rows. */
export function resultBlock(t: Table, title: string, csvName: string, notes: string[] = [], limit = 200,
                            labels: Record<string, string> = {}): HTMLDivElement {
  const d = document.createElement("div");
  d.className = "result";
  const shown = t.rows.slice(0, limit);
  d.innerHTML = `<h3><span>${escapeHtml(title)} <small>(${t.rows.length} rows)</small></span><button class="secondary">CSV</button></h3>
    ${notes.map((n) => `<p class="note">${escapeHtml(n)}</p>`).join("")}
    <div style="overflow:auto"><table><thead><tr>${t.columns.map((c) => `<th title="${escapeHtml(c)}">${escapeHtml(labels[c] ?? c)}</th>`).join("")}</tr></thead>
    <tbody>${shown.map((row) => `<tr>${t.columns.map((c) => `<td class="${typeof row[c] === "number" ? "num" : ""}">${fmtCell(row[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    ${t.rows.length > shown.length ? `<p class="note">First ${shown.length} rows shown; the CSV has all ${t.rows.length}.</p>` : ""}`;
  d.querySelector("button")!.onclick = () => downloadCsv(csvName, t.columns, t.rows);
  return d;
}
