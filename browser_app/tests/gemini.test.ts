import { expect, it, vi } from "vitest";
import { geminiSchema, geminiSession } from "../web/src/llm/gemini";
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

// fake generateContent: each reply in turn; records the functionCallingConfig mode of each request
function fakeGemini(replies: any[]) {
  const modes: string[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: any) => {
    modes.push(JSON.parse(init.body).toolConfig.functionCallingConfig.mode);
    return new Response(JSON.stringify(replies.shift()), { status: 200 });
  });
  return modes;
}
const thoughtOnly = { candidates: [{ finishReason: "STOP", content: { role: "model", parts: [{ text: "thinking…", thought: true }] } }] };
const toolCall = { candidates: [{ finishReason: "STOP", content: { role: "model", parts: [{ functionCall: { name: "query_tables", args: { plan_id: "P1" } } }] } }] };
const opts = { apiKey: "k", model: "gemini-2.5-flash", system: "s", tools: TOOLS };

it("after a confirmed plan, empty or thought-only Gemini replies are retried, the last time requiring a tool call", async () => {
  const modes = fakeGemini([thoughtOnly, { candidates: [{ finishReason: "STOP" }] }, toolCall]);
  const r = await geminiSession(opts).step({ userText: "I confirm plan P1.", expectTool: true });
  expect(modes).toEqual(["AUTO", "AUTO", "ANY"]);
  expect(r.toolCalls.map((c) => c.name)).toEqual(["query_tables"]);
  vi.unstubAllGlobals();
});

it("without a confirmed plan, one retry and then the empty reply is reported", async () => {
  const modes = fakeGemini([thoughtOnly, thoughtOnly]);
  const r = await geminiSession(opts).step({ userText: "hello" });
  expect(modes).toEqual(["AUTO", "AUTO"]);
  expect(r.toolCalls).toEqual([]);
  expect(r.detail).toMatch(/no answer/);
  vi.unstubAllGlobals();
});
