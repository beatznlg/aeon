"use client";

import { useState } from "react";

interface Message {
  role: "user" | "aeon";
  text: string;
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;
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
      setMessages((prev) => [...prev, { role: "aeon", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-4 flex flex-col h-screen">
      <h1 className="text-2xl font-bold mb-4 text-center">AEON Chat</h1>

      <div className="flex-1 overflow-auto bg-white rounded shadow p-4 mb-4 space-y-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-3 rounded-lg max-w-[80%] ${
              m.role === "user" ? "bg-blue-100 ml-auto" : "bg-gray-100"
            }`}
          >
            <pre className="whitespace-pre-wrap font-sans text-sm">{m.text}</pre>
          </div>
        ))}
        {loading && <div className="text-gray-500 text-sm">AEON is thinking...</div>}
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 border border-gray-300 rounded p-2 focus:outline-blue-500"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask AEON something..."
        />
        <button
          onClick={sendMessage}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
