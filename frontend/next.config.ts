import type { NextConfig } from "next";

/**
 * The Python site (web/) is the backend: JSON API, Google sign-in, the Gmail connection through AgentCore
 * Identity, and the admin /people page. Locally it runs on :8080 and this app proxies those paths to it,
 * so the browser sees one origin and one session cookie.
 */
const api = (process.env.SCAMSHIELD_API_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");

const backendPaths = [
  "/api/:path*",
  "/signin/google",
  "/signin/callback",
  "/signin/dev",
  "/signout",
  "/join/:token/connect",
  "/connect/callback",
  "/people",
  "/people/:path*",
  "/static/:path*",
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return {
      beforeFiles: [
        // Local-mode Gmail consent returns to the site root with ?code=…&state=… (Google's loopback flow).
        { source: "/", has: [{ type: "query", key: "state" }], destination: `${api}/` },
        ...backendPaths.map((source) => ({ source, destination: `${api}${source}` })),
      ],
      afterFiles: [],
      fallback: [],
    };
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
