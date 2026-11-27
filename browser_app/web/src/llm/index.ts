import { anthropicSession } from "./anthropic";
import { geminiSession } from "./gemini";
import { openaiSession } from "./openai";
import type { LlmSession, Provider, SessionOptions } from "./types";

export * from "./types";

export function createSession(provider: Provider, o: SessionOptions): LlmSession {
  switch (provider) {
    case "anthropic": return anthropicSession(o);
    case "openai": return openaiSession(o);
    case "gemini": return geminiSession(o);
  }
}
