import type { Metadata } from "next";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export const metadata: Metadata = {
  title: "Sign In — AEON OS",
  description:
    "Sign in to AEON OS, the autonomous AI operating system for government and enterprise. Access your workspace, command centers, and AI governance tools.",

  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
    },
  },

  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${SITE_URL}/login`,
    siteName: "AEON OS",
    title: "Sign In — AEON OS",
    description:
      "Sign in to AEON OS, the autonomous AI operating system for government and enterprise.",
    images: [
      {
        url: `${SITE_URL}/og-landing.svg`,
        width: 1200,
        height: 630,
        alt: "AEON OS — Sign in to your workspace",
        type: "image/svg+xml",
      },
    ],
  },

  twitter: {
    card: "summary",
    title: "Sign In — AEON OS",
    description:
      "Sign in to AEON OS, the autonomous AI operating system for government and enterprise.",
  },

  alternates: {
    canonical: `${SITE_URL}/login`,
  },
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
