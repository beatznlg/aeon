/** @type {import('next').NextConfig} */
const nextConfig = {
  // NOTE: do NOT pin outputFileTracingRoot here.
  allowedDevOrigins: ["*.daytonaproxy01.net"],
  // NOTE: no serverExternalPackages / outputFileTracingExcludes for
  // @opentelemetry — nothing in the app imports it, and marking it external
  // while also excluding it from traces guarantees MODULE_NOT_FOUND at every
  // Node lambda cold start.
};

module.exports = nextConfig;
