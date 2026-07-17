export const metadata = {
  title: "AEON \u03b1",
  description: "Streaming chat frontend for AEON \u03b1 — powered by Vercel AI SDK + Hugging Face.",
};

import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
