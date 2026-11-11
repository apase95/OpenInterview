import "server-only";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { backendOrigin } from "./backend.mjs";
import { returnPath } from "./return-path";

export async function requireResource(path: string, target: string) {
  const jar = await cookies();
  const response = await fetch(`${backendOrigin()}/workspace${path}`, {
    headers: { Cookie: jar.toString() },
    cache: "no-store",
    redirect: "manual",
    signal: AbortSignal.timeout(5000),
  });
  if (response.status === 401)
    redirect(`/login?return_to=${encodeURIComponent(returnPath(target))}`);
  if (response.status === 403 || response.status === 404) notFound();
  if (!response.ok)
    throw new Error("Workspace unavailable. Please try again later.");
  return response.json();
}
