/** Streaming providers for AI analysis — Anthropic, OpenAI, Gemini. */

async function* readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith("data: ")) yield line.slice(6);
    }
  }
}

export async function* streamAnthropic(key, model, system, user) {
  const m = model || "claude-sonnet-4-6";
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: m, max_tokens: 4096, stream: true,
      system, messages: [{ role: "user", content: user }],
    }),
  });
  if (!r.ok) throw new Error("Anthropic " + r.status + ": " + (await r.text()));
  for await (const data of readSSE(r)) {
    try {
      const d = JSON.parse(data);
      if (d.type === "content_block_delta" && d.delta?.type === "text_delta") yield d.delta.text;
    } catch {}
  }
}

export async function* streamOpenAI(key, model, system, user) {
  const m = model || "o3";
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: "Bearer " + key, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: m, max_completion_tokens: 4096, stream: true,
      messages: [{ role: "developer", content: system }, { role: "user", content: user }],
    }),
  });
  if (!r.ok) throw new Error("OpenAI " + r.status + ": " + (await r.text()));
  for await (const data of readSSE(r)) {
    if (data === "[DONE]") return;
    try {
      const c = JSON.parse(data).choices?.[0]?.delta?.content;
      if (c) yield c;
    } catch {}
  }
}

export async function* streamGemini(key, model, system, user) {
  const m = model || "gemini-2.5-pro";
  const url = "https://generativelanguage.googleapis.com/v1beta/models/" + m + ":streamGenerateContent?alt=sse&key=" + key;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: system }] },
      contents: [{ role: "user", parts: [{ text: user }] }],
      generationConfig: { maxOutputTokens: 4096, thinkingConfig: { thinkingBudget: 8000 } },
    }),
  });
  if (!r.ok) throw new Error("Gemini " + r.status + ": " + (await r.text()));
  for await (const data of readSSE(r)) {
    try {
      const parts = JSON.parse(data).candidates?.[0]?.content?.parts;
      if (parts) for (const p of parts) { if (p.text && !p.thought) yield p.text; }
    } catch {}
  }
}

export function getStream(ai, system, user) {
  if (ai.provider === "anthropic") return streamAnthropic(ai.api_key, ai.model, system, user);
  if (ai.provider === "openai") return streamOpenAI(ai.api_key, ai.model, system, user);
  if (ai.provider === "gemini") return streamGemini(ai.api_key, ai.model, system, user);
  throw new Error("Unknown provider: " + ai.provider);
}
