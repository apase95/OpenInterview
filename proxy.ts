import { NextRequest, NextResponse } from "next/server";
import { backendOrigin } from "./lib/backend.mjs";
import { returnPath } from "./lib/return-path";

// Next.js 16 calls middleware "proxy". Cookie presence is never authentication.
export async function proxy(request: NextRequest) {
  const target = returnPath(request.nextUrl.pathname);
  const login = new URL("/login", request.url);
  login.searchParams.set("return_to", target);
  try {
    const response = await fetch(`${backendOrigin()}/auth/me`, {
      headers: { Cookie: request.headers.get("cookie") || "" },
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(5000),
    });
    if (response.status === 401) return NextResponse.redirect(login);
    if (!response.ok)
      return new NextResponse(
        "Sign-in service unavailable. Please try again later.",
        { status: 503, headers: { "Cache-Control": "no-store" } },
      );
    const account = await response.json();
    if (!account?.user?.id)
      return new NextResponse("Sign-in service unavailable.", { status: 503 });
    const permission = request.nextUrl.pathname.startsWith("/hr")
      ? "hr"
      : request.nextUrl.pathname.startsWith("/admin")
        ? "admin"
        : null;
    if (
      permission &&
      !account.user.grants?.some(
        (g: { permission: string }) => g.permission === permission,
      )
    ) {
      return new NextResponse("Access denied.", {
        status: 403,
        headers: { "Cache-Control": "no-store" },
      });
    }
    const next = NextResponse.next();
    next.headers.set("Cache-Control", "no-store");
    next.headers.set("Referrer-Policy", "no-referrer");
    return next;
  } catch {
    return new NextResponse(
      "Sign-in service unavailable. Please try again later.",
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export const config = {
  matcher: [
    "/roles/:path*",
    "/rooms/:path*",
    "/sessions/:path*",
    "/hr/:path*",
    "/admin/:path*",
  ],
};
