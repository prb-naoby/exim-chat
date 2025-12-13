import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Skip ESLint during builds (especially for CI)
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Skip TypeScript errors during builds (especially for CI)
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
