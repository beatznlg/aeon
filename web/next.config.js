/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone' is only needed for self-hosted Docker deployments.
  // Vercel manages its own output structure; do NOT set it here.
  allowedDevOrigins: ["*.daytonaproxy01.net"],
  // Prevent the output-file tracer from lstat'ing @opentelemetry files that
  // may live at root-level node_modules (peer-dep of next) but are not
  // actually used by the application. Without this, the Vercel builder fails
  // with ENOENT during the "Traced Next.js server files" step.
  serverExternalPackages: ["@opentelemetry/api"],
  // Also exclude .data runtime files and the unused OpenTelemetry package
  // from output file tracing so the build doesn't fail on missing files.
  outputFileTracingExcludes: {
    "*": [
      "./.data/**",
      "./.data",
      "./node_modules/@opentelemetry/**",
      "../node_modules/@opentelemetry/**",
      "**/@opentelemetry/**",
    ],
  },
};

module.exports = nextConfig;
