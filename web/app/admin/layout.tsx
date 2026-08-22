import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Administration — AEON OS",
  description: "AEON OS administrative controls and operational observability.",
  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
    },
  },
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
