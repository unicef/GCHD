// Provider-neutral chat-with-tools interface. Each adapter keeps its own native message history, so
// provider-specific blocks (thinking, signatures) are echoed back unchanged.

export interface ToolDef {
  name: string;
  description: string;
  parameters: Record<string, unknown>;   // JSON schema (object)
}

export interface ToolCall { id: string; name: string; input: Record<string, unknown> }
export interface ToolResult { id: string; name: string; content: string; isError?: boolean }

export interface StepResult {
  text: string;
  toolCalls: ToolCall[];
  stop: "tool" | "end" | "refusal" | "max_tokens" | "other";
  detail?: string;          // why a reply is empty, shown to the user
}

export interface StepInput {
  userText?: string;
  toolResults?: ToolResult[];
  expectTool?: boolean;     // the next step should be a tool call (after a plan is confirmed): adapters may enforce it
}

export interface LlmSession {
  step(input: StepInput): Promise<StepResult>;
}

export interface SessionOptions {
  apiKey: string; model: string; system: string; tools: ToolDef[];
  onWait?: (msg: string) => void;   // shown while the adapter waits out a rate limit
}

export type Provider = "anthropic" | "openai" | "gemini";

export const DEFAULT_MODELS: Record<Provider, string> = {
  anthropic: "claude-opus-5-5",
  openai: "gpt-5",
  gemini: "gemini-3.8-flash",   // on the Gemini API free tier (no billing account needed)
};

export class LlmError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}
