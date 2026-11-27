// Basic tool, pure parts (no DOM): summary-table columns for a population, the SQL, and the share-link state.

export type Pop = "u18" | "all";
export type Sex = "total" | "f" | "m";
export type Value = "exposed" | "pct_exposed" | "hazard_mean" | "hazard_max" | "exposure_index" | "exposure_class";
export type Level = 0 | 1 | 2;

export interface State {
  iso3?: string; level: Level; adm1: string; hazard: string; pop: Pop; sex: Sex; value: Value; layer: boolean;
}
export const DEFAULT_STATE: State = { level: 2, adm1: "", hazard: "river_flood_100yr", pop: "u18", sex: "total", value: "exposed", layer: false };

/** Summary-table columns for a population: exposed count, exposed share (0-100), population, ADM2 index/class. */
export function columnsFor(pop: Pop, sex: Sex) {
  const s = { total: "", f: "f", m: "m" }[sex];
  if (pop === "u18") return {
    exp: `u18_a${s}exp`, share: `u18_r${s}exp`,
    pop: { total: "u18_pop_total", f: "u18_pop_f", m: "u18_pop_m" }[sex],
    index: `u18_c${s}expi`, cls: `u18_c${s}expc`,
  };
  return {
    exp: `a${s}exp`, share: `r${s}exp`,
    pop: { total: "pop_total", f: "pop_total_f", m: "pop_total_m" }[sex],
    index: `c${s}expi`, cls: `c${s}expc`,
  };
}

export function popLabel(pop: Pop, sex: Sex): string {
  return pop === "u18" ? { total: "children", f: "girls", m: "boys" }[sex] : { total: "people", f: "females", m: "males" }[sex];
}

export const VALUE_LABELS: Record<Value, string> = {
  exposed: "Number exposed", pct_exposed: "% exposed", hazard_mean: "Hazard intensity (mean)",
  hazard_max: "Hazard intensity (max)", exposure_index: "Exposure index (0-10, country scale)",
  exposure_class: "Exposure class (1-5, country scale)",
};
/** Map values each level has: the ADM1/ADM0 roll-ups carry no indices or classes. */
export function valuesFor(level: Level): Value[] {
  return level === 2 ? Object.keys(VALUE_LABELS) as Value[] : ["exposed", "pct_exposed", "hazard_mean", "hazard_max"];
}

const q = (s: string) => `'${s.replace(/'/g, "''")}'`;
const valid = (expr: string, as: string) => `CASE WHEN status = '' THEN ${expr} END AS ${as}`;

/** One hazard by unit (ADM1 or ADM2), optionally the districts of one ADM1 unit; rows with a status are kept, values empty. */
export function unitSql(s: State): string {
  const c = columnsFor(s.pop, s.sex);
  const l = s.level;
  const cols = [`adm${l}_ucode`, `adm${l}_name`, ...(l === 2 ? ["adm1_name"] : []), `${c.pop} AS population`,
    valid(c.exp, "exposed"), valid(`round(${c.share}, 2)`, "pct_exposed"), valid("hazs_mean", "hazard_mean"),
    valid("hazs_max", "hazard_max"),
    ...(l === 2 ? [valid(c.index, "exposure_index"), valid(c.cls, "exposure_class")] : []), "status"];
  return `SELECT ${cols.join(", ")} FROM adm${l}_hazard WHERE hazard_code = ${q(s.hazard)}`
    + (l === 2 && s.adm1 ? ` AND adm1_ucode = ${q(s.adm1)}` : "")
    + " ORDER BY exposed DESC NULLS LAST, population DESC";
}

/** All hazards of one unit (the country at ADM0), ranked by the number exposed (population: see popSql). */
export function profileSql(level: Level, ucode: string, pop: Pop, sex: Sex): string {
  const c = columnsFor(pop, sex);
  return `SELECT hazard, ${valid(c.exp, "exposed")}, ${valid(`round(${c.share}, 2)`, "pct_exposed")},
    ${valid("hazs_mean", "hazard_mean")}, status, hazard_code FROM adm${level}_hazard WHERE adm${level}_ucode = ${q(ucode)}
    ORDER BY exposed DESC NULLS LAST, hazard`;
}

/** The unit's population for the chosen group (the same on every hazard row). */
export function popSql(level: Level, ucode: string, pop: Pop, sex: Sex): string {
  return `SELECT max(${columnsFor(pop, sex).pop}) AS population FROM adm${level}_hazard WHERE adm${level}_ucode = ${q(ucode)}`;
}

export function stateToHash(s: State): string {
  const p = new URLSearchParams({ tool: "basic" });
  if (s.iso3) p.set("iso3", s.iso3);
  p.set("level", String(s.level));
  if (s.adm1) p.set("adm1", s.adm1);
  p.set("hazard", s.hazard); p.set("pop", s.pop); p.set("sex", s.sex); p.set("value", s.value);
  if (s.layer) p.set("layer", "1");
  return `#${p}`;
}

export function hashToState(hash: string): Partial<State> & { tool?: string } {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const out: Partial<State> & { tool?: string } = {};
  const tool = p.get("tool"); if (tool) out.tool = tool;
  const iso3 = p.get("iso3"); if (iso3) out.iso3 = iso3.toUpperCase();
  const level = Number(p.get("level")); if ([0, 1, 2].includes(level) && p.has("level")) out.level = level as Level;
  const adm1 = p.get("adm1"); if (adm1) out.adm1 = adm1;
  const hz = p.get("hazard"); if (hz) out.hazard = hz;
  const pop = p.get("pop"); if (pop === "u18" || pop === "all") out.pop = pop;
  const sex = p.get("sex"); if (sex === "total" || sex === "f" || sex === "m") out.sex = sex;
  const v = p.get("value"); if (v && v in VALUE_LABELS) out.value = v as Value;
  if (p.get("layer") === "1") out.layer = true;
  return out;
}
