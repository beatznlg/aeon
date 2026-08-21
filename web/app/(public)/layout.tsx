import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "AEON OS — Enterprise AI Operating System",
  description:
    "AEON OS: Autonomous AI operating system for government and enterprise. Multi-tenant, governed, sector-aware AI at scale.",
};

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="min-h-screen bg-aeon-bg-0 text-aeon-text-1 antialiased">
        {children}
      </body>
    </html>
  );
}
