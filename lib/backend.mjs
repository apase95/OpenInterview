export function backendOrigin(
  value = process.env.API_BACKEND_URL || process.env.AUTH_BACKEND_URL,
) {
  const url = new URL(value || "http://127.0.0.1:8000");
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error("API backend must be an HTTP(S) origin.");
  return url.origin;
}
