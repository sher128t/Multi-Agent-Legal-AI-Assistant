"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { AskResponse, askCase, ingestDocs } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: AskResponse["citations"];
  risks?: string[];
  nextSteps?: string[];
};

const SESSION_STORAGE_KEY = "legal-chat-sessions";

function randomId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [caseId, setCaseId] = useState("case-demo");
  const [sessionId, setSessionId] = useState<string>("");
  const [sessions, setSessions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [token, setToken] = useState<string>("");
  const [files, setFiles] = useState<FileList | null>(null);
  const disableSend = isLoading || !input.trim();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const history = JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) ?? "[]");
    setSessions(history);
    const initialSession = history[0] ?? randomId();
    setSessionId(initialSession);
  }, []);

  useEffect(() => {
    if (!sessionId || typeof window === "undefined") return;
    setSessions((prev) => {
      const next = Array.from(new Set([sessionId, ...prev]));
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, [sessionId]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim()) return;
    const query = input.trim();
    setInput("");
    const userMessage: Message = { id: randomId(), role: "user", content: query };
    const assistantId = randomId();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: [],
      risks: [],
      nextSteps: [],
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);

    try {
      for await (const chunk of askCase(query, caseId, sessionId, token || undefined)) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: chunk.final_answer ?? message.content,
                  citations: chunk.citations ?? message.citations,
                  risks: chunk.risks ?? message.risks,
                  nextSteps: chunk.next_steps ?? message.nextSteps,
                }
              : message,
          ),
        );
      }
    } catch (error) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? { ...message, content: `Request failed: ${(error as Error).message}` }
            : message,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!files || files.length === 0) return;
    try {
      await ingestDocs(files, caseId, token || undefined);
      setFiles(null);
    } catch (error) {
      alert(`Ingestion failed: ${(error as Error).message}`);
    }
  };

  const sessionButtons = useMemo(
    () =>
      sessions.map((id) => (
        <button
          key={id}
          onClick={() => {
            setSessionId(id);
            setMessages([]);
          }}
          className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
            id === sessionId ? "border-slate-900 bg-slate-100" : "border-slate-200 hover:border-slate-300"
          }`}
        >
          Session {id.slice(0, 8)}
        </button>
      )),
    [sessions, sessionId],
  );

  return (
    <div className="flex w-full gap-6">
      <aside className="sidebar">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-500">Sessions</span>
          <button
            className="rounded-md bg-slate-900 px-3 py-1 text-xs font-semibold text-white"
            onClick={() => {
              setSessionId(randomId());
              setMessages([]);
            }}
          >
            New
          </button>
        </div>
        <div className="space-y-2">{sessionButtons}</div>
        <div className="pt-4">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Case ID
          </label>
          <input
            value={caseId}
            onChange={(event) => setCaseId(event.target.value)}
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div className="pt-4">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Bearer Token
          </label>
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="demo-user:junior,senior"
            className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div className="pt-4 space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Ingest documents
          </label>
          <input
            type="file"
            multiple
            onChange={(event) => setFiles(event.target.files)}
            className="block w-full text-sm"
          />
          <button
            onClick={handleIngest}
            className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
            disabled={!files?.length}
          >
            Upload to case
          </button>
        </div>
      </aside>

      <section className="flex-1">
        <div className="chat-container">
          <div className="chat-messages">
            {messages.map((message) => (
              <div key={message.id} className="space-y-3">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  {message.role === "user" ? "You" : "Agents"}
                </div>
                <div className="prose prose-sm max-w-none text-slate-800">
                  {message.role === "assistant" ? (
                    <ReactMarkdown>{message.content || "…"}</ReactMarkdown>
                  ) : (
                    <p>{message.content}</p>
                  )}
                </div>
                {message.citations && message.citations.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {message.citations.map((citation) => (
                      <span key={`${citation.doc_id}-${citation.page}`} className="citation-chip">
                        Doc {citation.doc_id.slice(0, 6)} p.{citation.page}
                      </span>
                    ))}
                  </div>
                )}
                {message.risks && message.risks.length > 0 && (
                  <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                    <strong>Risks:</strong>
                    <ul className="list-disc pl-5">
                      {message.risks.map((risk) => (
                        <li key={risk}>{risk}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {message.nextSteps && message.nextSteps.length > 0 && (
                  <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
                    <strong>Next steps:</strong>
                    <ul className="list-disc pl-5">
                      {message.nextSteps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
            {messages.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
                Upload case documents on the left, then ask a question to kick off the junior → compliance →
                senior workflow.
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="border-t border-slate-200 p-4">
            <div className="flex gap-3">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask about retention, GDPR, or policy obligations…"
                className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={disableSend}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
              >
                {isLoading ? "Thinking…" : "Send"}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}

