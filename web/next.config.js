/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Allow HMR / assets when opening the lab Tailscale (or LAN) IP instead of localhost.
  allowedDevOrigins: ["100.64.0.5", "192.168.1.50", "fsb-01"],
  // /v1 and /health are handled by App Router route handlers with long generate timeouts
  // (Next rewrites abort ~30s and return a non-JSON 500).
};

module.exports = nextConfig;
