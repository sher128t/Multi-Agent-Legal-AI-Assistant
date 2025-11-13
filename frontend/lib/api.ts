import { z } from "zod";

// Use environment variable in production, fallback to localhost for local dev
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const CitationSchema = z.object({
  doc_id: z.string(),
  page: z.number(),
  quote: z.string().optional(),
});

const AskResponseSchema = z.object({
  final_answer: z.string(),
  citations: z.array(CitationSchema),
  risks: z.array(z.string()),
  next_steps: z.array(z.string()),
  request_id: z.string(),
});

export type AskResponse = z.infer<typeof AskResponseSchema>;

export async function ingestDocs(fileList: FileList, caseId: string, token?: string): Promise<number> {
  if (!fileList.length) {
    return 0;
  }
  const form = new FormData();
  Array.from(fileList).forEach((file) => form.append("files", file));
  form.append("case_id", caseId);

  const response = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });

  if (!response.ok) {
    throw new Error(`Ingestion failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.indexed ?? 0;
}

export async function* askCase(
  query: string,
  caseId: string,
  sessionId: string,
  token?: string,
): AsyncGenerator<Partial<AskResponse>> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, case_id: caseId, session_id: sessionId }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Ask request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const parsed = AskResponseSchema.partial().safeParse(JSON.parse(line));
      if (parsed.success) {
        yield parsed.data;
      }
    }
  }

  if (buffer.trim()) {
    const parsed = AskResponseSchema.safeParse(JSON.parse(buffer));
    if (!parsed.success) {
      throw new Error("Invalid response payload");
    }
    yield parsed.data;
  }
}

