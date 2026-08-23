/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone' is only needed for self-hosted Docker deployments.
  // Vercel manages its own output structure; do NOT set it here.
  allowedDevOrigins: ["*.daytonaproxy01.net"],
  experimental: {
    // The offline local user store (web/lib/local-users.ts) reads
    // `.data/aeon-users.json` at runtime. The file doesn't exist at build
    // time, and Vercel's output file tracing would statically resolve the
    // path and fail with ENOENT. Excluding it keeps the build green while
    // the runtime fs access keeps working where the filesystem is writable.
    outputFileTracingExcludes: {
      "*": ["./.data/**", "./.data"],
    },
  },
};

module.exports = nextConfig;
