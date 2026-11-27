// OpenAI Chat Completions with function tools, called directly from the browser with the user's key.
import { LlmError, LlmSession, SessionOptions, StepInput, StepResult } from "./types";

export function openaiSession(o: SessionOptions): LlmSession {
  const messages: any[] = [{ role: "system", content: o.system }];
  const tools = o.tools.map((t) => ({ type: "function", function: { name: t.name, description: t.description, parameters: t.parameters } }));
  return {
    async step(input: StepInput): Promise<StepResult> {
      const added: any[] = [];
      for (const r of input.toolResults ?? []) added.push({ role: "tool", tool_call_id: r.id, content: r.content });
      if (input.userText) added.push({ role: "user", content: input.userText });
      const res = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${o.apiKey}` },
        body: JSON.stringify({ model: o.model, messages: [...messages, ...added], tools }),
      });
      if (!res.ok) throw new LlmError(`OpenAI ${res.status}: ${(await res.text()).slice(0, 300)}`, res.status);
      const d = await res.json();
      const choice = d.choices?.[0];
      const msg = choice?.message ?? { role: "assistant", content: "" };
      messages.push(...added, msg);
      const toolCalls = (msg.tool_calls ?? []).map((c: any) => {
        let args: Record<string, unknown> = {};
        try { args = JSON.parse(c.function.arguments || "{}"); } catch { args = { _invalid_json: c.function.arguments }; }
        return { id: c.id, name: c.function.name, input: args };
      });
      const fr = choice?.finish_reason;
      return {
        text: msg.content ?? "", toolCalls,
        stop: toolCalls.length ? "tool" : fr === "length" ? "max_tokens" : fr === "content_filter" ? "refusal" : "end",
      };
    },
  };
}
