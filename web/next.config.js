/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone' is only needed for self-hosted Docker deployments.
  // Vercel manages its own output structure; do NOT set it here.
  allowedDevOrigins: ["*.daytonaproxy01.net"],
  // NOTE: do NOT set outputFileTracingRoot here. The Freebuff/Vercel builder
  // packages the app from the repo root, so the traced file map must stay
  // root-relative; pinning it to web/ breaks module resolution in every
  // serverless function at runtime (MODULE_NOT_FOUND on next internals).
  // The offline local user store (web/lib/local-users.ts) reads
  // `.data/aeon-users.json` at runtime. The file doesn't exist at build
  // time, and Vercel's output file tracing would statically resolve the
  // path and fail with ENOENT. Excluding it keeps the build green while
  // the runtime fs access keeps working where the filesystem is writable.
  outputFileTracingExcludes: {
    "*": [
      "./.data/**",
      "./.data",
      // The app does not use OpenTelemetry (no instrumentation.ts). Excluding
      // the package stops the Vercel builder's output tracer from lstat'ing
      // a root-node_modules copy whose build layout differs from web's, which
      // previously failed the deploy with ENOENT after a successful build.
      "./node_modules/@opentelemetry/**",
      "node_modules/@opentelemetry/**",
    ],
  },
};

module.exports = nextConfig;
