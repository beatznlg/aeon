import type { Metadata } from "next";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export const metadata: Metadata = {
  title: "Pricing — AEON OS | Enterprise AI Platform",
  description:
    "Start free, scale with your team. AEON OS pricing includes Free, Team ($49/mo), and Enterprise ($199/mo) plans with 16 industry sectors, RBAC, and full AI governance.",

  keywords: [
    "AEON OS pricing",
    "enterprise AI platform",
    "AI operating system",
    "AI governance pricing",
    "sector AI",
    "workspace AI",
    "enterprise AI plan",
  ],

  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${SITE_URL}/pricing`,
    siteName: "AEON OS",
    title: "Pricing — AEON OS | Enterprise AI Platform",
    description:
      "Start free, scale with your team. AEON OS pricing includes Free, Team ($49/mo), and Enterprise ($199/mo) plans with 16 industry sectors, RBAC, and full AI governance.",
    images: [
      {
        url: `${SITE_URL}/og-pricing.svg`,
        width: 1200,
        height: 630,
        alt: "AEON OS Pricing — Simple, transparent plans for every team",
        type: "image/svg+xml",
      },
    ],
  },

  twitter: {
    card: "summary_large_image",
    title: "Pricing — AEON OS | Enterprise AI Platform",
    description:
      "Start free, scale with your team. Free, Team ($49/mo), and Enterprise ($199/mo) plans with 16 industry sectors and full AI governance.",
    images: [`${SITE_URL}/og-pricing.svg`],
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
    canonical: `${SITE_URL}/pricing`,
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const productSchema = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: "AEON OS",
    description:
      "Enterprise AI operating system for government and enterprise. Multi-tenant, governed, sector-aware AI at scale with 16 industry verticals.",
    url: SITE_URL,
    brand: {
      "@type": "Brand",
      name: "AEON OS",
    },
    manufacturer: {
      "@type": "Organization",
      name: "AEON OS",
      url: SITE_URL,
    },
    category: "Enterprise AI Platform",
    image: `${SITE_URL}/og-pricing.svg`,
    offers: [
      {
        "@type": "Offer",
        name: "Free",
        price: "0",
        priceCurrency: "USD",
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
        url: `${SITE_URL}/login`,
        description:
          "1 workspace, basic sector dashboards, community plugins, stub AI provider.",
        hasTier: {
          "@type": "PriceSpecification",
          name: "Free",
          price: "0",
          priceCurrency: "USD",
        },
      },
      {
        "@type": "Offer",
        name: "Team",
        price: "49",
        priceCurrency: "USD",
        billingIncrement: {
          "@type": "UnitPriceSpecification",
          price: "49",
          priceCurrency: "USD",
          unitText: "MONTH",
        },
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
        url: `${SITE_URL}/login?callbackUrl=/os/billing`,
        description:
          "Up to 10 workspaces, all AI providers, all 16 sectors, automations, RAG, priority support.",
        hasTier: {
          "@type": "PriceSpecification",
          name: "Team",
          price: "49",
          priceCurrency: "USD",
          billingDuration: {
            "@type": "QuantitativeValue",
            value: 1,
            unitCode: "MON",
          },
        },
      },
      {
        "@type": "Offer",
        name: "Enterprise",
        price: "199",
        priceCurrency: "USD",
        billingIncrement: {
          "@type": "UnitPriceSpecification",
          price: "199",
          priceCurrency: "USD",
          unitText: "MONTH",
        },
        priceValidUntil: "2027-12-31",
        availability: "https://schema.org/InStock",
        url: "mailto:sales@aeonos.com",
        description:
          "Unlimited workspaces, SSO/SCIM, SIEM, DR, compliance policies, dedicated support.",
        hasTier: {
          "@type": "PriceSpecification",
          name: "Enterprise",
          price: "199",
          priceCurrency: "USD",
          billingDuration: {
            "@type": "QuantitativeValue",
            value: 1,
            unitCode: "MON",
          },
        },
      },
    ],
  };

  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "What is included in the free plan?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "The free plan gives you one workspace with access to basic sector dashboards and community plugins. It uses the stub AI provider so you can explore the platform without any API keys.",
        },
      },
      {
        "@type": "Question",
        name: "Can I try Team or Enterprise before committing?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Yes. Both Team and Enterprise include a 14-day free trial with full feature access. No credit card required to start.",
        },
      },
      {
        "@type": "Question",
        name: "How does billing work?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "We use Stripe for secure payment processing. You can upgrade, downgrade, or cancel anytime from your billing settings. Plans renew monthly.",
        },
      },
      {
        "@type": "Question",
        name: "What AI providers are supported?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "AEON supports OpenAI, Anthropic, Google, Mistral, HuggingFace, Ollama, vLLM, and custom providers. The Team and Enterprise plans include access to all providers.",
        },
      },
      {
        "@type": "Question",
        name: "Is my data secure?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Yes. AEON is built with enterprise security: workspace isolation, RBAC, tamper-evident audit logs, encrypted at rest, and SOC 2 readiness controls. We never train on your data.",
        },
      },
      {
        "@type": "Question",
        name: "Do you offer volume or annual discounts?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Yes. Contact our sales team for annual billing discounts and custom enterprise pricing for large deployments.",
        },
      },
    ],
  };

  const orgSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "AEON OS",
    url: SITE_URL,
    logo: `${SITE_URL}/og-landing.svg`,
    sameAs: [],
    contactPoint: {
      "@type": "ContactPoint",
      email: "sales@aeonos.com",
      contactType: "sales",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />
      {children}
    </>
  );
}
