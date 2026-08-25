/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["*.daytonaproxy01.net"],
  // Self-contained server bundle for Docker/OCI deploys. Vercel ignores this
  // and uses its own builder; other hosts get a runnable server.js.
  output: "standalone",
  // Cap build-time parallelism: the app has ~60 routes, and full parallel
  // static generation exhausts build-runner memory (~4 GB), which kills CI
  // builds mid-prerender. Lower CPU count trades a slower build for one
  // that actually finishes.
  experimental: {
    cpus: Math.max(1, Number(process.env.AEON_BUILD_CPUS || 1)),
  },

  // NOTE: no serverExternalPackages / outputFileTracingExcludes for
  // @opentelemetry — nothing in the app imports it, and marking it external
  // while also excluding it from traces guarantees MODULE_NOT_FOUND at every
  // Node lambda cold start.
};

// Freebuff hosting builds from the REPO ROOT: the build command runs
// `next build` inside web/ and then copies web/.next to <root>/.next.
// By default Next.js emits module traces (*.nft.json) relative to the app
// directory (web/), so after the copy every traced node_modules path is
// wrong and every Node serverless function (/api routes, SSR) crashes at
// cold start while static assets keep working. Pinning the tracing root to
// the repo root makes trace paths resolve against <root>/node_modules.
// Vercel's own frontend project (rootDirectory=web) is detected via VERCEL=1
// and keeps its default behavior.
if (process.env.VERCEL !== "1" && process.env.AEON_DOCKER_BUILD !== "1") {
  const path = require("path");
  nextConfig.outputFileTracingRoot = path.join(__dirname, "..");
}

module.exports = nextConfig;
