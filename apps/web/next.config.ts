import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  /** Browser → ``/api/v1/*`` on the web host → FastAPI (set ``API_PROXY_TARGET`` at Web build time). */
  async rewrites() {
    const target = (process.env.API_PROXY_TARGET || "").trim().replace(/\/+$/, "");
    if (!target) return [];
    return [{ source: "/api/v1/:path*", destination: `${target}/api/v1/:path*` }];
  },
  async redirects() {
    return [
      { source: "/pricing", destination: "/dashboard", permanent: false },
      { source: "/onboarding", destination: "/dashboard", permanent: false },
      { source: "/export/deck", destination: "/dashboard", permanent: false },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "trafficradius.com.au",
        pathname: "/wp-content/**",
      },
    ],
  },
};

export default nextConfig;
