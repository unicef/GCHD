import { expect, it, vi } from "vitest";
import { geminiSchema, geminiSession, rateLimitWait } from "../web/src/llm/gemini";
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

// Gemini 429 bodies: per-minute quota (RetryInfo) vs daily quota
const quota429 = (quotaId: string, retryDelay?: string) => JSON.stringify({ error: { code: 429, status: "RESOURCE_EXHAUSTED", details: [
  { "@type": "type.googleapis.com/google.rpc.QuotaFailure", violations: [{ quotaId, quotaMetric: "generativelanguage.googleapis.com/generate_content_free_tier_requests" }] },
  ...(retryDelay ? [{ "@type": "type.googleapis.com/google.rpc.RetryInfo", retryDelay }] : [])] } });

it("rate limits: wait out a per-minute limit, stop on a daily one", () => {
  expect(rateLimitWait(quota429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "37.2s"))).toBe(38);
  expect(rateLimitWait(quota429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"))).toBe(20);
  expect(rateLimitWait(quota429("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "40s"))).toBeNull();
  expect(rateLimitWait("not json")).toBe(20);
});

it("a per-minute 429 is waited out and the step continues; a daily 429 is reported", async () => {
  vi.useFakeTimers();
  const waits: string[] = [];
  const bodies = [new Response(quota429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "3s"), { status: 429 }),
    new Response(JSON.stringify(toolCall), { status: 200 })];
  vi.stubGlobal("fetch", async () => bodies.shift());
  const p = geminiSession({ ...opts, onWait: (m: string) => waits.push(m) }).step({ userText: "go" });
  await vi.advanceTimersByTimeAsync(3000);
  expect((await p).toolCalls.map((c) => c.name)).toEqual(["query_tables"]);
  expect(waits[0]).toMatch(/waiting 3 s/);
  vi.stubGlobal("fetch", async () => new Response(quota429("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), { status: 429 }));
  await expect(geminiSession(opts).step({ userText: "go" })).rejects.toThrow(/daily limit/);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
