import { expect, it } from "vitest";
import { geminiSchema } from "../web/src/llm/gemini";
import { TOOLS } from "../web/src/tools";

it("Gemini tool schemas carry only string enums and no additionalProperties", () => {
  const bad: string[] = [];
  const walk = (s: any, path: string) => {
    if (!s || typeof s !== "object") return;
    if (Array.isArray(s.enum) && s.enum.some((x: unknown) => typeof x !== "string")) bad.push(`${path}.enum`);
    if ("additionalProperties" in s) bad.push(`${path}.additionalProperties`);
    for (const [k, v] of Object.entries(s)) walk(v, `${path}.${k}`);
  };
  for (const t of TOOLS) walk(geminiSchema(t.parameters), t.name);
  expect(bad).toEqual([]);
  const plan = geminiSchema(TOOLS.find((t) => t.name === "propose_plan")!.parameters);
  expect(plan.properties.admin_level).toEqual({ type: "integer", description: "One of: 0, 1, 2." });
});
