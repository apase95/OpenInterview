import { backendOrigin } from "./lib/backend.mjs";
export { backendOrigin as authBackend } from "./lib/backend.mjs";

// Browsers reach only the auth and workspace APIs. Developer-only backend
// routes such as /local/voice and /health are never proxied.
export default {
  output: "standalone",
  async redirects() {
    return [{ source: "/signup", destination: "/login", permanent: true }];
  },
  async rewrites() {
    const origin = backendOrigin();
    return [
      { source: "/api/auth/:path*", destination: `${origin}/auth/:path*` },
      { source: "/api/workspace/:path*", destination: `${origin}/workspace/:path*` },
      { source: "/auth/:path*", destination: `${origin}/auth/:path*` },
    ];
  },
};
