/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone' is only needed for self-hosted Docker deployments.
  // Vercel manages its own output structure; do NOT set it here.
  allowedDevOrigins: ["*.daytonaproxy01.net"],
};

module.exports = nextConfig;
