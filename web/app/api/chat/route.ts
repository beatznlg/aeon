import { streamText } from "ai";
import { huggingface } from "@ai-sdk/huggingface";

// Allow streaming responses up to 30 seconds.
export const maxDuration = 30;

export async function POST(req: Request) {
  const { messages } = await req.json();
  const last = messages[messages.length - 1];
  const prompt = last?.content ?? "";

  const result = await streamText({
    model: huggingface("Qwen/Qwen2.5-3B-Instruct"),
    prompt,
  });

  return result.toAIStreamResponse();
}
