/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Allow HMR when opening the UI via a LAN / Tailscale hostname instead of localhost.
  // Override locally as needed; keep lab-specific IPs out of the public default.
  allowedDevOrigins: process.env.SPRUCER_DEV_ORIGINS
    ? process.env.SPRUCER_DEV_ORIGINS.split(",").map((s) => s.trim()).filter(Boolean)
    : [],
  // /v1 and /health are handled by App Router route handlers with long generate timeouts
  // (Next rewrites abort ~30s and return a non-JSON 500).
};

module.exports = nextConfig;
