// Claude via the official Anthropic TypeScript SDK, called directly from the browser with the user's key.
import Anthropic from "@anthropic-ai/sdk";
import { LlmError, LlmSession, SessionOptions, StepInput, StepResult } from "./types";

// models that take the server-side refusal fallback ("default" routes by refusal category)
const FALLBACK_MODELS = /^claude-(opus-5|sonnet-5-5|fable-5)/;

export function anthropicSession(o: SessionOptions): LlmSession {
  const client = new Anthropic({ apiKey: o.apiKey, dangerouslyAllowBrowser: true, maxRetries: 2 });
  const messages: Anthropic.Beta.BetaMessageParam[] = [];
  const tools: Anthropic.Beta.BetaTool[] = o.tools.map((t) => ({
    name: t.name, description: t.description,
    input_schema: t.parameters as Anthropic.Beta.BetaTool.InputSchema,
  }));
  const fallback = FALLBACK_MODELS.test(o.model);

  return {
    async step(input: StepInput): Promise<StepResult> {
      const content: Anthropic.Beta.BetaContentBlockParam[] = [];
      for (const r of input.toolResults ?? [])
        content.push({ type: "tool_result", tool_use_id: r.id, content: r.content, is_error: r.isError });
      if (input.userText) content.push({ type: "text", text: input.userText });
      messages.push({ role: "user", content });
      try {
        const params: Record<string, unknown> = {
          model: o.model,
          max_tokens: 16000,
          // stable prefix (tools + system) is cached across the turns of a conversation
          system: [{ type: "text", text: o.system, cache_control: { type: "ephemeral" } }],
          tools,
          messages,
          thinking: { type: "adaptive" },
          output_config: { effort: "medium" },
        };
        if (fallback) Object.assign(params, { betas: ["server-side-fallback-2026-07-01"], fallbacks: "default" });
        let res = await client.beta.messages.create(params as any) as Anthropic.Beta.BetaMessage;
        // server-side pause: send the turn back so it continues
        while (res.stop_reason === "pause_turn") {
          messages.push({ role: "assistant", content: res.content as any });
          res = await client.beta.messages.create({ ...params, messages } as any) as Anthropic.Beta.BetaMessage;
        }
        messages.push({ role: "assistant", content: res.content as any });
        const text = res.content.filter((b) => b.type === "text").map((b: any) => b.text).join("\n");
        const toolCalls = res.content.filter((b) => b.type === "tool_use")
          .map((b: any) => ({ id: b.id, name: b.name, input: (b.input ?? {}) as Record<string, unknown> }));
        const stop = res.stop_reason === "tool_use" ? "tool" : res.stop_reason === "end_turn" ? "end"
          : res.stop_reason === "refusal" ? "refusal" : res.stop_reason === "max_tokens" ? "max_tokens" : "other";
        return { text, toolCalls, stop };
      } catch (e) {
        messages.pop();   // keep the history valid for a retry
        if (e instanceof Anthropic.AuthenticationError) throw new LlmError("Anthropic rejected the API key.", 401);
        if (e instanceof Anthropic.RateLimitError) throw new LlmError("Anthropic rate limit reached; wait a moment and retry.", 429);
        if (e instanceof Anthropic.BadRequestError) throw new LlmError(`Anthropic: ${e.message}`, 400);
        if (e instanceof Anthropic.APIError) throw new LlmError(`Anthropic: ${e.message}`, e.status);
        throw e;
      }
    },
  };
}
