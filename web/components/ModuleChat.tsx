"use client";

import { useEffect, useState } from "react";
import { useChat, type Message } from "@ai-sdk/react";
import { getStoredProvider, type StoredProvider } from "@/lib/provider";

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

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    error,
  } = useChat({
    api: `/api/os/apps/${appId}/chat`,
    id: `module-chat-${appId}`,
    body: { appId },
    headers: { "x-aeon-provider": provider },
    initialMessages: [
      {
        id: "welcome",
        role: "assistant",
        content: `Welcome to the ${appName ?? appId} command center. I'm AEON, your autonomous agent for this vertical. Ask me anything — I can analyze live data, run tools, and help you make decisions.`,
      } as Message,
    ],
  });

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
          <div
            key={message.id}
            className={`chat-message ${message.role}`}
          >
            <div className="chat-message-avatar">
              {message.role === "user" ? "👤" : "🤖"}
            </div>
            <div className="chat-message-content">
              <div className="chat-message-text">
                {message.content || (
                  <span className="chat-empty-content">…</span>
                )}
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
          <div className="module-alert danger">
            Chat error: {error.message || String(error)}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="os-chat-input">
        <input
          name="prompt"
          value={input}
          onChange={handleInputChange}
          placeholder={`Ask ${appName ?? "the agent"} anything...`}
          disabled={isLoading}
          autoComplete="off"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? "Streaming…" : "Send"}
        </button>
      </form>
    </div>
  );
}
