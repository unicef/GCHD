// Google Gemini generateContent with function declarations, called from the browser with the user's key.
import { LlmError, LlmSession, SessionOptions, StepInput, StepResult } from "./types";

// Gemini accepts a subset of JSON schema
export function geminiSchema(s: any): any {
  if (Array.isArray(s)) return s.map(geminiSchema);
  if (!s || typeof s !== "object") return s;
  const out: any = {};
  for (const [k, v] of Object.entries(s)) {
    if (k === "additionalProperties" || k === "$schema" || k === "default") continue;
    // Gemini allows enum only on strings: move numeric enums into the description
    if (k === "enum" && Array.isArray(v) && v.some((x) => typeof x !== "string")) continue;
    out[k] = geminiSchema(v);
  }
  if (Array.isArray(s.enum) && s.enum.some((x: unknown) => typeof x !== "string"))
    out.description = `${s.description ? `${s.description}. ` : ""}One of: ${s.enum.join(", ")}.`;
  return out;
}

export function geminiSession(o: SessionOptions): LlmSession {
  const contents: any[] = [];
  const tools = [{ functionDeclarations: o.tools.map((t) => ({ name: t.name, description: t.description, parameters: geminiSchema(t.parameters) })) }];
  let n = 0;
  return {
    async step(input: StepInput): Promise<StepResult> {
      const parts: any[] = [];
      for (const r of input.toolResults ?? [])
        parts.push({ functionResponse: { name: r.name, response: r.isError ? { error: r.content } : { result: r.content } } });
      if (input.userText) parts.push({ text: input.userText });
      const turn = { role: "user", parts };
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(o.model)}:generateContent`;
      const call = async (extra: any[], mode: "AUTO" | "ANY" = "AUTO") => {
        const res = await fetch(url, {
          method: "POST",
          headers: { "content-type": "application/json", "x-goog-api-key": o.apiKey },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: o.system }] },
            contents: [...contents, turn, ...extra], tools,
            toolConfig: { functionCallingConfig: { mode } },
          }),
        });
        if (!res.ok) throw new LlmError(`Gemini ${res.status}: ${(await res.text()).slice(0, 400)}`, res.status);
        return res.json();
      };
      // empty = no tool call and no visible text (no parts at all, or only "thought" parts)
      const empty = (c: any) => !c?.content?.parts?.some((p: any) => p.functionCall || (p.text && !p.thought));
      let d = await call([]);
      let cand = d.candidates?.[0];
      // Gemini 2.5 sometimes ends a turn with nothing to show (often right after a function response):
      // retry with a nudge; after a confirmed plan the next step must be a tool call, so the last retry
      // requires one (functionCallingConfig ANY).
      const retries: ("AUTO" | "ANY")[] = input.expectTool ? ["AUTO", "ANY"] : ["AUTO"];
      for (const mode of retries) {
        if (!empty(cand) || d.promptFeedback?.blockReason) break;
        const why = cand?.finishReason ?? "no candidate";
        console.warn(`Gemini empty reply (${why}), retrying with mode ${mode}`, d);
        d = await call([{ role: "model", parts: [{ text: "(my previous reply was empty)" }] },
          { role: "user", parts: [{ text: input.expectTool
            ? "Your previous reply was empty. The plan is confirmed: call the tool for its first step now, with valid arguments that follow the schema."
            : `Your previous reply was empty (${why}). Answer again: either reply in plain text or call one tool with valid JSON arguments that follow its schema.` }] }], mode);
        cand = d.candidates?.[0];
      }
      const fr: string = cand?.finishReason ?? "";
      const content = cand?.content;
      if (empty(cand)) {
        // keep the history valid for the next message: do not store an empty model turn
        const reason = d.promptFeedback?.blockReason ? `blocked: ${d.promptFeedback.blockReason}` : fr || "no candidate";
        return { text: "", toolCalls: [], stop: fr === "SAFETY" || d.promptFeedback?.blockReason ? "refusal" : "other",
                 detail: `Gemini returned no answer (${reason}).` };
      }
      contents.push(turn, content);   // echoed back unchanged (keeps thought signatures)
      const toolCalls = content.parts.filter((p: any) => p.functionCall)
        .map((p: any) => ({ id: `g${++n}`, name: p.functionCall.name, input: p.functionCall.args ?? {} }));
      const text = content.parts.filter((p: any) => p.text && !p.thought).map((p: any) => p.text).join("\n");
      return {
        text, toolCalls,
        stop: toolCalls.length ? "tool" : fr === "MAX_TOKENS" ? "max_tokens" : fr === "SAFETY" ? "refusal" : "end",
        detail: !text && !toolCalls.length ? `Gemini finished without text (${fr || "unknown reason"}).` : undefined,
      };
    },
  };
}
