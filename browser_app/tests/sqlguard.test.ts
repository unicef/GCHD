import { describe, expect, it } from "vitest";
import { guardSql } from "../web/src/sqlguard";

describe("guardSql", () => {
  it("accepts SELECT and WITH over the country tables", () => {
    expect(guardSql("SELECT adm2_ucode, u18_aexp FROM adm2_hazard WHERE hazard_code = 'river_flood_100yr'").ok).toBe(true);
    expect(guardSql("WITH t AS (SELECT * FROM adm1_hazard) SELECT * FROM t;").ok).toBe(true);
    expect(guardSql("SELECT a.adm2_name FROM adm2_hazard a JOIN adm1_hazard b ON a.adm1_ucode = b.adm1_ucode").ok).toBe(true);
    expect(guardSql("SELECT * FROM (SELECT * FROM adm0_hazard) x").ok).toBe(true);
  });
  it("refuses files, URLs, other tables and statements", () => {
    for (const q of [
      "SELECT * FROM read_parquet('adm2_hazard_src.parquet')",
      "SELECT * FROM 'adm2_hazard_src.parquet'",
      "SELECT * FROM read_csv('https://example.org/x.csv')",
      "COPY adm2_hazard TO 'x.csv'",
      "SELECT 1; DROP TABLE adm2_hazard",
      "INSTALL httpfs",
      "SELECT * FROM duckdb_settings()",
      "SELECT * FROM adm2_hazard_src",
      "ATTACH 'x.db'",
      "",
    ]) expect(guardSql(q).ok, q).toBe(false);
  });
  it("ignores keywords inside comments and string literals", () => {
    expect(guardSql("SELECT * FROM adm2_hazard -- drop table\nWHERE adm2_name = 'Delete; Me'").ok).toBe(true);
  });
});
