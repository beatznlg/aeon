"use client";

import { useChat } from "@ai-sdk/react";

export default function Page() {
  const { messages, input, handleInputChange, handleSubmit, status } = useChat({
    api: "/api/chat",
  });

  return (
    <main>
      <h1>AEON \u03b1</h1>
      <p className="subtle">Streaming chat frontend. Powered by Vercel AI SDK + Hugging Face.</p>
      {messages.map((m) => (
        <div key={m.id} className={"msg " + (m.role === "user" ? "user" : "bot")}>
          <div className="role">{m.role}</div>
          <div>{m.content}</div>
        </div>
      ))}
      {status === "submitted" || status === "streaming" ? (
        <div className="msg bot"><div className="role">assistant</div><div>...</div></div>
      ) : null}
      <form onSubmit={handleSubmit}>
        <input
          name="prompt"
          value={input}
          onChange={handleInputChange}
          placeholder="Ask AEON anything..."
          autoComplete="off"
        />
        <button type="submit" disabled={status !== "ready"}>Send</button>
      </form>
    </main>
  );
}
