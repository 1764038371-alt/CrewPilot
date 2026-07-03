import type { NextConfig } from "next";

const apiProxyTarget = process.env.API_PROXY_TARGET ?? "https://crewpilot-api.onrender.com";

const nextConfig: NextConfig = {
  distDir: process.env.NODE_ENV === "production" ? ".next-build" : ".next",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`
      },
      {
        source: "/health",
        destination: `${apiProxyTarget}/health`
      }
    ];
  }
};

export default nextConfig;
