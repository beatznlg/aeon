"use client";

import { useSession, signOut } from "next-auth/react";

export default function UserMenu() {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return <span className="user-menu-loading">...</span>;
  }

  if (!session?.user) {
    return null;
  }

  const role = (session.user as any).role || "viewer";

  return (
    <div className="user-menu">
      <span className="user-menu-email" title={session.user.email || undefined}>
        {session.user.email}
      </span>
      <span className="user-menu-role">{String(role).toUpperCase()}</span>
      <button
        className="user-menu-logout"
        onClick={() => signOut({ callbackUrl: "/login" })}
        title="Sign out"
      >
        →
      </button>
    </div>
  );
}
