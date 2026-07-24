"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "aeon";
  text: string;
}

function formatMessage(text: string) {
  const parts = text.split(/(```[\s\S]*?```|\*\*[\s\S]*?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      return (
        <pre
          key={index}
          className="bg-slate-800 text-slate-100 p-3 rounded-md mt-2 mb-2 overflow-x-auto text-sm font-mono"
        >
          {part.slice(3, -3).replace(/^[\w]+\n/, "")}
        </pre>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMsg }),
      });
      const data = await res.json();
      const reply =
        typeof data.data === "string"
          ? data.data
          : data.answer
          ? data.answer
          : data.error
          ? `Error: ${data.error}`
          : JSON.stringify(data.data ?? data, null, 2);
      setMessages((prev) => [...prev, { role: "aeon", text: reply }]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "aeon", text: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white relative">
      <div className="h-16 border-b flex items-center px-6 font-semibold shadow-sm">
        AEON Terminal
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto p-6 space-y-6"
      >
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-400">
            Start a conversation with AEON...
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-3xl p-4 rounded-2xl ${
                m.role === "user"
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-gray-100 text-gray-900 rounded-bl-none"
              }`}
            >
              <div className="whitespace-pre-wrap leading-relaxed">
                {formatMessage(m.text)}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 max-w-3xl p-4 rounded-2xl rounded-bl-none flex items-center space-x-2">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:75ms]"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]"></div>
            </div>
          </div>
        )}
      </div>
      <div className="p-4 bg-white border-t">
        <div className="max-w-4xl mx-auto flex gap-3">
          <input
            className="flex-1 border-2 border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Type your message..."
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="bg-blue-600 text-white px-8 py-3 rounded-xl hover:bg-blue-700 disabled:opacity-50 font-semibold"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
