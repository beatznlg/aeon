"use client";

import { useEffect, useState } from "react";
import { useChat, type UIMessage } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { getStoredProvider, type StoredProvider } from "@/lib/provider";
import { messageText } from "@/lib/chat-message";

interface ModuleChatProps {
  appId: string;
  appName?: string;
}

export function ModuleChat({ appId, appName }: ModuleChatProps) {
  const [provider, setProvider] = useState<StoredProvider>(getStoredProvider());

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "aeon_provider" && e.newValue) {
        setProvider(e.newValue as StoredProvider);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const [input, setInput] = useState("");

  const welcomeMessage: UIMessage = {
    id: "welcome",
    role: "assistant",
    parts: [
      {
        type: "text",
        text: `Welcome to the ${appName ?? appId} command center. I'm AEON, your autonomous agent for this vertical. Ask me anything — I can analyze live data, run tools, and help you make decisions.`,
      },
    ],
  };

  const { messages, sendMessage, status, error } = useChat({
    id: `module-chat-${appId}`,
    transport: new DefaultChatTransport({
      api: `/api/os/apps/${appId}/chat`,
      body: { appId },
      headers: { "x-aeon-provider": provider },
    }),
    messages: [welcomeMessage],
  });

  const isLoading = status === "submitted" || status === "streaming";

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    sendMessage({ text });
    setInput("");
  };

  return (
    <div className="os-chat">
      <div className="os-chat-header">
        <h3>💬 AEON Agent Chat</h3>
        <span className="os-chat-live">
          <span className="live-dot ok" />
          Live
        </span>
      </div>

      <div className="os-chat-messages">
        {messages.map((message) => (
          <div key={message.id} className={`chat-message ${message.role}`}>
            <div className="chat-message-avatar">{message.role === "user" ? "👤" : "🤖"}</div>
            <div className="chat-message-content">
              <div className="chat-message-text">
                {messageText(message) || <span className="chat-empty-content">…</span>}
              </div>
            </div>
          </div>
        ))}

        {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
          <div className="chat-message assistant">
            <div className="chat-message-avatar">🤖</div>
            <div className="chat-message-content">
              <div className="chat-typing">
                <span className="chat-typing-dot" />
                <span className="chat-typing-dot" />
                <span className="chat-typing-dot" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="module-alert danger">Chat error: {error.message || String(error)}</div>
        )}
      </div>

      <form onSubmit={onSubmit} className="os-chat-input">
        <input
          name="prompt"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask ${appName ?? "the agent"} anything...`}
          disabled={isLoading}
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary" disabled={isLoading || !input.trim()}>
          {isLoading ? "Streaming…" : "Send"}
        </button>
      </form>
    </div>
  );
}
