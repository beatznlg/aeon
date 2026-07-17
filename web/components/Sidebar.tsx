"use client";

export default function Sidebar({
  onNewChat,
  onOpenMemory,
  onOpenSettings,
}: {
  onNewChat: () => void;
  onOpenMemory: () => void;
  onOpenSettings: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <span className="logo">⟁</span>
          <span>AEON</span>
        </div>
        <button className="btn-primary" onClick={onNewChat}>
          + New chat
        </button>
      </div>

      <nav className="sidebar-section">
        <h3>Workspace</h3>
        <a href="#" onClick={(e) => { e.preventDefault(); onOpenMemory(); }}>
          Memory browser
        </a>
        <a href="#" onClick={(e) => { e.preventDefault(); onOpenSettings(); }}>
          Settings & keys
        </a>
        <a
          href="https://huggingface.co/settings/tokens"
          target="_blank"
          rel="noopener noreferrer"
        >
          HF token ↗
        </a>
        <a
          href="https://supabase.com/dashboard"
          target="_blank"
          rel="noopener noreferrer"
        >
          Supabase ↗
        </a>
        <a
          href="https://huggingface.co/new-space"
          target="_blank"
          rel="noopener noreferrer"
        >
          HF Space (kernel) ↗
        </a>
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot"></span>
        <span>
          kernel <code style={{ fontSize: "0.78rem" }}>v2.1</code>
        </span>
      </div>
    </aside>
  );
}
