import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXTAUTH_URL || "https://aeonos.com";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const publicPages: MetadataRoute.Sitemap = [
    {
      url: SITE_URL,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1.0,
    },
    {
      url: `${SITE_URL}/pricing`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/login`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.3,
    },
  ];

  return publicPages;
}
