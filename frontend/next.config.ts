import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
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
