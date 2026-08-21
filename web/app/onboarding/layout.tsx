import type { Metadata } from "next";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export const metadata: Metadata = {
  title: "Set Up Your Workspace — AEON OS",
  description:
    "Choose your industry and configure your AEON OS workspace with the right command centers, tools, and branding for your organization.",

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
    url: `${SITE_URL}/onboarding`,
    siteName: "AEON OS",
    title: "Set Up Your Workspace — AEON OS",
    description:
      "Choose your industry and configure your AEON OS workspace with the right command centers and tools.",
    images: [
      {
        url: `${SITE_URL}/og-landing.svg`,
        width: 1200,
        height: 630,
        alt: "AEON OS — Set up your workspace",
        type: "image/svg+xml",
      },
    ],
  },

  twitter: {
    card: "summary",
    title: "Set Up Your Workspace — AEON OS",
    description:
      "Choose your industry and configure your AEON OS workspace with the right command centers and tools.",
  },

  alternates: {
    canonical: `${SITE_URL}/onboarding`,
  },
};

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
