import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  /** Browser → ``/api/v1/*`` on the web host → FastAPI (avoids CORS in local dev). */
  async rewrites() {
    const devPort = process.env.DEV_API_PORT || "8000";
    const target = (
      process.env.API_PROXY_TARGET ||
      (process.env.NODE_ENV === "development" ? `http://127.0.0.1:${devPort}` : "")
    )
      .trim()
      .replace(/\/+$/, "");
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
