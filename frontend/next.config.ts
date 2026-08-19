import type { NextConfig } from "next";

const backendUrl = process.env.WEALTH_COPILOT_BACKEND_URL ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
