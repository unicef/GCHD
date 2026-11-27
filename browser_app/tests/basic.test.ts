import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { DEFAULT_STATE, State, columnsFor, hashToState, profileSql, stateToHash, unitSql, valuesFor } from "../web/src/basic_query";
import { guardSql } from "../web/src/sqlguard";

// columns of the published exposure tables (STAC table:columns)
const cols = (id: string) => new Set<string>(JSON.parse(readFileSync(
  new URL(`../../STAC_catalog/stac/exposure/${id}/collection.json`, import.meta.url), "utf8"))["table:columns"].map((c: any) => c.name));

it("every population x sex maps to columns that exist in the summary tables", () => {
  const adm2 = cols("adm2_hazard"), adm1 = cols("adm1_hazard");
  for (const pop of ["u18", "all"] as const) for (const sex of ["total", "f", "m"] as const) {
    const c = columnsFor(pop, sex);
    for (const k of [c.exp, c.share, c.pop, c.index, c.cls]) expect(adm2.has(k), `${pop}/${sex}: ${k}`).toBe(true);
    for (const k of [c.exp, c.share, c.pop]) expect(adm1.has(k), `adm1 ${k}`).toBe(true);
  }
  expect(columnsFor("u18", "f")).toMatchObject({ exp: "u18_afexp", share: "u18_rfexp", pop: "u18_pop_f" });
  expect(columnsFor("all", "total")).toMatchObject({ exp: "aexp", share: "rexp", pop: "pop_total" });
});

it("map values follow the level: indices and classes only at ADM2", () => {
  expect(valuesFor(2)).toContain("exposure_class");
  expect(valuesFor(1)).not.toContain("exposure_index");
});

it("unit and profile SQL pass the SQL guard and filter as asked", () => {
  const s: State = { ...DEFAULT_STATE, level: 2, adm1: "BRA_035", hazard: "river_flood_100yr", pop: "all", sex: "m" };
  const sql = unitSql(s);
  expect(guardSql(sql).ok).toBe(true);
  expect(sql).toMatch(/FROM adm2_hazard WHERE hazard_code = 'river_flood_100yr' AND adm1_ucode = 'BRA_035'/);
  expect(sql).toMatch(/CASE WHEN status = '' THEN amexp END AS exposed/);
  expect(sql).toMatch(/exposure_class/);
  const s1 = unitSql({ ...s, level: 1 });
  expect(s1).not.toMatch(/adm1_ucode = /);
  expect(s1).not.toMatch(/exposure_index/);
  const p = profileSql(0, "KEN_V1", "u18", "total");
  expect(guardSql(p).ok).toBe(true);
  expect(p).toMatch(/WHERE adm0_ucode = 'KEN_V1'/);
  expect(unitSql({ ...s, hazard: "x' OR 1=1 --" })).toMatch(/'x'' OR 1=1 --'/);   // quoted, not injected
});

it("share links round-trip", () => {
  const s: State = { ...DEFAULT_STATE, iso3: "BRA", level: 2, adm1: "BRA_035", hazard: "drought_asi", pop: "u18", sex: "f", value: "pct_exposed", layer: true };
  expect(hashToState(stateToHash(s))).toEqual({ tool: "basic", ...s });
  expect(hashToState("#tool=ai")).toEqual({ tool: "ai" });
  expect(hashToState("#level=9&pop=bad&value=zzz")).toEqual({});
});
