// SQL guard for queries the LLM writes. The country's rows are pre-loaded into local tables
// (adm0/1/2_hazard, adm0/1/2_pop), so a query only needs SELECT over those tables. Anything that
// reads files or URLs, changes state or loads code is refused.

export const QUERY_TABLES = ["adm0_hazard", "adm1_hazard", "adm2_hazard", "adm0_pop", "adm1_pop", "adm2_pop"] as const;

const FORBIDDEN = [
  /\b(attach|detach|copy|export|import|install|load|pragma|set|reset|call|create|drop|alter|insert|update|delete|truncate|vacuum|checkpoint|begin|commit|rollback|use|prepare|execute)\b/i,
  /\b(read_\w+|glob|parquet_\w+|sniff_csv|getenv|current_setting|duckdb_\w+|query_table|query)\s*\(/i,
];
// checked on the query with its string literals kept: URLs and file names
const FORBIDDEN_LITERAL = [/:\/\//, /'[^']*\.(parquet|csv|json|tsv|db|duckdb|arrow)'/i];

export function stripComments(sql: string): string {
  return sql.replace(/--[^\n]*/g, " ").replace(/\/\*[\s\S]*?\*\//g, " ");
}

export interface GuardResult { ok: boolean; sql: string; error?: string }

export function guardSql(input: string): GuardResult {
  let sql = stripComments(input).trim().replace(/;+\s*$/, "");
  if (!sql) return { ok: false, sql, error: "empty query" };
  // a single statement only (ignore semicolons inside string literals)
  const noStrings = sql.replace(/'(?:[^']|'')*'/g, "''");
  if (noStrings.includes(";")) return { ok: false, sql, error: "only one statement is allowed" };
  if (!/^\s*(select|with)\b/i.test(noStrings)) return { ok: false, sql, error: "only SELECT / WITH queries are allowed" };
  for (const re of FORBIDDEN) {
    const m = noStrings.match(re);
    if (m) return { ok: false, sql, error: `not allowed in a query: ${m[0]}` };
  }
  for (const re of FORBIDDEN_LITERAL) {
    const m = sql.match(re);
    if (m) return { ok: false, sql, error: `files and URLs are not allowed in a query: ${m[0]}` };
  }
  const refs = [...noStrings.matchAll(/\b(?:from|join)\s+("?)([\w.]+)\1/gi)].map((m) => m[2].toLowerCase());
  const ctes = new Set([...noStrings.matchAll(/(?:with|,)\s*("?)(\w+)\1\s+as\s*\(/gi)].map((m) => m[2].toLowerCase()));
  const bad = refs.filter((r) => !ctes.has(r) && !(QUERY_TABLES as readonly string[]).includes(r) && r !== "(");
  if (bad.length) return { ok: false, sql, error: `unknown table(s): ${bad.join(", ")}; use ${QUERY_TABLES.join(", ")}` };
  return { ok: true, sql };
}
