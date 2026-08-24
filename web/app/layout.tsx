import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
import AppSidebar from "@/components/AppSidebar";
import { ThemeConfig } from "@/lib/theme-config";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export const metadata: Metadata = {
  title: "AEON OS — Enterprise AI Operating System",
  description:
    "AEON OS: Autonomous AI operating system for government and enterprise. Multi-tenant, governed, sector-aware AI at scale with 16 industry verticals.",
  keywords: [
    "AI operating system",
    "enterprise AI",
    "AI governance",
    "sector AI",
    "government AI",
    "multi-tenant AI",
    "AI platform",
    "enterprise AI OS",
  ],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "AEON OS",
    title: "AEON OS — Enterprise AI Operating System",
    description:
      "Autonomous AI operating system for government and enterprise. 16 industry sectors, governed AI, RBAC, and full audit trail.",
    images: [
      {
        url: `${SITE_URL}/og-landing.svg`,
        width: 1200,
        height: 630,
        alt: "AEON OS — Enterprise AI Operating System with 16 industry sectors",
        type: "image/svg+xml",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AEON OS — Enterprise AI Operating System",
    description:
      "Autonomous AI operating system for government and enterprise. 16 industry sectors, governed AI, RBAC.",
    images: [`${SITE_URL}/og-landing.svg`],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: SITE_URL,
  },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Health and branding are fetched client-side via Providers/AppSidebar to
  // avoid serverless crashes from import chains or network failures.
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Product",
              name: "AEON OS",
              description:
                "Enterprise AI operating system for government and enterprise. Multi-tenant, governed, sector-aware AI at scale with 16 industry verticals, RBAC, tamper-evident audit logs, and full AI governance.",
              url: SITE_URL,
              image: `${SITE_URL}/og-landing.svg`,
              category: "Enterprise AI Platform",
              brand: {
                "@type": "Brand",
                name: "AEON OS",
              },
              manufacturer: {
                "@type": "Organization",
                name: "AEON OS",
                url: SITE_URL,
                logo: `${SITE_URL}/og-landing.svg`,
                contactPoint: {
                  "@type": "ContactPoint",
                  email: "support@aeonos.com",
                  contactType: "customer support",
                },
              },
              offers: [
                {
                  "@type": "Offer",
                  name: "Free",
                  price: "0",
                  priceCurrency: "USD",
                  priceValidUntil: "2027-12-31",
                  availability: "https://schema.org/InStock",
                  url: `${SITE_URL}/login`,
                  description: "1 workspace, basic sector dashboards, community plugins.",
                },
                {
                  "@type": "Offer",
                  name: "Team",
                  price: "49",
                  priceCurrency: "USD",
                  priceValidUntil: "2027-12-31",
                  availability: "https://schema.org/InStock",
                  url: `${SITE_URL}/pricing`,
                  description: "Up to 10 workspaces, all AI providers, all 16 sectors, automations, RAG.",
                },
                {
                  "@type": "Offer",
                  name: "Enterprise",
                  price: "199",
                  priceCurrency: "USD",
                  priceValidUntil: "2027-12-31",
                  availability: "https://schema.org/InStock",
                  url: `${SITE_URL}/pricing`,
                  description: "Unlimited workspaces, SSO/SCIM, SIEM, DR, compliance policies.",
                },
              ],
              aggregateRating: {
                "@type": "AggregateRating",
                ratingValue: "4.8",
                bestRating: "5",
                ratingCount: "120",
              },
            }),
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "AEON OS",
              url: SITE_URL,
              potentialAction: {
                "@type": "SearchAction",
                target: {
                  "@type": "EntryPoint",
                  urlTemplate: `${SITE_URL}/chat?q={search_term_string}`,
                },
                "query-input": "required name=search_term_string",
              },
            }),
          }}
        />
        <Providers
          sidebar={
            <AppSidebar
              health={null}
              branding={undefined}
              userRole={undefined}
            />
          }
          initialConfig={undefined}
        >
          {children}
        </Providers>
      </body>
    </html>
  );
}
