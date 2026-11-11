export class ApiError extends Error {
  constructor(public status: number) {
    super(
      status === 401
        ? "Please sign in again."
        : status === 403
          ? "You do not have access to this action."
          : status === 404
            ? "This room or session is unavailable."
            : status === 409
              ? "Not available yet. Refresh the room to check the schedule."
              : "Could not load the workspace. Please try again.",
    );
  }
}

// The CSRF digest is bound to the session cookie, so one lookup per page load
// is enough. A 403 drops the cached value and retries once with a fresh one.
let csrf: Promise<string> | null = null;

function csrfToken(): Promise<string> {
  csrf ??= fetch("/api/auth/me", {
    signal: AbortSignal.timeout(5000),
    credentials: "same-origin",
    cache: "no-store",
  })
    .then(async (me) => {
      if (!me.ok) throw new ApiError(me.status);
      const account = await me.json();
      if (typeof account?.csrf_token !== "string") throw new ApiError(503);
      return account.csrf_token as string;
    })
    .catch((error) => {
      csrf = null;
      throw error;
    });
  return csrf;
}

async function send(path: string, body: object | undefined, keepalive: boolean) {
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["X-CSRF-Token"] = await csrfToken();
    headers["Content-Type"] = "application/json";
  }
  return fetch(`/api/workspace${path}`, {
    signal: AbortSignal.timeout(5000),
    credentials: "same-origin",
    cache: "no-store",
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive,
  });
}

export async function api<T>(
  path: string,
  body?: object,
  keepalive = false,
): Promise<T> {
  let response = await send(path, body, keepalive);
  if (response.status === 403 && body !== undefined) {
    csrf = null;
    response = await send(path, body, keepalive);
  }
  if (!response.ok) throw new ApiError(response.status);
  return response.json();
}

export type Room = {
  id: string;
  role_id: string;
  campaign_name: string;
  campaign_id: string;
  opens_at: string;
  closes_at: string;
  timezone: string;
  contact: string;
  ready: boolean;
  session_id: string | null;
  ended_at: string | null;
};
export type Session = { id: string; room_id: string; ended_at: string | null };
export const careers = [
  ["ba", "BA", "Business analysis", "branch"],
  ["devops", "DevOps", "Infrastructure & delivery", "layers"],
  ["fullstack", "Fullstack", "End-to-end development", "code"],
  ["frontend", "Frontend", "Web interfaces & accessibility", "window"],
  ["backend", "Backend", "Services & data systems", "database"],
  ["ai", "AI Engineer", "Applied AI systems", "sparkle"],
];
export function schedule(room: Room) {
  try {
    return `${new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: room.timezone }).format(new Date(room.opens_at))} – ${new Intl.DateTimeFormat("en-GB", { timeStyle: "short", timeZone: room.timezone }).format(new Date(room.closes_at))} · ${room.timezone}`;
  } catch {
    return `${room.opens_at} – ${room.closes_at} · UTC`;
  }
}
