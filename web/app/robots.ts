import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/login",
          "/onboarding",
          "/api/",
          "/os/",
          "/settings/",
          "/admin/",
          "/chat",
          "/agents/",
          "/anomalies/",
          "/dr/",
          "/incidents/",
          "/llm/",
          "/swarms/",
          "/error",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
