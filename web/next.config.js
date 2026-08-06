/** @type {import('next').NextConfig} */
const brain = process.env.SPRUCER_PUBLIC_URL || "http://127.0.0.1:8787";

const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Same-origin proxy so session cookies work on localhost and 127.0.0.1.
    return [
      { source: "/v1/:path*", destination: `${brain}/v1/:path*` },
      { source: "/health", destination: `${brain}/health` },
    ];
  },
};

module.exports = nextConfig;
